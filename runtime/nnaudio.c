/* nn::audio (AudioOut: raw PCM output) on Windows waveOut, and nn::codec::HardwareOpusDecoder.
 *
 * What the game does (read off its code, addresses are guest addresses):
 *   0x710373ec20  InitializeAudioOutParameter(&p); p.sampleRate (u32 at +0) = 48000; p.channelCount (u16 at +4) = n;
 *                 OpenDefaultAudioOut(&audioOut 0x7106dd48a8, &systemEvent 0x7106dd4860, p) -> Result (0 = ok);
 *                 then GetAudioOutChannelCount / SampleRate / SampleFormat. The format's value is ignored: the
 *                 mixer always writes 16-bit signed samples (0x710398b0fc: float * 32767 -> strh).
 *                 It allocates N buffers (N at 0x7106dd489c, clamped to 2..16) of 512 frames
 *                 (512 * channels * 2 bytes, capacity rounded up to 4 KB) and for each calls
 *                 SetAudioOutBufferInfo(buf, data, capacity, dataSize) and AppendAudioOutBuffer.
 *                 The AudioOutBuffer array has a stride of 0x28 bytes.
 *   0x7103987890  thread "nus3::audio update": StartAudioOut, then forever:
 *                 b = GetReleasedAudioOutBuffer(); if null: TimedWaitSystemEvent(0x7106dd4860, 32 ms) and retry;
 *                 else mix 512 frames into GetAudioOutBufferDataPointer(b) and AppendAudioOutBuffer(b).
 *                 The event is waited on at the SystemEvent's own address, so SystemEventType is its first member.
 *                 On shutdown: StopAudioOut, CloseAudioOut, GetAudioOutBufferDataPointer of every buffer to free it.
 *   0x710373f8b0  AcquireAudioDeviceNotificationForOutput(&event); a thread "AudioDeviceChange" waits on it and
 *                 calls GetActiveAudioDeviceName(char name[0x100]) (used with strcpy/strlen: a C string).
 *   0x71022bca24  SetAudioDeviceOutputVolume(name, volume): "AudioTvOutput" 1.0, "AudioStereoJackOutput" 1.4,
 *                 "AudioBuiltInSpeakerOutput" 2.0, "AudioUsbDeviceOutput" 1.0.
 *
 * AudioOutBuffer is only touched through these functions, so the field order inside its 0x28 bytes is ours
 * (the same as in the public SDK headers): +0 next, +8 data, +0x10 capacity, +0x18 data size, +0x20 data offset.
 *
 * Host side: every appended buffer is copied (6 channels are mixed down to stereo) and handed to waveOut at once.
 * A buffer is "released" when the device has finished playing its copy, in the order it was appended; the
 * guest's event is signalled then. Without an output device the buffers are released by the clock instead.
 *
 * Environment: SSBU_WAV=<file>          write the first 30 s of what is played to a WAV file
 *              SSBU_AUDIO_CHANNELS=6    grant 6 channels when the game asks for them (default: stereo, the game
 *                                       then does its own mix-down, as on a console set to stereo output)
 *              SSBU_AUDIO_LOG=1         print the statistics every second instead of every 10 s
 *              SSBU_AUDIO_MUTE=1        no host device (clock-driven)
 *              SSBU_AUDIO_TONE=1        add a quiet 440 Hz test tone to the first second (checks the host path)
 *              SSBU_OPUS_DLL=<file>     libopus DLL for the Opus decoder (default libopus-0.dll, then MSYS2's)
 *
 * HardwareOpusDecoder: the game only imports the constructor; everything else goes through the object's
 * virtual table (0x71039937b8 and following): +0x00 destructor, +0x10 GetWorkBufferSize(sampleRate, channels),
 * +0x20 Initialize(sampleRate, channels, buffer, size) -> 0 = ok, +0x28 Finalize,
 * +0x48 DecodeInterleaved(size_t *consumed, int *sampleCount, int16_t *out, size_t outBytes, in, inBytes) -> 0 = ok.
 * Each input packet starts with an 8-byte header (big-endian u32 payload length, u32 final range) as in the
 * public descriptions of the console's Opus service. Decoding is done by libopus, loaded at run time; without
 * it the decoder produces silence. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include <mmsystem.h>
#include "runtime.h"
#include "hostrt.h"

#define A0 (c->x[0])
#define A1 (c->x[1])
#define A2 (c->x[2])
#define A3 (c->x[3])
#define A4 (c->x[4])
#define A5 (c->x[5])
#define A6 (c->x[6])
#define RET(v) (c->x[0] = (uint64_t)(v))

void os_init_event(uint64_t key, int autoclear);     /* os_threads.c */
void os_signal_event(uint64_t key);

/* ---------------------------------------------------------------- AudioOut */
#define BUF_NEXT 0x00
#define BUF_DATA 0x08
#define BUF_CAPACITY 0x10
#define BUF_SIZE 0x18
#define BUF_OFFSET 0x20
#define SAMPLE_FORMAT_PCM16 2                         /* nn::audio::SampleFormat_PcmInt16 */
#define SLOTS 64                                      /* more than the game's maximum of 16 buffers */
#define WAV_SECONDS 30

typedef struct {
    WAVEHDR hdr;
    int16_t *pcm;                                     /* host copy, stereo */
    size_t capacity;                                  /* bytes allocated for pcm */
    uint64_t guest;                                   /* the guest's AudioOutBuffer */
    LONGLONG due;                                     /* clock-driven mode: when it has been "played" */
    unsigned frames;
    int prepared;
} Slot;

static CRITICAL_SECTION g_lock;
static uint64_t g_audio_out, g_event, g_device_event;
static int g_rate = 48000, g_channels = 2, g_open, g_started;
static HWAVEOUT g_wave;
static HANDLE g_wake;
static Slot g_slots[SLOTS];
static unsigned g_head, g_tail;                       /* playing queue: slots head..tail-1 (mod SLOTS) */
static uint64_t g_released[SLOTS];
static unsigned g_rel_head, g_rel_tail;
static LARGE_INTEGER g_freq;
static LONGLONG g_clock_due;
static float g_volume = 1.0f;                         /* output volume of the active device */
static int g_host_percent = -1;                      /* U1: the host volume set at open (0..100), -1 before; nnaudio_set_volume changes it */
static const char g_device_name[] = "AudioTvOutput";
/* statistics, protected by g_lock */
static unsigned long long g_total_appended, g_total_released, g_total_dropped, g_nonsilent_seconds;
static unsigned g_sec_appended, g_sec_released, g_sec_peak, g_sec_polls, g_sec_empty;
/* Underruns (bounded round 2026-10-09): the device played every buffer it had while the output was started, i.e. the
 * game did not append the next one in time; the listener hears a gap until the next AppendAudioOutBuffer. Counted from
 * the first buffer with sound on (before it the game's mixer may legitimately idle). audio_report prints them. */
static unsigned long long g_underruns, g_underrun_ticks, g_underrun_longest;
static LONGLONG g_empty_since;
static unsigned g_queue_max;
/* A second, stricter measure: at an append, the DEVICE's own play position (waveOutGetPosition, samples) had already
 * reached the end of everything handed to it: the output really ran out of samples (waveOut marks a buffer "done" when
 * its own pipeline has taken it, which can be earlier than the moment it is heard). */
static unsigned long long g_frames_submitted, g_starved;
static FILE *g_wav;
static int g_tone_left, g_heard;
static unsigned long long g_tone_phase;
static unsigned long long g_wav_bytes;

/* AUDIO_RELEASE_OBSERVER_BEGIN: all mutable queue metadata is owned by g_lock.
 * Only on/sealed/frozen, sticky errors/late and H2-owned boundary statuses are
 * inspected without it. No callback from this owner into AP while locked. */
#include <limits.h>
_Static_assert(sizeof(unsigned)==4 && SLOTS==64,"release cursor/slot contract");
_Static_assert(sizeof(ArRecord)==384 && sizeof(ArEvent)==392,"release wire v1");
_Static_assert(sizeof(ArBoundary)==5504 && sizeof(ArBoundaryEvent)==5512,"boundary wire v1");
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error Audio release observer requires little endian
#endif
typedef struct { uint64_t cursor,id,play,guest; } ArMember;
typedef struct { uint64_t id,epoch,wave; } ArControl;
typedef struct {
    ArEvent events[AR_CAP]; ArBoundaryEvent boundaries[AR_BOUNDARIES]; ArFooter footer;
    ArMember play[64],rel[64]; ArControl controls[8];
    uint64_t op,collect,write,record,control,epoch,count,drops,phase;
    uint64_t current_op,current_collect,caller,actor,pending_getter,pending_collect;
    ArStamp stamp;
    volatile LONG on,errors,sealed,frozen,late;
    int live,view_attempted;
} ArStore;
static ArStore g_ar;
static volatile LONG g_ar_lock_ready;
static volatile LONG g_ar_configured;
static __declspec(thread) unsigned t_ar_scope;
_Static_assert(sizeof(ArStore)+sizeof(t_ar_scope)+sizeof(g_ar_lock_ready)+sizeof(g_ar_configured)<=2097152,"release observer storage bound");
static LONG ar_read(volatile LONG *p) { return InterlockedCompareExchange(p,0,0); }
int audio_release_probe_enabled(void) { return ar_read(&g_ar.on)!=0; }
static void ar_fail(unsigned bit) {
    /* Post-cut ordinary audio cannot invalidate the earlier immutable packet.
     * Old AP publications use the independent late marker below. */
    if(!ar_read(&g_ar.frozen))InterlockedOr(&g_ar.errors,(LONG)bit);
}
static uint64_t ar_next(uint64_t *p) {
    if(*p==UINT64_MAX){ar_fail(AR_E_WRAP);return 0;}return ++*p;
}
/* Volatile scalar loops prohibit lazy CRT memset/memcpy in the new try section. */
static void ar_zero(void *p,size_t n) {
    volatile uint64_t *w=(volatile uint64_t *)p;for(size_t i=0;i<n/8;i++)w[i]=0;
}
static void ar_copy(void *d,const void *s,size_t n) {
    volatile uint64_t *out=(volatile uint64_t *)d;const volatile uint64_t *in=(const volatile uint64_t *)s;
    for(size_t i=0;i<n/8;i++)out[i]=in[i];
}
static void ar_scope_enter(void) { if(audio_release_probe_enabled())t_ar_scope++; }
static void ar_scope_leave(void) { if(audio_release_probe_enabled())t_ar_scope--; }
static unsigned ar_controls(void) {
    unsigned mask=0;for(unsigned i=0;i<8;i++)if(g_ar.controls[i].id)mask|=1u<<i;return mask;
}
static void ar_geometry(void) {
    unsigned np=g_tail-g_head,nr=g_rel_tail-g_rel_head;
    if(np>64)ar_fail(AR_E_PLAY_GEOMETRY);
    if(nr>64)ar_fail(AR_E_RELEASE_OVERRUN);
    for(unsigned j=0;j<np && j<64;j++) {
        unsigned c=g_head+j;ArMember *m=&g_ar.play[c%64];
        if(!m->id || m->cursor!=c || m->guest!=g_slots[c%64].guest)ar_fail(AR_E_OCCURRENCE);
    }
    for(unsigned j=0;j<nr && j<64;j++) {
        unsigned c=g_rel_head+j;ArMember *m=&g_ar.rel[c%64];
        if(!m->id || !m->play || m->cursor!=c || m->guest!=g_released[c%64])ar_fail(AR_E_OCCURRENCE);
    }
}
static void ar_header(ArRecord *r,unsigned kind) {
    ar_zero(r,sizeof *r);ar_geometry();
    r->kind=kind;r->stream_id=1;r->phase=g_ar.phase;r->op_id=g_ar.current_op;
    r->collect_id=g_ar.current_collect;r->write_seq=g_ar.write;r->device_epoch=g_ar.epoch;
    r->actor=g_ar.actor;r->caller_kind=g_ar.caller;r->detail=ar_controls();
    r->audio_out_owner=g_audio_out;r->open=g_open;r->started=g_started;r->wave=(uintptr_t)g_wave;
    r->play_head=g_head;r->play_tail=g_tail;r->rel_head=g_rel_head;r->rel_tail=g_rel_tail;
    r->valid_mask=AR_V_QUEUE_FIELDS_READ|AR_V_OWNER_FIELDS_READ|AR_V_HOST_ORDER_VALID;
    if(g_tail-g_head<=64 && g_rel_tail-g_rel_head<=64)r->valid_mask|=AR_V_QUEUE_GEOMETRY_VALID;
    else r->valid_mask|=AR_V_DIAGNOSTIC_TRUNCATED;
    if(g_rel_head!=g_rel_tail) {
        ArMember *m=&g_ar.rel[g_rel_head%64];r->front_guest=g_released[g_rel_head%64];
        r->front_release_id=m->id;r->front_play_id=m->play;r->valid_mask|=AR_V_FRONT_READ;
    }
    if(g_head!=g_tail) {
        Slot *s=&g_slots[g_head%64];r->slot=g_head%64;r->play_id=g_ar.play[g_head%64].id;
        r->guest=s->guest;r->prepared=s->prepared;r->due=(uint64_t)s->due;r->valid_mask|=AR_V_PLAYING_SLOT_READ;
    }
    ArStamp *a=&g_ar.stamp;
    r->ctx=a->ctx;r->ap_ticket=a->ticket;r->ap_epoch=a->epoch;r->ap_generation=a->generation;r->ap_stage=a->stage;
    r->ap_enter_event=a->enter_event;r->ap_bind_event=a->bind_event;r->lr=a->lr;r->audio_out_arg=a->audio_out;
    r->stamp_status=a->status;
    if(a->status==AR_STAMP_VALID || a->status==AR_STAMP_PREFIX)r->valid_mask|=AR_V_AP_STAMP_VALID;
    if(a->status==AR_STAMP_PREFIX)r->valid_mask|=AR_V_PREFIX;
    if(a->status==AR_STAMP_GAP)r->valid_mask|=AR_V_GAP;
    r->errors=(unsigned)ar_read(&g_ar.errors);
}
static ArRecord *ar_emit(ArRecord *r) {
    if(!g_ar.live || ar_read(&g_ar.frozen))return NULL;
    r->record_id=ar_next(&g_ar.record);
    if(g_ar.count==AR_CAP || !r->record_id) {
        ar_next(&g_ar.drops);ar_fail(AR_E_OBSERVER_OVERFLOW);return NULL;
    }
    ArEvent *e=&g_ar.events[g_ar.count++];r->errors=(unsigned)ar_read(&g_ar.errors);
    ar_copy(&e->r,r,sizeof *r);InterlockedExchange((volatile LONG *)&e->ready,1);return &e->r;
}
static void ar_note(unsigned kind) {
    if(!audio_release_probe_enabled())return;
    ArRecord r;ar_header(&r,kind);if(kind==AR_APPEND_REFUSE)r.decision=AR_DEC_REFUSED;ar_emit(&r);
}
static void ar_begin(unsigned caller,const ArStamp *a) {
    if(!audio_release_probe_enabled())return;
    if(g_ar.current_op){ar_fail(AR_E_CONTEXT_OVERLAP);return;}
    DWORD error=GetLastError();g_ar.actor=GetCurrentThreadId();SetLastError(error);
    g_ar.current_op=ar_next(&g_ar.op);g_ar.caller=caller;ar_zero(&g_ar.stamp,sizeof g_ar.stamp);
    if(a) {
        ar_copy(&g_ar.stamp,a,sizeof *a);
        if(a->status==AR_STAMP_INVALID)ar_fail(AR_E_AP_STAMP);
        if(ar_read(&g_ar.sealed) && a->ticket)audio_release_probe_late(a->ticket);
    }
    g_ar.pending_getter=caller==AR_CALL_GETTER;
}
static void ar_end(void) {
    if(!audio_release_probe_enabled())return;
    if(t_ar_scope>1){ar_fail(AR_E_CONTEXT_OVERLAP);return;}
    g_ar.current_op=0;g_ar.current_collect=0;g_ar.caller=0;g_ar.pending_getter=0;
    ar_zero(&g_ar.stamp,sizeof g_ar.stamp);
}
static uint64_t ar_write(void) { return audio_release_probe_enabled()?ar_next(&g_ar.write):0; }
static void ar_collect_begin(int all,LONGLONG now) {
    if(!audio_release_probe_enabled())return;
    if(!g_ar.current_op || g_ar.current_collect)ar_fail(AR_E_CONTEXT_OVERLAP);
    g_ar.current_collect=ar_next(&g_ar.collect);g_ar.pending_collect++;
    ArRecord r;ar_header(&r,AR_COLLECT_BEGIN);r.everything=(unsigned)all;r.now=(uint64_t)now;
    r.valid_mask|=AR_V_ORIGINAL_COLLECT_NOW_READ;ar_emit(&r);
}
static void ar_check(int all,LONGLONG now,unsigned decision,unsigned flags,unsigned mask) {
    if(!audio_release_probe_enabled())return;
    ArRecord r;ar_header(&r,AR_CHECK);r.everything=(unsigned)all;r.now=(uint64_t)now;
    r.decision=decision;r.flags=flags;r.valid_mask|=AR_V_ORIGINAL_COLLECT_NOW_READ|mask;ar_emit(&r);
}
static void ar_publish(unsigned pc,unsigned rc,uint64_t guest,int all,LONGLONG now) {
    if(!audio_release_probe_enabled())return;
    if((unsigned)(rc-g_rel_head)>=64)ar_fail(AR_E_RELEASE_OVERRUN);
    ArMember p=g_ar.play[pc%64],old=g_ar.rel[rc%64];
    if(!p.id || p.cursor!=pc || p.guest!=guest || !guest)ar_fail(AR_E_OCCURRENCE);
    uint64_t id=ar_write();g_ar.rel[rc%64]=(ArMember){rc,id,p.id,guest};
    g_ar.play[pc%64]=(ArMember){0};
    ArRecord r;ar_header(&r,AR_PUBLISH);r.play_id=p.id;r.release_id=id;r.guest=guest;r.slot=pc%64;
    r.everything=(unsigned)all;r.now=(uint64_t)now;r.valid_mask|=AR_V_ORIGINAL_COLLECT_NOW_READ;
    /* On overrun flags carries the overwritten release id (not a tested flag). */
    if((unsigned)(rc-g_rel_head)>=64)r.flags=old.id;
    ar_emit(&r);
}
static void ar_collect_end(int all,LONGLONG now,int n) {
    if(!audio_release_probe_enabled())return;
    ArRecord r;ar_header(&r,AR_COLLECT_END);r.everything=(unsigned)all;r.now=(uint64_t)now;r.n=(unsigned)n;
    r.valid_mask|=AR_V_ORIGINAL_COLLECT_NOW_READ;ar_emit(&r);g_ar.current_collect=0;g_ar.pending_collect--;
}
static void ar_getter_post(int called,int n) {
    if(!audio_release_probe_enabled())return;
    ArRecord r;ar_header(&r,AR_POSTCOLLECT);r.n=(unsigned)n;
    r.decision=called?AR_DEC_COLLECT_CALLED:AR_DEC_COLLECT_SKIPPED_CLOSED;ar_emit(&r);
}
static void ar_pop(unsigned before,int popped,uint64_t value) {
    if(!audio_release_probe_enabled())return;
    ArMember m={0};if(popped){m=g_ar.rel[before%64];ar_write();g_ar.rel[before%64]=(ArMember){0};
        if(!m.id || m.cursor!=before || m.guest!=value || !value)ar_fail(AR_E_OCCURRENCE);}
    ArRecord r;ar_header(&r,AR_POP);r.popped=(unsigned)popped;r.returned=value;
    if(popped){r.slot=before%64;r.play_id=m.play;r.release_id=m.id;r.guest=value;r.valid_mask|=AR_V_POP_LOAD_VALID;}
    ar_emit(&r);
}
static void ar_append(unsigned cursor,Slot *s) {
    if(!audio_release_probe_enabled())return;
    uint64_t id=ar_write();g_ar.play[cursor%64]=(ArMember){cursor,id,0,s->guest};
    if(!s->guest)ar_fail(AR_E_OCCURRENCE);
    ArRecord r;ar_header(&r,AR_APPEND);r.play_id=id;r.guest=s->guest;r.slot=cursor%64;r.n=s->frames;
    r.prepared=s->prepared;r.due=(uint64_t)s->due;r.detail=(uint64_t)g_clock_due;r.decision=AR_DEC_ACCEPTED;ar_emit(&r);
}
static void ar_start(unsigned kind,unsigned cursor) {
    if(!audio_release_probe_enabled())return;
    if(kind!=AR_START_COMMIT)ar_write();
    ArRecord r;ar_header(&r,kind);r.detail=(uint64_t)g_clock_due;
    if(kind==AR_START_SLOT){Slot *s=&g_slots[cursor%64];r.slot=cursor%64;r.play_id=g_ar.play[cursor%64].id;
        r.guest=s->guest;r.prepared=s->prepared;r.due=(uint64_t)s->due;r.n=s->frames;}
    ar_emit(&r);
}
static void ar_open_reset(void) {
    if(!audio_release_probe_enabled())return;
    if(ar_controls())ar_fail(AR_E_CONTROL_AMBIGUOUS);
    ar_next(&g_ar.epoch);ar_write();ar_zero(g_ar.play,sizeof g_ar.play);ar_zero(g_ar.rel,sizeof g_ar.rel);
    ar_note(AR_OPEN_RESET);
}
static uint64_t ar_intent(HWAVEOUT w) {
    if(!audio_release_probe_enabled())return 0;
    unsigned i=0;while(i<8 && g_ar.controls[i].id)i++;
    uint64_t id=ar_next(&g_ar.control);
    if(i==8){ar_fail(AR_E_CONTROL_OVERFLOW);return 0;}
    if(ar_controls())ar_fail(AR_E_CONTROL_AMBIGUOUS);
    g_ar.controls[i]=(ArControl){id,g_ar.epoch,(uintptr_t)w};
    ArRecord r;ar_header(&r,AR_RESET_INTENT);r.control_id=id;r.slot=i;r.valid_mask|=AR_V_CONTROL_VALID;ar_emit(&r);return id;
}
static void ar_reset_commit(uint64_t id,HWAVEOUT w,MMRESULT result) {
    if(!audio_release_probe_enabled())return;
    unsigned i=0;while(i<8 && g_ar.controls[i].id!=id)i++;
    if(!id || i==8 || g_ar.controls[i].epoch!=g_ar.epoch || g_ar.controls[i].wave!=(uintptr_t)g_wave || w!=g_wave)
        ar_fail(AR_E_CONTROL_AMBIGUOUS);
    ArRecord r;ar_header(&r,AR_RESET_COMMIT);r.control_id=id;r.slot=i;r.detail=w!=NULL;r.n=w?result:0;
    r.valid_mask|=AR_V_CONTROL_VALID|(w?AR_V_RESET_RETURN_VALID:0);ar_emit(&r);
}
static void ar_lifecycle(uint64_t id) {
    if(!audio_release_probe_enabled())return;
    ar_write();ArRecord r;ar_header(&r,AR_LIFECYCLE_COMMIT);r.control_id=id;r.valid_mask|=AR_V_CONTROL_VALID;
    unsigned i=0;while(i<8 && g_ar.controls[i].id!=id)i++;
    if(!id || i==8)ar_fail(AR_E_CONTROL_AMBIGUOUS);else g_ar.controls[i]=(ArControl){0};
    ar_emit(&r);
}
void audio_release_probe_late(uint64_t ticket) {
    if(audio_release_probe_enabled() && ticket && ar_read(&g_ar.sealed))InterlockedOr(&g_ar.late,AR_E_LATE_INVALID);
}
int audio_release_probe_configure(void) {
    DWORD error=GetLastError();
    if(InterlockedCompareExchange(&g_ar_configured,1,0)){SetLastError(error);return 0;}
    /* Only called after explicit option validation. Pre-touch before any guests. */
    ar_zero(&g_ar,sizeof g_ar);
    if(!ar_read(&g_ar_lock_ready)){ar_fail(AR_E_UNINITIALIZED);SetLastError(error);return 0;}
    if(!TryEnterCriticalSection(&g_lock)){ar_fail(AR_E_INIT_BUSY);SetLastError(error);return 0;}
    int ok=!g_open && g_head==g_tail && g_rel_head==g_rel_tail;
    if(!ok)ar_fail(AR_E_INIT_STATE);
    /* Publish while still owning g_lock: no original owner can enter off-mode
     * and then observe enablement halfway through that same lock scope. */
    if(ok)InterlockedExchange(&g_ar.on,1);
    LeaveCriticalSection(&g_lock);
    SetLastError(error);return ok;
}
static void ar_footer(int sealed) {
    ArFooter *f=&g_ar.footer;ar_zero(f,sizeof *f);
    f->version=1;f->layout=1;f->record_bytes=384;f->boundary_bytes=5504;f->capacity=AR_CAP;
    f->boundary_capacity=8;f->stream_id=1;f->sealed=sealed;f->failed=!sealed;f->record_count=g_ar.count;
    f->attempted_records=g_ar.record;f->dropped_records=g_ar.drops;f->last_attempted_record_id=g_ar.record;
    if(g_ar.count){f->first_record_id=g_ar.events[0].r.record_id;f->first_op_id=g_ar.events[0].r.op_id;f->first_write_seq=g_ar.events[0].r.write_seq;}
    f->last_op_id=g_ar.op;f->last_write_seq=g_ar.write;f->last_collect_id=g_ar.collect;f->device_epoch=g_ar.epoch;f->phase=g_ar.phase;
    f->pending_getter_count=g_ar.pending_getter;f->pending_collect_count=g_ar.pending_collect;
    for(unsigned i=0;i<8;i++){
        f->pending_control_count+=g_ar.controls[i].id!=0;
        f->boundary_statuses[i]=ar_read((volatile LONG *)&g_ar.boundaries[i].ready)?g_ar.boundaries[i].b.r.stamp_status:AR_B_NOT_REACHED;
    }
    for(unsigned i=0;i<g_ar.count;i++){
        ArEvent *e=&g_ar.events[i];if(ar_read((volatile LONG *)&e->ready))f->ready_count++;else ar_fail(AR_E_UNREADY);
        if(e->r.kind<23)f->kind_counts[e->r.kind]++;
    }
    if(f->pending_control_count)ar_fail(AR_E_CONTROL_AMBIGUOUS);
    f->errors=(unsigned)ar_read(&g_ar.errors);f->failed|=f->errors!=0;
}
static int ar_boundary_failure(ArBoundaryEvent *e,const ArBoundaryStamp *s,unsigned status,unsigned error) {
    ar_fail(error);ArRecord *r=&e->b.r;ar_zero(&e->b,sizeof e->b);
    r->kind=AR_BOUNDARY;r->stream_id=1;r->stamp_status=status;
    if(s){r->valid_mask=AR_V_BOUNDARY_STAMP_VALID;r->guest=s->frame;r->detail=s->event;r->control_id=s->transition;
        r->n=s->slot;r->ap_stage=s->stage;r->ap_epoch=s->epoch;r->ap_generation=s->generation;r->actor=s->actor;r->decision=s->hold;}
    r->errors=(unsigned)ar_read(&g_ar.errors);InterlockedExchange((volatile LONG *)&e->ready,1);return (int)status;
}
int audio_release_probe_boundary(const ArBoundaryStamp *s) {
    if(!audio_release_probe_enabled())return AR_B_UNINITIALIZED;
    DWORD error=GetLastError();
    if(ar_read(&g_ar.frozen)){audio_release_probe_late(1);SetLastError(error);return AR_B_INVALID;}
    if(!s || s->slot>=5){ar_fail(AR_E_BOUNDARY_INVALID);SetLastError(error);return AR_B_INVALID;}
    ArBoundaryEvent *e=&g_ar.boundaries[s->slot];unsigned status=AR_B_OK;
    if(ar_read((volatile LONG *)&e->ready)) {ar_fail(AR_E_BOUNDARY_INVALID);status=AR_B_INVALID;}
    else if(!ar_read(&g_ar_lock_ready))status=ar_boundary_failure(e,s,AR_B_UNINITIALIZED,AR_E_UNINITIALIZED);
    else if(t_ar_scope)status=ar_boundary_failure(e,s,AR_B_REENTRANT,AR_E_REENTRANT);
    else if(!s->valid)status=ar_boundary_failure(e,s,AR_B_INVALID,AR_E_BOUNDARY_INVALID);
    else if(!TryEnterCriticalSection(&g_lock))status=ar_boundary_failure(e,s,AR_B_BUSY,AR_E_BOUNDARY_BUSY|(s->slot==4?AR_E_END_BUSY:0));
    else {
        /* No OS except the intrinsic ready publication, no callbacks or other
         * locks, no clock/device/CRT work, and no guest memory in this section. */
        if(g_ar.phase!=s->slot || ar_read(&g_ar.frozen))status=ar_boundary_failure(e,s,AR_B_INVALID,AR_E_BOUNDARY_INVALID);
        else if(!s->slot && ar_controls())status=ar_boundary_failure(e,s,AR_B_INFLIGHT,AR_E_BOUNDARY_INFLIGHT);
        else {
            if(!s->slot)g_ar.live=1;g_ar.phase=s->slot+1;
            ar_zero(&e->b,sizeof e->b);ArRecord *r=&e->b.r;ar_header(r,AR_BOUNDARY);
            r->op_id=g_ar.op;r->collect_id=g_ar.collect;r->actor=s->actor;r->caller_kind=AR_CALL_BOUNDARY;
            r->ap_stage=s->stage;r->ap_epoch=s->epoch;r->ap_generation=s->generation;
            r->guest=s->frame;r->detail=s->event;r->control_id=s->transition;r->n=s->slot;r->decision=s->hold;
            r->stamp_status=AR_B_OK;r->valid_mask|=AR_V_BOUNDARY_STAMP_VALID;
            unsigned nr=g_rel_tail-g_rel_head,np=g_tail-g_head;r->slot=nr<64?nr:64;r->prepared=np<64?np:64;
            for(unsigned j=0;j<r->slot;j++){
                unsigned c=g_rel_head+j;ArMember *m=&g_ar.rel[c%64];ArReleased *d=&e->b.released[j];
                d->cursor=c;d->release_id=m->id;d->play_id=m->play;d->guest=g_released[c%64];
            }
            for(unsigned j=0;j<r->prepared;j++){
                unsigned c=g_head+j;ArPlaying *d=&e->b.playing[j];Slot *p=&g_slots[c%64];
                d->cursor=c;d->play_id=g_ar.play[c%64].id;d->guest=p->guest;d->prepared=p->prepared;d->due=(uint64_t)p->due;d->frames=p->frames;
            }
            ar_emit(r);InterlockedExchange((volatile LONG *)&e->ready,1);
            if(s->slot==4){ar_footer(1);InterlockedExchange(&g_ar.sealed,1);InterlockedExchange(&g_ar.frozen,1);}
        }
        LeaveCriticalSection(&g_lock);
    }
    SetLastError(error);return (int)status;
}
int audio_release_probe_view(ArView *out) {
    if(!audio_release_probe_enabled())return 0;
    DWORD error=GetLastError();
    if(!ar_read(&g_ar.frozen) && !g_ar.view_attempted) {
        g_ar.view_attempted=1;
        /* Deferred H2 only: this is a failed freeze, never an endpoint retry. */
        if(!t_ar_scope && TryEnterCriticalSection(&g_lock)) {
            ar_fail(AR_E_BOUNDARY_INVALID);ar_footer(0);InterlockedExchange(&g_ar.frozen,1);LeaveCriticalSection(&g_lock);
        }
    }
    out->available=ar_read(&g_ar.frozen)!=0;out->events=out->available?g_ar.events:NULL;
    out->footer=out->available?&g_ar.footer:NULL;out->boundaries=g_ar.boundaries;
    out->late_invalid=(unsigned)ar_read(&g_ar.late);out->errors=(unsigned)ar_read(&g_ar.errors);
    SetLastError(error);return 1;
}
/* AUDIO_RELEASE_OBSERVER_END */

static LONGLONG now_ticks(void) { LARGE_INTEGER t; QueryPerformanceCounter(&t); return t.QuadPart; }

static void wav_header(void) {
    unsigned char h[44];
    uint32_t data = (uint32_t)g_wav_bytes, riff = data + 36, rate = (uint32_t)g_rate, bytes_per_sec = rate * 4;
    uint16_t fmt = 1, ch = 2, align = 4, bits = 16;
    uint32_t fmt_size = 16;
    memcpy(h, "RIFF", 4); memcpy(h + 4, &riff, 4); memcpy(h + 8, "WAVEfmt ", 8); memcpy(h + 16, &fmt_size, 4);
    memcpy(h + 20, &fmt, 2); memcpy(h + 22, &ch, 2); memcpy(h + 24, &rate, 4); memcpy(h + 28, &bytes_per_sec, 4);
    memcpy(h + 32, &align, 2); memcpy(h + 34, &bits, 2); memcpy(h + 36, "data", 4); memcpy(h + 40, &data, 4);
    fseek(g_wav, 0, SEEK_SET);
    fwrite(h, 1, sizeof h, g_wav);
    fseek(g_wav, 0, SEEK_END);
    fflush(g_wav);
}

static int16_t sat16(int v) { return (int16_t)(v > 32767 ? 32767 : v < -32768 ? -32768 : v); }

/* Copies a guest buffer to host stereo samples; returns the number of frames and the peak amplitude. */
static unsigned convert(Slot *s, const int16_t *in, size_t bytes, unsigned *peak_out) {
    unsigned frames = (unsigned)(bytes / (2u * (unsigned)g_channels)), peak = 0;
    size_t need = (size_t)frames * 4;
    if (need > s->capacity || !s->pcm) {
        free(s->pcm);
        s->capacity = need < 4096 ? 4096 : need;
        s->pcm = malloc(s->capacity);
    }
    int16_t *out = s->pcm;
    for (unsigned i = 0; i < frames; i++) {
        float l, r;
        if (g_channels == 6) {                        /* FL FR FC LFE RL RR */
            const int16_t *p = in + (size_t)i * 6;
            l = p[0] + 0.707f * p[2] + 0.251f * p[3] + 0.707f * p[4];
            r = p[1] + 0.707f * p[2] + 0.251f * p[3] + 0.707f * p[5];
        } else if (g_channels == 1) {
            l = r = in[i];
        } else {
            const int16_t *p = in + (size_t)i * (unsigned)g_channels;
            l = p[0];
            r = p[1];
        }
        int li = (int)(l * g_volume), ri = (int)(r * g_volume);
        out[i * 2] = sat16(li);
        out[i * 2 + 1] = sat16(ri);
        unsigned a = (unsigned)abs(out[i * 2]), b = (unsigned)abs(out[i * 2 + 1]);
        if (a > peak) peak = a;
        if (b > peak) peak = b;
    }
    *peak_out = peak;
    return frames;
}

/* SSBU_AUDIO_TONE: a quiet 440 Hz tone over the first second, to check the host output path by ear. */
static unsigned add_tone(int16_t *pcm, unsigned frames, unsigned peak) {
    for (unsigned i = 0; i < frames; i++, g_tone_phase++) {
        int v = (int)(3000.0 * sin(6.283185307179586 * 440.0 * (double)g_tone_phase / g_rate));
        for (int k = 0; k < 2; k++) {
            pcm[i * 2 + k] = sat16(pcm[i * 2 + k] + v);
            unsigned a = (unsigned)abs(pcm[i * 2 + k]);
            if (a > peak) peak = a;
        }
    }
    return peak;
}

/* Moves the buffers that have finished playing to the released list. Returns how many. Caller holds g_lock. */
static int collect_finished(int everything) {
    int n = 0;
    LONGLONG now = now_ticks();
    ar_collect_begin(everything,now);
    while (g_head != g_tail) {
        Slot *s = &g_slots[g_head % SLOTS];
        unsigned decision=AR_DEC_FORCED,flags=0,mask=0;
        if (!everything) {
            if (s->prepared) {
                flags=s->hdr.dwFlags;mask=AR_V_FLAGS_ACTUALLY_TESTED;
                decision=(flags & WHDR_DONE)?AR_DEC_PASS_DEVICE:AR_DEC_BLOCK_DEVICE;
            } else {
                mask=AR_V_STARTED_ACTUALLY_TESTED;
                if (!g_started) decision=AR_DEC_BLOCK_STOPPED;
                else { mask|=AR_V_NOW_USED_IN_FALLBACK_COMPARE|AR_V_DUE_USED_IN_FALLBACK_COMPARE;
                    decision=now < s->due?AR_DEC_BLOCK_NOT_DUE:AR_DEC_PASS_FALLBACK; }
            }
        }
        ar_check(everything,now,decision,flags,mask);
        if(decision==AR_DEC_BLOCK_DEVICE || decision==AR_DEC_BLOCK_STOPPED || decision==AR_DEC_BLOCK_NOT_DUE)break;
        unsigned ar_pc=g_head,ar_rc=g_rel_tail;
        if (s->prepared) { waveOutUnprepareHeader(g_wave, &s->hdr, sizeof s->hdr); s->prepared = 0; }
        g_released[g_rel_tail++ % SLOTS] = s->guest;
        g_head++;
        g_total_released++;
        g_sec_released++;
        n++;
        ar_publish(ar_pc,ar_rc,s->guest,everything,now);
    }
    if (n && !everything && g_head == g_tail && g_started && g_heard && !g_empty_since) { g_underruns++; g_empty_since = now; }
    ar_collect_end(everything,now,n);
    return n;
}

static DWORD WINAPI audio_thread(LPVOID arg) {
    (void)arg;
    LONGLONG next_report = now_ticks() + g_freq.QuadPart;
    unsigned seconds = 0;
    int every_second = getenv("SSBU_AUDIO_LOG") != NULL;
    unsigned acc_appended = 0, acc_released = 0, acc_peak = 0, acc_polls = 0, acc_empty = 0;
    for (;;) {
        WaitForSingleObject(g_wake, 2);
        EnterCriticalSection(&g_lock);
        ar_scope_enter();
        ar_begin(AR_CALL_AUDIO_THREAD,NULL);
        if(audio_release_probe_enabled()) {ArRecord r;ar_header(&r,AR_THREAD_POLL);
            r.decision=g_open?AR_DEC_COLLECT_CALLED:AR_DEC_COLLECT_SKIPPED_CLOSED;ar_emit(&r);}
        int n = g_open ? collect_finished(0) : 0;
        uint64_t ev = g_event;
        LONGLONG now = now_ticks();
        int report = 0;
        unsigned queued = g_tail - g_head;
        if (now >= next_report) {
            next_report += g_freq.QuadPart;
            seconds++;
            if (g_sec_peak) g_nonsilent_seconds++;
            acc_appended += g_sec_appended; acc_released += g_sec_released; acc_polls += g_sec_polls; acc_empty += g_sec_empty;
            if (g_sec_peak > acc_peak) acc_peak = g_sec_peak;
            g_sec_appended = g_sec_released = g_sec_peak = g_sec_polls = g_sec_empty = 0;
            if (g_wav) wav_header();
            report = g_open && (every_second || seconds % 10 == 0);
        }
        ar_end();
        ar_scope_leave();
        LeaveCriticalSection(&g_lock);
        if (n && ev) os_signal_event(ev);
        if (report) {
            printf("nn::audio: t=%us appended %u released %u polls %u (empty %u) queued %u peak %u, total %llu buffers, %llu s with sound\n",
                   seconds, acc_appended, acc_released, acc_polls, acc_empty, queued, acc_peak, g_total_appended, g_nonsilent_seconds);
            fflush(stdout);
            acc_appended = acc_released = acc_peak = acc_polls = acc_empty = 0;
        }
    }
}

static void audio_InitializeAudioOutParameter(Ctx *c) {   /* (AudioOutParameter *): u32 sampleRate, u16 channelCount, u16 reserved */
    wr32(A0, 0);
    wr16(A0 + 4, 0);
    wr16(A0 + 6, 0);
}

static void audio_OpenDefaultAudioOut(Ctx *c) {       /* (AudioOut *, nn::os::SystemEvent *, const AudioOutParameter &) -> Result */
    unsigned want_rate = rd32(A2), want_channels = rd16(A2 + 4);
    EnterCriticalSection(&g_lock);
    ar_scope_enter();
    ar_begin(AR_CALL_OPEN,NULL);ar_note(AR_OPEN_BEFORE);
    g_audio_out = A0;
    g_event = A1;
    g_rate = want_rate ? (int)want_rate : 48000;
    const char *env = getenv("SSBU_AUDIO_CHANNELS");
    g_channels = want_channels == 6 && env && atoi(env) == 6 ? 6 : 2;
    g_head = g_tail = g_rel_head = g_rel_tail = 0;
    g_frames_submitted = 0;
    g_started = 0;
    g_clock_due = 0;
    os_init_event(g_event, 1);
    g_wave = NULL;
    if (!getenv("SSBU_AUDIO_MUTE")) {
        WAVEFORMATEX f;
        memset(&f, 0, sizeof f);
        f.wFormatTag = WAVE_FORMAT_PCM;
        f.nChannels = 2;
        f.nSamplesPerSec = (DWORD)g_rate;
        f.wBitsPerSample = 16;
        f.nBlockAlign = 4;
        f.nAvgBytesPerSec = (DWORD)g_rate * 4;
        MMRESULT r = waveOutOpen(&g_wave, WAVE_MAPPER, &f, (DWORD_PTR)g_wake, 0, CALLBACK_EVENT);
        if (r != MMSYSERR_NOERROR) { g_wave = NULL; printf("nn::audio: waveOutOpen failed (%u): no sound, buffers are released by the clock\n", (unsigned)r); }
        else {
            waveOutPause(g_wave);                     /* nothing plays before StartAudioOut */
            /* Test copies are silent: only the copies a person plays (ssbu_native.exe, ssbu_user.exe) are audible,
             * like the window rule in display.c. The device stays open, so timing is the same as with sound.
             * SSBU_VOLUME=<0..100> overrides either way. */
            char exe[MAX_PATH] = "";
            GetModuleFileNameA(NULL, exe, sizeof exe);
            const char *base = strrchr(exe, '\\') ? strrchr(exe, '\\') + 1 : exe, *vol = getenv("SSBU_VOLUME");
            int gfx_volume(void);                     /* U1: graphics.ini volume = auto | 0..100, for the copies a person plays only (gfx_options.c) */
#ifdef _WIN32
            int person = !_stricmp(base, "ssbu_native.exe") || !_stricmp(base, "ssbu_user.exe") || !_stricmp(base, "ssbu_native_rb.exe");   /* (_rb: the rollback pair) */
#else
            if (strrchr(base, '/')) base = strrchr(base, '/') + 1;
            int person = !strcmp(base, "ssbu_native") || !strcmp(base, "ssbu_user");      /* Linux build: no ".exe" */
#endif
            int percent = vol ? atoi(vol) : person ? (gfx_volume() >= 0 ? gfx_volume() : 100) : 0;
            if (percent < 0) percent = 0;
            if (percent > 100) percent = 100;
            DWORD level = (DWORD)(0xffff * percent / 100);
            waveOutSetVolume(g_wave, level | level << 16);
            g_host_percent = percent;
            printf("nn::audio: host volume %d%%%s\n", percent, percent ? "" : " (test copy: silent; SSBU_VOLUME=<0..100> to change)");
        }
    }
    const char *wav = getenv("SSBU_WAV");
    if (wav && !g_wav) {
        g_wav = fopen(wav, "wb");
        g_wav_bytes = 0;
        if (g_wav) wav_header();
    }
    g_tone_left = getenv("SSBU_AUDIO_TONE") ? g_rate / 512 : 0;
    g_open = 1;
    ar_open_reset();ar_end();
    ar_scope_leave();
    LeaveCriticalSection(&g_lock);
    printf("nn::audio: OpenDefaultAudioOut: game asks %u Hz, %u channels -> %d Hz, %d channels, 16-bit, %s\n",
           want_rate, want_channels, g_rate, g_channels, g_wave ? "waveOut device open" : "no host device");
    RET(0);
}

static void audio_GetAudioOutChannelCount(Ctx *c) { RET(g_channels); }
static void audio_GetAudioOutSampleRate(Ctx *c) { RET(g_rate); }
static void audio_GetAudioOutSampleFormat(Ctx *c) { RET(SAMPLE_FORMAT_PCM16); }

static void audio_SetAudioOutBufferInfo(Ctx *c) {     /* (AudioOutBuffer *, void *data, size_t capacity, size_t dataSize) */
    wr64(A0 + BUF_NEXT, 0);
    wr64(A0 + BUF_DATA, A1);
    wr64(A0 + BUF_CAPACITY, A2);
    wr64(A0 + BUF_SIZE, A3);
    wr64(A0 + BUF_OFFSET, 0);
}

static void audio_GetAudioOutBufferDataPointer(Ctx *c) { RET(rd64(A0 + BUF_DATA)); }

static void audio_AppendAudioOutBuffer(Ctx *c) {      /* (AudioOut *, AudioOutBuffer *) -> bool */
    uint64_t buf = A1, data = rd64(buf + BUF_DATA), size = rd64(buf + BUF_SIZE);
    int ok = 0;
    EnterCriticalSection(&g_lock);
    ar_scope_enter();
    ar_begin(AR_CALL_APPEND,NULL);ar_note(AR_APPEND_BEGIN);
    if (g_open && g_tail - g_head < SLOTS && data && size) {
        Slot *s = &g_slots[g_tail % SLOTS];
        unsigned peak = 0;
        unsigned frames = convert(s, (const int16_t *)(uintptr_t)data, (size_t)size, &peak);
        s->guest = buf;
        s->frames = frames;
        s->prepared = 0;
        if (g_tone_left > 0) { g_tone_left--; peak = add_tone(s->pcm, frames, peak); }
        if (peak && !g_heard) { g_heard = 1; printf("nn::audio: first buffer with sound (buffer %llu, peak %u)\n", g_total_appended, peak); }
        {   /* TEST ONLY, SSBU_AUDIO_HASH=<file> (round "four players"): one line per buffer the game hands to the device:
             * index, frames, peak, FNV-1a 64 of the game's own samples (before our stereo copy). Compares the mixer's output
             * of two builds (tests\p15_pcm_compare.py). One getenv at the first buffer; nothing without the variable. */
            static FILE *hf; static int tried;
            if (!tried) { const char *hp = getenv("SSBU_AUDIO_HASH"); tried = 1; if (hp && *hp) hf = fopen(hp, "w"); }
            if (hf) {
                uint64_t h = 0xcbf29ce484222325ULL;
                const uint8_t *pb = (const uint8_t *)(uintptr_t)data;
                for (uint64_t i = 0; i < size; i++) { h ^= pb[i]; h *= 0x100000001b3ULL; }
                fprintf(hf, "%llu %u %u %016llx\n", g_total_appended, frames, peak, (unsigned long long)h);
                if ((g_total_appended & 63) == 0) fflush(hf);
            }
        }
        if (g_wav && g_wav_bytes < (unsigned long long)WAV_SECONDS * (unsigned)g_rate * 4) {
            fwrite(s->pcm, 4, frames, g_wav);
            g_wav_bytes += (unsigned long long)frames * 4;
        }
        if (g_wave) {
            if (g_started && g_heard && g_frames_submitted) {
                MMTIME mt;
                memset(&mt, 0, sizeof mt);
                mt.wType = TIME_SAMPLES;
                if (waveOutGetPosition(g_wave, &mt, sizeof mt) == MMSYSERR_NOERROR && mt.wType == TIME_SAMPLES && (unsigned long long)mt.u.sample >= g_frames_submitted) g_starved++;
            }
            g_frames_submitted += frames;
            memset(&s->hdr, 0, sizeof s->hdr);
            s->hdr.lpData = (LPSTR)s->pcm;
            s->hdr.dwBufferLength = frames * 4;
            if (waveOutPrepareHeader(g_wave, &s->hdr, sizeof s->hdr) == MMSYSERR_NOERROR) {
                if (waveOutWrite(g_wave, &s->hdr, sizeof s->hdr) == MMSYSERR_NOERROR) s->prepared = 1;
                else waveOutUnprepareHeader(g_wave, &s->hdr, sizeof s->hdr);
            }
        }
        if (!s->prepared) {                           /* clock-driven: one buffer after the other in real time */
            LONGLONG now = now_ticks();
            if (g_clock_due < now) g_clock_due = now;
            g_clock_due += (LONGLONG)frames * g_freq.QuadPart / g_rate;
            s->due = g_clock_due;
        }
        unsigned ar_cursor=g_tail;
        g_tail++;
        ar_append(ar_cursor,s);
        if (g_empty_since) {
            unsigned long long gap = (unsigned long long)(now_ticks() - g_empty_since);
            g_underrun_ticks += gap; if (gap > g_underrun_longest) g_underrun_longest = gap;
            g_empty_since = 0;
        }
        if (g_tail - g_head > g_queue_max) g_queue_max = g_tail - g_head;
        g_total_appended++;
        g_sec_appended++;
        if (peak > g_sec_peak) g_sec_peak = peak;
        ok = 1;
    } else {
        g_total_dropped++;
        ar_note(AR_APPEND_REFUSE);
    }
    ar_end();
    ar_scope_leave();
    LeaveCriticalSection(&g_lock);
    RET(ok);
}

/* End-of-run line (hostrt.c report_and_exit): what the output path did in this run. */
void audio_report(FILE *out) {
    if (!g_total_appended) return;
    double f = g_freq.QuadPart ? (double)g_freq.QuadPart : 1.0;
    fprintf(out, "nn::audio: %d Hz, %d channels granted, 16-bit; %llu buffers appended, %llu released, %llu refused; deepest queue %u buffers; "
                 "underruns (device ran dry while started, after the first sound): %llu, %.1f ms in all, longest %.1f ms; %llu s with sound\n",
            g_rate, g_channels, g_total_appended, g_total_released, g_total_dropped, g_queue_max,
            g_underruns, (double)g_underrun_ticks * 1000.0 / f, (double)g_underrun_longest * 1000.0 / f, g_nonsilent_seconds);
    fprintf(out, "nn::audio: appends that found the device's own play position at the end of everything submitted (the output had no samples left): %llu of %llu\n", g_starved, g_total_appended);
}

static void audio_StartAudioOut(Ctx *c) {             /* (AudioOut *) -> Result */
    EnterCriticalSection(&g_lock);
    ar_scope_enter();
    ar_begin(AR_CALL_START,NULL);ar_note(AR_START_BEGIN);
    if (g_open && !g_started) {
        g_started = 1;
        g_clock_due = now_ticks();                    /* clock-driven buffers queued before the start begin now */
        ar_start(AR_START_STATE,0);
        for (unsigned i = g_head; i != g_tail; i++) {
            Slot *s = &g_slots[i % SLOTS];
            g_clock_due += (LONGLONG)s->frames * g_freq.QuadPart / g_rate;
            s->due = g_clock_due;
            ar_start(AR_START_SLOT,i);
        }
        if (g_wave) waveOutRestart(g_wave);
    }
    ar_start(AR_START_COMMIT,0);ar_end();
    ar_scope_leave();
    LeaveCriticalSection(&g_lock);
    printf("nn::audio: StartAudioOut (%llu buffers queued)\n", g_total_appended - g_total_released);
    RET(0);
}

static void audio_GetReleasedAudioOutBuffer(Ctx *c) { /* original single acquisition */
    uint64_t r = 0;
    ArStamp ar_stamp={0};
    if(audio_release_probe_enabled() && !ar_read(&g_ar.sealed)) {
        /* A recursive inherited caller may already own g_lock. Never add a
         * g_lock -> AP edge even on that invalid observation path. */
        if(t_ar_scope){ar_stamp.status=AR_STAMP_INVALID;ar_fail(AR_E_REENTRANT);}
        else r1_audio_release_stamp(c,audio_GetReleasedAudioOutBuffer,&ar_stamp);
    }
    EnterCriticalSection(&g_lock);
    ar_scope_enter();ar_begin(AR_CALL_GETTER,&ar_stamp);
    ar_note(AR_PRECOLLECT);
    int ar_called=g_open,ar_n=0;
    if (ar_called) ar_n=collect_finished(0);
    ar_getter_post(ar_called,ar_n);
    unsigned ar_before=g_rel_head;int ar_popped=0;
    if (g_rel_head != g_rel_tail) {r = g_released[g_rel_head++ % SLOTS];ar_popped=1;}
    ar_pop(ar_before,ar_popped,r);
    g_sec_polls++;
    if (!r) g_sec_empty++;
    ar_end();ar_scope_leave();
    LeaveCriticalSection(&g_lock);
    RET(r);
}

static void audio_StopAudioOut(Ctx *c) {              /* (AudioOut *): everything queued becomes released */
    EnterCriticalSection(&g_lock);
    ar_scope_enter();
    ar_begin(AR_CALL_STOP_FORCE,NULL);
    HWAVEOUT w = g_wave;
    uint64_t ar_control=ar_intent(w);ar_end();
    ar_scope_leave();
    LeaveCriticalSection(&g_lock);
    MMRESULT ar_result=0;
    if (w) ar_result=waveOutReset(w);                           /* marks every queued header as done */
    g_frames_submitted = 0;                           /* waveOutReset also sets the device position back to 0 */
    EnterCriticalSection(&g_lock);
    ar_scope_enter();
    ar_begin(AR_CALL_STOP_FORCE,NULL);ar_reset_commit(ar_control,w,ar_result);
    if (g_open) collect_finished(1);
    g_started = 0;
    if (g_wave) waveOutPause(g_wave);
    uint64_t ev = g_event;
    ar_lifecycle(ar_control);ar_end();
    ar_scope_leave();
    LeaveCriticalSection(&g_lock);
    if (ev) os_signal_event(ev);
    printf("nn::audio: StopAudioOut\n");
}

static void audio_CloseAudioOut(Ctx *c) {             /* (AudioOut *) */
    EnterCriticalSection(&g_lock);
    ar_scope_enter();
    ar_begin(AR_CALL_CLOSE_FORCE,NULL);
    HWAVEOUT w = g_wave;
    uint64_t ar_control=ar_intent(w);ar_end();
    ar_scope_leave();
    LeaveCriticalSection(&g_lock);
    MMRESULT ar_result=0;
    if (w) ar_result=waveOutReset(w);
    EnterCriticalSection(&g_lock);
    ar_scope_enter();
    ar_begin(AR_CALL_CLOSE_FORCE,NULL);ar_reset_commit(ar_control,w,ar_result);
    if (g_open) collect_finished(1);
    g_open = g_started = 0;
    g_wave = NULL;
    g_event = 0;
    if (g_wav) wav_header();
    ar_lifecycle(ar_control);ar_end();
    ar_scope_leave();
    LeaveCriticalSection(&g_lock);
    if (w) waveOutClose(w);
    printf("nn::audio: CloseAudioOut (%llu buffers appended, %llu released)\n", g_total_appended, g_total_released);
}

/* ---------------------------------------------------------------- audio device */
/* [sdk] 0x990f0 AcquireAudioDeviceNotificationForOutput(SystemEvent *): a second call returns 0x499 (module 153,
 * description 2; flag byte 0xc5efa2); otherwise it asks the audio device service for its output event
 * (slot +0x78 = QueryAudioDeviceOutputEvent, any failure aborts) and attaches the handle with
 * nn::os::AttachReadableHandleToSystemEvent(event, handle, managed, clear mode 1 = auto clear); Result 0.
 * The service side (not in the dump), after [doc] suyu audio/audio_device.cpp: the event is signalled when the
 * service object is created, i.e. it arrives signalled, and again whenever the output device changes.
 * Here: the output device is the Windows default render endpoint; IMMNotificationClient::OnDefaultDeviceChanged
 * (render, console role) signals the event. */
#ifdef _WIN32
typedef struct NotifyClient { const void *const *vtbl; } NotifyClient;
typedef struct { const void *const *vtbl; } ComObj;
static const GUID k_clsid_enumerator = {0xbcde0395, 0xe52f, 0x467c, {0x8e, 0x3d, 0xc4, 0x57, 0x92, 0x91, 0x69, 0x2e}};
static const GUID k_iid_enumerator = {0xa95664d2, 0x9614, 0x4f35, {0xa7, 0x46, 0xde, 0x8d, 0xb6, 0x36, 0x17, 0xe6}};
static const GUID k_iid_notify = {0x7991eec9, 0x7e89, 0x4d85, {0x83, 0x90, 0x6c, 0x70, 0x3c, 0xec, 0x60, 0xc0}};
static const GUID k_iid_unknown = {0, 0, 0, {0xc0, 0, 0, 0, 0, 0, 0, 0x46}};
#endif
static volatile LONG g_device_acquired, g_device_changes;
#ifdef _WIN32
static HRESULT STDMETHODCALLTYPE nc_query(NotifyClient *self, const GUID *iid, void **out) {
    if (!memcmp(iid, &k_iid_notify, sizeof *iid) || !memcmp(iid, &k_iid_unknown, sizeof *iid)) { *out = self; return S_OK; }
    *out = NULL; return E_NOINTERFACE;
}
static ULONG STDMETHODCALLTYPE nc_ref(NotifyClient *self) { (void)self; return 1; }      /* static object */
static HRESULT STDMETHODCALLTYPE nc_state(NotifyClient *self, const WCHAR *id, DWORD state) { (void)self; (void)id; (void)state; return S_OK; }
static HRESULT STDMETHODCALLTYPE nc_id(NotifyClient *self, const WCHAR *id) { (void)self; (void)id; return S_OK; }
static HRESULT STDMETHODCALLTYPE nc_default(NotifyClient *self, int flow, int role, const WCHAR *id) {
    (void)self; (void)id;
    if (flow == 0 && role == 0) {                             /* eRender, eConsole */
        InterlockedIncrement(&g_device_changes);
        printf("nn::audio: the Windows default output device changed: device notification signalled\n");
        if (g_device_event) os_signal_event(g_device_event);
    }
    return S_OK;
}
static HRESULT STDMETHODCALLTYPE nc_prop(NotifyClient *self, const WCHAR *id, PROPERTYKEY key) { (void)self; (void)id; (void)key; return S_OK; }
static const void *const g_nc_vtbl[] = {nc_query, nc_ref, nc_ref, nc_state, nc_id, nc_id, nc_default, nc_prop};   /* IUnknown, OnDeviceStateChanged, OnDeviceAdded, OnDeviceRemoved, OnDefaultDeviceChanged, OnPropertyValueChanged */
static NotifyClient g_nc = {g_nc_vtbl};
static DWORD WINAPI device_watch_thread(void *arg) {
    ComObj *en = NULL;
    (void)arg;
    CoInitializeEx(NULL, COINIT_MULTITHREADED);
    HRESULT hr = CoCreateInstance(&k_clsid_enumerator, NULL, CLSCTX_ALL, &k_iid_enumerator, (void **)&en);
    if (SUCCEEDED(hr) && en) {
        /* IMMDeviceEnumerator: slot 6 = RegisterEndpointNotificationCallback(IMMNotificationClient *) */
        hr = ((HRESULT (STDMETHODCALLTYPE *)(ComObj *, NotifyClient *))en->vtbl[6])(en, &g_nc);
    }
    if (FAILED(hr)) printf("nn::audio: the Windows device notification is not available (0x%08lx): output device changes are not reported\n", (unsigned long)hr);
    Sleep(INFINITE);                                          /* keeps the apartment and the registration alive */
    return 0;
}
#else
static DWORD WINAPI device_watch_thread(void *arg) { (void)arg; (void)g_device_changes; return 0; }     /* Linux build: device changes are not reported */
#endif
#define AUDIO_DEVICE_NOTIFICATION_ALREADY_ACQUIRED 0x499u
static void audio_AcquireAudioDeviceNotificationForOutput(Ctx *c) {   /* (nn::os::SystemEvent *) -> Result */
    if (InterlockedCompareExchange(&g_device_acquired, 1, 0) != 0) { RET(AUDIO_DEVICE_NOTIFICATION_ALREADY_ACQUIRED); return; }
    os_init_event(A0, 1);
    g_device_event = A0;
    os_signal_event(A0);                                      /* the service's event arrives signalled */
    CloseHandle(CreateThread(NULL, 0, device_watch_thread, NULL, 0, NULL));
    RET(0);
}

static void audio_GetActiveAudioDeviceName(Ctx *c) {  /* (AudioDeviceName *): char[0x100] */
    memset((void *)(uintptr_t)A0, 0, 0x100);
    memcpy((void *)(uintptr_t)A0, g_device_name, sizeof g_device_name);
}

static void audio_SetAudioDeviceOutputVolume(Ctx *c) {   /* (const AudioDeviceName *, float) */
    const char *name = (const char *)(uintptr_t)A0;
    float v = c->v[0].f[0];
    trace_printf("nn::audio: SetAudioDeviceOutputVolume(%s, %g)\n", name, v);
    if (strcmp(name, g_device_name) == 0 && v >= 0.0f && v <= 4.0f) g_volume = v;
}

/* ---------------------------------------------------------------- nn::codec::HardwareOpusDecoder */
#define OPUS_SLOTS 10                                 /* [sdk] _ZTVN2nn5codec19HardwareOpusDecoderE has exactly 10 entries (0x00..0x48) */
#define OPUS_HEADER 8
#define OPUS_MAX_FRAMES 5760                          /* 120 ms at 48 kHz, the longest Opus packet */
#define OBJ_VTABLE 0x00
#define OBJ_STATE 0x08                                /* our decoder state (inside the game's work buffer) */
#define OBJ_RATE 0x10
#define OBJ_CHANNELS 0x14

static uint64_t g_opus_vtable[OPUS_SLOTS];
static char g_opus_names[OPUS_SLOTS][48];
static unsigned char g_opus_seen[OPUS_SLOTS];
static HMODULE g_opus_dll;
static int g_opus_tried;
static int (*p_opus_decoder_get_size)(int channels);
static int (*p_opus_decoder_init)(void *st, int rate, int channels);
static int (*p_opus_decode)(void *st, const unsigned char *data, int len, int16_t *pcm, int frame_size, int fec);
static volatile LONG64 g_opus_packets, g_opus_errors, g_opus_frames;

static void opus_load(void) {
    if (g_opus_tried) return;
    g_opus_tried = 1;
    const char *env = getenv("SSBU_OPUS_DLL");
#ifdef _WIN32
    const char *const tries[] = { env, "libopus-0.dll", "opus.dll", "C:\\msys64\\ucrt64\\bin\\libopus-0.dll", "C:\\msys64\\mingw64\\bin\\libopus-0.dll", "C:\\msys64\\clang64\\bin\\libopus-0.dll" };
#else
    const char *const tries[] = { env, "libopus-0.dll" };      /* plat_posix.c maps it to libopus.so.0 */
#endif
    const char *used = NULL;
    for (unsigned i = 0; i < sizeof tries / sizeof tries[0] && !g_opus_dll; i++) {
        if (!tries[i]) continue;
        g_opus_dll = LoadLibraryExA(tries[i], NULL, strchr(tries[i], '\\') ? LOAD_WITH_ALTERED_SEARCH_PATH : 0);
        used = tries[i];
    }
    if (g_opus_dll) {
        p_opus_decoder_get_size = (int (*)(int))GetProcAddress(g_opus_dll, "opus_decoder_get_size");
        p_opus_decoder_init = (int (*)(void *, int, int))GetProcAddress(g_opus_dll, "opus_decoder_init");
        p_opus_decode = (int (*)(void *, const unsigned char *, int, int16_t *, int, int))GetProcAddress(g_opus_dll, "opus_decode");
        if (!p_opus_decoder_get_size || !p_opus_decoder_init || !p_opus_decode) g_opus_dll = NULL;
    }
    printf("nn::codec: libopus %s%s\n", g_opus_dll ? "loaded from " : "NOT FOUND: Opus streams will be silent (set SSBU_OPUS_DLL)", g_opus_dll ? used : "");
}

static uint32_t be32(uint64_t a) { uint32_t v = rd32(a); return (v >> 24) | ((v >> 8) & 0xff00) | ((v << 8) & 0xff0000) | (v << 24); }

static void opus_destructor(Ctx *c) { wr64(A0 + OBJ_STATE, 0); }

static void opus_GetWorkBufferSize(Ctx *c) {          /* (this, int sampleRate, int channelCount) -> size_t */
    opus_load();
    int channels = (int)A2 == 1 ? 1 : 2;
    size_t size = g_opus_dll ? (size_t)p_opus_decoder_get_size(channels) : 0;
    RET((size + 0x1fff) & ~(size_t)0xfff);
}

static void opus_Initialize(Ctx *c) {                 /* (this, int sampleRate, int channelCount, void *buffer, size_t size) -> 0 ok */
    uint64_t self = A0, buffer = A3;
    int rate = (int)A1, channels = (int)A2, ok = 0;
    opus_load();
    wr32(self + OBJ_RATE, (uint32_t)rate);
    wr32(self + OBJ_CHANNELS, (uint32_t)channels);
    wr64(self + OBJ_STATE, 0);
    if (g_opus_dll && buffer && (channels == 1 || channels == 2) && (size_t)p_opus_decoder_get_size(channels) <= A4) {
        ok = p_opus_decoder_init((void *)(uintptr_t)buffer, rate, channels) == 0;
        if (ok) wr64(self + OBJ_STATE, buffer);
    }
    printf("nn::codec: HardwareOpusDecoder::Initialize(%d Hz, %d channels, work buffer %llu bytes): %s\n", rate, channels,
           (unsigned long long)A4, ok ? "libopus decoder ready" : "no decoder, output will be silence");
    RET(0);
}

static void opus_Finalize(Ctx *c) { wr64(A0 + OBJ_STATE, 0); wr32(A0 + OBJ_RATE, 0); wr32(A0 + OBJ_CHANNELS, 0); }

static void opus_DecodeInterleaved(Ctx *c) {          /* (this, size_t *consumed, int *sampleCount, int16_t *out, size_t outBytes, const void *in, size_t inBytes) */
    uint64_t self = A0, in = A5, in_size = A6;
    int16_t *out = (int16_t *)(uintptr_t)A3;
    int channels = (int)rd32(self + OBJ_CHANNELS), rate = (int)rd32(self + OBJ_RATE);
    if (channels != 1) channels = 2;
    int room = (int)(A4 / (2u * (unsigned)channels));  /* frames that fit in the output */
    if (in_size < OPUS_HEADER) { InterlockedIncrement64(&g_opus_errors); RET(6); return; }      /* any non-zero value: the game only tests for 0 */
    uint32_t len = be32(in);
    if ((uint64_t)len + OPUS_HEADER > in_size) { InterlockedIncrement64(&g_opus_errors); RET(6); return; }
    void *st = (void *)(uintptr_t)rd64(self + OBJ_STATE);
    int frames;
    if (st) {
        { void r1_nosim(uint64_t, uint64_t); r1_nosim((uint64_t)(uintptr_t)out, A4); r1_nosim((uint64_t)(uintptr_t)st, (uint64_t)p_opus_decoder_get_size(channels)); }   /* R1 (r1_state.c): decoded sound and the decoder's state (libopus writes it in the game's work buffer, round 5) are not simulation state (nothing without SSBU_R1_MARK) */
        frames = p_opus_decode(st, (const unsigned char *)(uintptr_t)(in + OPUS_HEADER), (int)len, out, room > OPUS_MAX_FRAMES ? OPUS_MAX_FRAMES : room, 0);
        if (frames < 0) {
            if (InterlockedIncrement64(&g_opus_errors) <= 5) printf("nn::codec: opus_decode error %d (packet of %u bytes, input %llu bytes)\n", frames, len, (unsigned long long)in_size);
            RET(6);
            return;
        }
    } else {
        frames = rate / 50;                           /* a 20 ms packet of silence */
        if (frames > room) frames = room;
        memset(out, 0, (size_t)frames * 2 * (unsigned)channels);
    }
    wr64(A1, (uint64_t)len + OPUS_HEADER);
    wr32(A2, (uint32_t)frames);
    InterlockedAdd64(&g_opus_frames, frames);
    LONG64 n = InterlockedIncrement64(&g_opus_packets);
    if (n == 1 || n % 5000 == 0)
        printf("nn::codec: %lld Opus packets decoded (%lld frames, %lld errors); last: %u bytes -> %d frames\n",
               (long long)n, (long long)g_opus_frames, (long long)g_opus_errors, len, frames);
    RET(0);
}

/* The four remaining virtual functions of the real class ([sdk] vtable: +0x18 IsInitialized, +0x30 GetSampleRate,
 * +0x38 GetChannelCount, +0x40 Reset) and the deleting destructor (+0x08). */
static void opus_IsInitialized(Ctx *c) { RET(rd32(A0 + OBJ_RATE) != 0); }       /* Initialize stores the rate, Finalize clears it */
static void opus_GetSampleRate(Ctx *c) { RET(rd32(A0 + OBJ_RATE)); }
static void opus_GetChannelCount(Ctx *c) { RET(rd32(A0 + OBJ_CHANNELS)); }
static void opus_Reset(Ctx *c) {                      /* back to the state right after Initialize: the decoder's history is dropped */
    void *st = (void *)(uintptr_t)rd64(A0 + OBJ_STATE);
    int channels = (int)rd32(A0 + OBJ_CHANNELS) == 1 ? 1 : 2;
    if (st && p_opus_decoder_init) p_opus_decoder_init(st, (int)rd32(A0 + OBJ_RATE), channels);
}
static void opus_deleting_destructor(Ctx *c) {        /* ~HardwareOpusDecoder() then operator delete(this): the game's own operator delete */
    uint64_t self = A0, del = 0;
    wr64(self + OBJ_STATE, 0);
    for (int i = 0; i < dyn_sym_count && !del; i++)
        if (dyn_syms[i].defined && strcmp(dyn_syms[i].name, "_ZdlPv") == 0) del = GUEST_BASE + dyn_syms[i].value;
    if (!del) guest_trap("HardwareOpusDecoder deleting destructor: the game's operator delete was not found", c->x[30] - 4);
    c->x[0] = self;
    call_guest(c, del);
}
static void opus_unknown(Ctx *c) {                    /* a virtual function the game was not seen to call */
    const char *name = hostfn_current_name();
    for (int i = 0; i < OPUS_SLOTS; i++)
        if (name == g_opus_names[i] && !g_opus_seen[i]) {
            g_opus_seen[i] = 1;
            printf("nn::codec: %s called (x1=%llx x2=%llx x3=%llx) -> 0\n", name, (unsigned long long)A1, (unsigned long long)A2, (unsigned long long)A3);
        }
    RET(0);
}

static void opus_constructor(Ctx *c) {                /* HardwareOpusDecoder(int option) */
    EnterCriticalSection(&g_lock);
    ar_scope_enter();
    if (!g_opus_vtable[0]) {
        for (int i = 0; i < OPUS_SLOTS; i++) {
            ImportFn fn = opus_unknown;
            const char *what = NULL;
            switch (i * 8) {
            case 0x00: fn = opus_destructor; what = "destructor"; break;
            case 0x08: fn = opus_deleting_destructor; what = "deleting destructor"; break;
            case 0x18: fn = opus_IsInitialized; what = "IsInitialized"; break;
            case 0x30: fn = opus_GetSampleRate; what = "GetSampleRate"; break;
            case 0x38: fn = opus_GetChannelCount; what = "GetChannelCount"; break;
            case 0x40: fn = opus_Reset; what = "Reset"; break;
            case 0x10: fn = opus_GetWorkBufferSize; what = "GetWorkBufferSize"; break;
            case 0x20: fn = opus_Initialize; what = "Initialize"; break;
            case 0x28: fn = opus_Finalize; what = "Finalize"; break;
            case 0x48: fn = opus_DecodeInterleaved; what = "DecodeInterleaved"; break;
            }
            if (what) snprintf(g_opus_names[i], sizeof g_opus_names[i], "HardwareOpusDecoder::%s", what);
            else snprintf(g_opus_names[i], sizeof g_opus_names[i], "HardwareOpusDecoder vtable+0x%x", i * 8);
            g_opus_vtable[i] = hostfn_address(g_opus_names[i], fn);
        }
    }
    ar_scope_leave();
    LeaveCriticalSection(&g_lock);
    wr64(A0 + OBJ_VTABLE, (uint64_t)(uintptr_t)g_opus_vtable);
    wr64(A0 + OBJ_STATE, 0);
    wr64(A0 + OBJ_RATE, 0);
}

/* ---------------------------------------------------------------- registration */
#define AU(n) "_ZN2nn5audio" n
static const ImportDef audio_imports[] = {
    {AU("27InitializeAudioOutParameterEPNS0_17AudioOutParameterE"), audio_InitializeAudioOutParameter},
    {AU("19OpenDefaultAudioOutEPNS0_8AudioOutEPNS_2os11SystemEventERKNS0_17AudioOutParameterE"), audio_OpenDefaultAudioOut},
    {AU("23GetAudioOutChannelCountEPKNS0_8AudioOutE"), audio_GetAudioOutChannelCount},
    {AU("21GetAudioOutSampleRateEPKNS0_8AudioOutE"), audio_GetAudioOutSampleRate},
    {AU("23GetAudioOutSampleFormatEPKNS0_8AudioOutE"), audio_GetAudioOutSampleFormat},
    {AU("21SetAudioOutBufferInfoEPNS0_14AudioOutBufferEPvmm"), audio_SetAudioOutBufferInfo},
    {AU("28GetAudioOutBufferDataPointerEPKNS0_14AudioOutBufferE"), audio_GetAudioOutBufferDataPointer},
    {AU("20AppendAudioOutBufferEPNS0_8AudioOutEPNS0_14AudioOutBufferE"), audio_AppendAudioOutBuffer},
    {AU("13StartAudioOutEPNS0_8AudioOutE"), audio_StartAudioOut},
    {AU("25GetReleasedAudioOutBufferEPNS0_8AudioOutE"), audio_GetReleasedAudioOutBuffer},
    {AU("12StopAudioOutEPNS0_8AudioOutE"), audio_StopAudioOut},
    {AU("13CloseAudioOutEPNS0_8AudioOutE"), audio_CloseAudioOut},
    {AU("39AcquireAudioDeviceNotificationForOutputEPNS_2os11SystemEventE"), audio_AcquireAudioDeviceNotificationForOutput},
    {AU("24GetActiveAudioDeviceNameEPNS0_15AudioDeviceNameE"), audio_GetActiveAudioDeviceName},
    {AU("26SetAudioDeviceOutputVolumeEPKNS0_15AudioDeviceNameEf"), audio_SetAudioDeviceOutputVolume},
    {"_ZN2nn5codec19HardwareOpusDecoderC1Ei", opus_constructor},
};

void register_audio_imports(void) {
#ifndef _WIN32
    const char *ar_mode=getenv("SSBU_RB_AUDIO_RELEASE_QUEUE");
    if(ar_mode && strcmp(ar_mode,"0")){fprintf(stderr,"audio release observer requires Windows/offline admitted AP fixture\n");exit(1);}
#endif
    InitializeCriticalSection(&g_lock);
    InterlockedExchange(&g_ar_lock_ready,1);
    QueryPerformanceFrequency(&g_freq);
    g_wake = CreateEventA(NULL, FALSE, FALSE, NULL);
    CreateThread(NULL, 0, audio_thread, NULL, 0, NULL);
    register_imports(audio_imports, (int)(sizeof audio_imports / sizeof audio_imports[0]));
}

/* U1, the settings menu (menu.cpp): the host output volume (the game's whole mix; music and effects apart are the game's
 * own Options > Sound). -1 = no output device yet. */
int nnaudio_volume(void) { return g_wave ? g_host_percent : -1; }
void nnaudio_set_volume(int percent) {
    if (percent < 0) percent = 0;
    if (percent > 100) percent = 100;
    if (!g_wave) return;
    DWORD level = (DWORD)(0xffff * percent / 100);
    waveOutSetVolume(g_wave, level | level << 16);
    g_host_percent = percent;
    printf("nn::audio: host volume %d%% (settings menu)\n", percent);
}
