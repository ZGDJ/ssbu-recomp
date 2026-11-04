/* Included once after replay_queue_probe.h in r1_ring.c. Never snapshotted.
 * Ownership is a single nonblocking CAS; unexpected concurrent observation
 * loses coverage with a sticky error rather than serializing guest workers. */
#include <stddef.h>
#include <limits.h>
#define AP_CAP 512
#define AP_INTERIOR 496
#define AP_TICKETS 8
enum { AP_IDENTITY=1, AP_OVERLAP=2, AP_STALE=4, AP_CHAIN=8, AP_FRAME=16,
       AP_READ=32, AP_CAPACITY=64, AP_UNREADY=128, AP_BINDING=256,
       AP_BOUNDARY=512, AP_POST_SEAL=1024, AP_PENDING=2048, AP_WRAP=4096 };
enum { AP_AWAIT_PREFIX,AP_OPEN_POSITIVE,AP_OPEN_PARTIAL,AP_AFTER_END,AP_GAP,AP_SEALED };
enum { AP_INTERVAL_BEGIN=1,AP_INTERVAL_END,AP_GAP_BEGIN,AP_LOAD_READY,
       AP_REGION_BEGIN,AP_REGION_RESUME,AP_PRODUCER_RETURN,AP_AUDIO_ENTER,
       AP_AUDIO_BIND,AP_AUDIO_RETURN,AP_REGION_END,AP_REGION_PARTIAL,AP_ERROR,
       AP_IMPORT_ENTER,AP_IMPORT_BIND,AP_IMPORT_RETURN,AP_PRODUCER_ENTER };
enum { AP_PREFIX_UNKNOWN=1,AP_BEFORE_WINDOW=2,AP_SUFFIX_HELD=4,AP_RESTORED_UNKNOWN=8 };
/* Wire v1: 36 little-endian uint64 fields, Ctx[848], AudioBinding[320],
 * metadata_status u64 and bounded import_name[96].
 * All records are zeroed before filling; includes all Ctx bytes, ex_val2 too. */
typedef struct {
    uint64_t id,kind,stage,epoch,generation,actor,ctx,region,coverage,state;
    uint64_t lr,sp,fp,body_sp,parent_fp,buffer,target,context,qp_token;
    uint64_t arm_ordinal,region_ordinal,previous_return,latest_return,attempts,returns;
    uint64_t edge,entered,returned,ticket,purpose,ctx_valid,read_mask,saved_fp,saved_lr;
    uint64_t errors,pending;
    Ctx full;
    AudioBinding binding;
    uint64_t metadata_status; /* 0 NULL, 1 bounded complete name, 2 unresolved */
    unsigned char import_name[96];
} ApRecord;
typedef struct { volatile LONG ready; ApRecord r; } ApEvent;
typedef struct {
    uint64_t id,epoch,generation,region,sp,fp,lr,sym,edge,purpose,binds;
    DWORD actor; const Ctx *ctx;
    Ctx entry_ctx,bind_ctx;
    AudioBinding binding;
    uint64_t end_event,enter_event,bind_event;
} ApTicket;
typedef struct {
    uint64_t id,body_sp,fp,buffer,coverage,attempts,returns,first_qp,last_qp,latest_return;
    unsigned entered,returned; int state,buffer_known;
    uint64_t end_event;
} ApRegion;
static ApEvent g_ap_events[AP_CAP];
static ApTicket g_ap_tickets[AP_TICKETS];
static ApRegion g_ap_region;
static volatile LONG g_ap_on,g_ap_owner,g_ap_errors;
static uint64_t g_ap_epoch=1,g_ap_generation,g_ap_id,g_ap_ticket_id,g_ap_region_id;
static uint64_t g_ap_count,g_ap_interior,g_ap_boundary_count,g_ap_drops,g_ap_gap_activity;
static uint64_t g_ap_arm_ordinal,g_ap_producer,g_ap_complete,g_ap_partial;
static uint64_t g_ap_transitions,g_ap_peak_tickets,g_ap_pending_seal;
static uint64_t g_ap_pending_category[4];
static LONG g_ap_stage;
static DWORD g_ap_actor; static const Ctx *g_ap_ctx;
static int g_ap_reported;
static LONG g_ap_reported_errors;
static LONG g_ap_enveloped_errors;
_Static_assert(sizeof(Ctx)==848 && offsetof(Ctx,v)==256 && offsetof(Ctx,N)==768 &&
    offsetof(Ctx,tpidr)==784 && offsetof(Ctx,ex_addr)==792 && offsetof(Ctx,ex_val)==800 &&
    offsetof(Ctx,ex_fail)==808 && offsetof(Ctx,fn)==816 && offsetof(Ctx,in_import)==824 &&
    offsetof(Ctx,import_from)==832 && offsetof(Ctx,ex_val2)==840,"Ctx wire v1 changed");
_Static_assert(sizeof(AudioBinding)==320 && sizeof(ApRecord)==1560,"audio wire v1 changed");
_Static_assert(sizeof(ApEvent)<=2048,"audio event exceeds diagnostic bound");
static void ap_fail(LONG e) { InterlockedOr(&g_ap_errors,e); }
static uint64_t ap_next(uint64_t *n) {
    if(*n==UINT64_MAX) { ap_fail(AP_WRAP);return 0; } return ++*n;
}
static int ap_lock(void) {
    if(!qp_read(&g_ap_on))return 0;
    if(InterlockedCompareExchange(&g_ap_owner,1,0)) { ap_fail(AP_OVERLAP);return 0; }
    return 1;
}
static void ap_unlock(void) { InterlockedExchange(&g_ap_owner,0); }
static int ap_recording(void) { return g_ap_stage==1 || g_ap_stage==3; }
static int ap_open(void) { return g_ap_region.state==AP_OPEN_POSITIVE || g_ap_region.state==AP_OPEN_PARTIAL; }
static uint64_t ap_pending(void) {
    uint64_t p=ap_open()?1:0;
    if(g_ap_producer)p|=2;
    for(int i=0;i<AP_TICKETS;i++)if(g_ap_tickets[i].id)p|=g_ap_tickets[i].purpose?8:4;
    return p;
}
static int ap_actor(const Ctx *c) {
    DWORD a=GetCurrentThreadId();
    /* Adopt already-discovered QP identity, including before frame 118. */
    DWORD qa=(DWORD)qp_read(&g_qp_producer.actor);
    if((qa && (qa!=a || (g_qp_producer.ctx && g_qp_producer.ctx!=c))) ||
       (g_ap_actor && (g_ap_actor!=a || g_ap_ctx!=c))) { ap_fail(AP_IDENTITY);return 0; }
    g_ap_actor=a;g_ap_ctx=c;return 1;
}
static ApRecord *ap_event(unsigned kind,const Ctx *c,int boundary) {
    if(!boundary && !ap_recording())return NULL;
    if(g_ap_stage==4 && !boundary) { ap_fail(AP_POST_SEAL);return NULL; }
    if(g_ap_count>=AP_CAP || (boundary?g_ap_boundary_count>=16:g_ap_interior>=AP_INTERIOR)) {
        ap_fail(AP_CAPACITY);ap_next(&g_ap_drops);return NULL;
    }
    uint64_t id=ap_next(&g_ap_id);if(!id)return NULL;
    ApEvent *e=&g_ap_events[g_ap_count++];memset(&e->r,0,sizeof e->r);
    if(boundary)g_ap_boundary_count++;else g_ap_interior++;
    ApRecord *r=&e->r;
    r->id=id;r->kind=kind;r->stage=g_ap_stage;r->epoch=g_ap_epoch;r->generation=g_ap_generation;
    r->actor=g_ap_actor;r->ctx=(uint64_t)(uintptr_t)c;r->region=g_ap_region.id;
    r->coverage=g_ap_region.coverage;r->state=g_ap_region.state;
    r->body_sp=g_ap_region.body_sp;r->parent_fp=g_ap_region.fp;r->buffer=g_ap_region.buffer;
    r->arm_ordinal=g_ap_arm_ordinal;r->region_ordinal=g_ap_region.attempts;
    r->latest_return=g_ap_region.latest_return;r->attempts=g_ap_region.attempts;r->returns=g_ap_region.returns;
    r->entered=g_ap_region.entered;r->returned=g_ap_region.returned;
    r->errors=(unsigned)qp_read(&g_ap_errors);r->pending=ap_pending();
    if(c) { memcpy(&r->full,c,sizeof *c);r->ctx_valid=1;r->lr=c->x[30];r->sp=c->x[31];
        r->fp=c->x[29];r->context=c->x[0];
        if(c->in_import) {
            SIZE_T got=0;r->metadata_status=2;
            if(ReadProcessMemory(GetCurrentProcess(),c->in_import,r->import_name,sizeof r->import_name,&got) &&
               got==sizeof r->import_name) {
                unsigned char *end=memchr(r->import_name,0,sizeof r->import_name);
                if(end){r->metadata_status=1;memset(end,0,sizeof r->import_name-(size_t)(end-r->import_name));}
                else ap_fail(AP_BINDING);
            } else ap_fail(AP_READ);
        }
    }
    return r;
}
static void ap_publish(ApRecord *r) {
    if(r) { ApEvent *e=(ApEvent *)((unsigned char *)r - offsetof(ApEvent,r));InterlockedExchange(&e->ready,1); }
}
static void ap_simple(unsigned kind,const Ctx *c,int boundary) { ap_publish(ap_event(kind,c,boundary)); }
static int ap_body(uint64_t sp,uint64_t fp) {
    if(sp>UINT64_MAX-2336 || fp!=sp+2336) { ap_fail(AP_FRAME);return 0; }
    return 1;
}
static int ap_member(const Ctx *c,uint64_t sp,uint64_t fp) {
    if(!ap_actor(c) || !ap_body(sp,fp))return 0;
    if(!ap_open()) {
        if(g_ap_region.state!=AP_AWAIT_PREFIX) { ap_fail(AP_BOUNDARY);return 0; }
        memset(&g_ap_region,0,sizeof g_ap_region);g_ap_region.id=ap_next(&g_ap_region_id);
        if(!g_ap_region.id)return 0;
        g_ap_region.state=AP_OPEN_PARTIAL;
        g_ap_region.coverage=AP_PREFIX_UNKNOWN|(g_ap_stage==3?AP_RESTORED_UNKNOWN:0);
        g_ap_region.body_sp=sp;g_ap_region.fp=fp;
        ap_simple(AP_REGION_PARTIAL,c,0);
    }
    if(g_ap_region.body_sp!=sp || g_ap_region.fp!=fp) { ap_fail(AP_FRAME);return 0; }
    return 1;
}
static ApTicket *ap_ticket(AudioTicket id,const Ctx *c,unsigned purpose) {
    for(int i=0;i<AP_TICKETS;i++) {
        ApTicket *t=&g_ap_tickets[i];
        if(t->id!=id)continue;
        if(t->epoch!=g_ap_epoch || t->generation!=g_ap_generation || t->purpose!=purpose ||
           t->ctx!=c || t->actor!=GetCurrentThreadId()) { ap_fail(AP_STALE);return NULL; }
        return t;
    }
    ap_fail(g_ap_stage==4?AP_POST_SEAL:AP_STALE);return NULL;
}
static ApTicket *ap_mint(const Ctx *c,unsigned purpose) {
    int used=0,slot=-1;
    for(int i=0;i<AP_TICKETS;i++)if(g_ap_tickets[i].id)used++;else if(slot<0)slot=i;
    if(slot<0) { ap_fail(AP_CAPACITY);return NULL; }
    uint64_t id=ap_next(&g_ap_ticket_id);if(!id)return NULL;
    if((uint64_t)(used+1)>g_ap_peak_tickets)g_ap_peak_tickets=used+1;
    ApTicket *t=&g_ap_tickets[slot];memset(t,0,sizeof *t);
    t->id=id;t->epoch=g_ap_epoch;t->generation=g_ap_generation;t->region=g_ap_region.id;
    t->ctx=c;t->actor=GetCurrentThreadId();t->sp=c->x[31];t->fp=c->x[29];t->lr=c->x[30];t->purpose=purpose;
    memcpy(&t->entry_ctx,c,sizeof *c);
    return t;
}
static uint64_t ap_ticket_event(unsigned kind,const Ctx *c,ApTicket *t) {
    ApRecord *r=ap_event(kind,c,0);
    if(r){r->ticket=t->id;r->purpose=t->purpose;r->edge=t->edge;r->target=t->sym;r->region=t->region;}
    ap_publish(r);
    return r?r->id:0;
}
static uint64_t ap_digest(uint64_t,const char *,size_t);
#include "replay_audio_postload.h"
static int ap_live(void) {
    if(g_ap_stage==2){ap_next(&g_ap_gap_activity);return 0;}
    /* Normal later execution is outside this bounded window. Only an attempted
     * publication with an old nonzero ticket is a post-seal error. */
    if(g_ap_stage==4)return 0;return 1;
}
static AudioTicket ap_import_enter(const Ctx *c,int sym) {
    unsigned purpose=(sym==1884 && c->x[30]==0x7103987f94ULL)?1:
                     (sym==1887 && c->x[30]==0x710398b68cULL)?2:0;
    if(!purpose || !ap_live() || !ap_actor(c))return 0;
    al_conflict(); /* A new source operation cannot overwrite a missed seam. */
    /* Import thunks forward Ctx unchanged; fn names the last lifted entry, not this checkpoint. */
    if(!ap_body(c->x[31],c->x[29])) {
        ap_fail(AP_FRAME);return 0;
    }
    if(purpose==1 && ap_open()) { ap_fail(AP_OVERLAP);return 0; }
    if(purpose==2) {
        if(!ap_member(c,c->x[31],c->x[29]))return 0;
        if(!c->x[0]) { ap_fail(AP_IDENTITY);return 0; }
        if(g_ap_producer || (ap_pending()&12)) { ap_fail(AP_PENDING);return 0; }
        if(g_ap_region.buffer_known && g_ap_region.buffer!=c->x[0]) { ap_fail(AP_IDENTITY);return 0; }
        g_ap_region.buffer=c->x[0];g_ap_region.buffer_known=1;
        ApRecord *end=ap_event(AP_REGION_END,c,0);ap_publish(end);
        g_ap_region.end_event=end?end->id:0;
        if(ap_recording()) { if(g_ap_region.coverage)ap_next(&g_ap_partial);else ap_next(&g_ap_complete); }
        g_ap_region.state=AP_AFTER_END;
    } else if(ap_pending()&12) { ap_fail(AP_OVERLAP);return 0; }
    ApTicket *t=ap_mint(c,purpose);if(!t)return 0;
    t->sym=sym;t->end_event=g_ap_region.end_event;
    t->enter_event=ap_ticket_event(AP_IMPORT_ENTER,c,t);return t->id;
}
static void ap_import_return(const Ctx *c,int sym,AudioTicket id) {
    ApTicket *t=ap_ticket(id,c,sym==1884?1:2);if(!t)return;
    if(t->sym!=(uint64_t)sym || t->sp!=c->x[31] || t->fp!=c->x[29]) { ap_fail(AP_FRAME);return; }
    if(t->binds!=1)ap_fail(AP_BINDING);
    uint64_t return_event=ap_ticket_event(AP_IMPORT_RETURN,c,t);
    if(t->purpose==2)al_origin(c,t,return_event); /* exact ticket still live under CAS */
    unsigned purpose=(unsigned)t->purpose;t->id=0;
    if(purpose==1 && c->x[0]) {
        memset(&g_al_tombstone,0,sizeof g_al_tombstone);
        if(ap_open()) { ap_fail(AP_OVERLAP);return; }
        memset(&g_ap_region,0,sizeof g_ap_region);g_ap_region.id=ap_next(&g_ap_region_id);
        g_ap_region.state=AP_OPEN_POSITIVE;g_ap_region.body_sp=c->x[31];g_ap_region.fp=c->x[29];
        g_ap_region.buffer=c->x[0];g_ap_region.buffer_known=1;
        ap_simple(AP_REGION_BEGIN,c,0);
    }
}
static void ap_producer_enter(const Ctx *c,long token,int stage) {
    DWORD error=GetLastError();
    if(!ap_lock()) { SetLastError(error);return; }
    if(ap_recording()) {
        al_conflict();
        if(stage!=g_ap_stage || token<=0 || g_ap_producer || (ap_pending()&4) || g_ap_region.entered)ap_fail(AP_CHAIN);
        else if(c->x[30]!=0x710398b444ULL || !ap_member(c,c->x[31],c->x[29]))ap_fail(AP_FRAME);
        else {
            g_ap_producer=(uint64_t)token;
            ap_next(&g_ap_arm_ordinal);ap_next(&g_ap_region.attempts);
            if(!g_ap_region.first_qp)g_ap_region.first_qp=token;g_ap_region.last_qp=token;
            ApRecord *r=ap_event(AP_PRODUCER_ENTER,c,0);
            if(r){r->qp_token=token;r->previous_return=g_ap_region.latest_return;}ap_publish(r);
        }
    } else if(stage==2)ap_next(&g_ap_gap_activity);
    else if(stage==4)ap_fail(AP_POST_SEAL);
    ap_unlock();SetLastError(error);
}
void r1_audio_producer_return(const Ctx *c,long token,int accepted) {
    DWORD error=GetLastError();if(!ap_lock()){SetLastError(error);return;}
    if(ap_recording()) {
        if(g_ap_producer!=(uint64_t)token || !g_ap_producer || !ap_actor(c) ||
           c->x[31]!=g_ap_region.body_sp || c->x[29]!=g_ap_region.fp)ap_fail(AP_CHAIN);
        else {
            ap_next(&g_ap_region.returns);
            ApRecord *r=ap_event(AP_PRODUCER_RETURN,c,0);
            if(r){r->qp_token=token;r->purpose=accepted?1:0;r->previous_return=g_ap_region.latest_return;
                g_ap_region.latest_return=r->id;}
            ap_publish(r);g_ap_producer=0;
        }
    } else if(g_ap_stage==2)ap_next(&g_ap_gap_activity);
    else if(g_ap_stage==4)ap_fail(AP_POST_SEAL);
    ap_unlock();SetLastError(error);
}
static AudioTicket ap_indirect_enter(const Ctx *c,uint64_t addr) {
    unsigned edge=c->x[30]==0x7103964ba0ULL?1:c->x[30]==0x7103964de0ULL?2:0;
    if(!edge || !ap_recording()) { if(edge && g_ap_stage>=2)ap_live();return 0; }
    al_conflict();
    uint64_t sp=c->x[31],body,fp,saved[2]={0};SIZE_T got=0;
    if(sp>UINT64_MAX-48 || sp+48>UINT64_MAX-2336) { ap_fail(AP_FRAME);return 0; }
    body=sp+48;fp=body+2336;
    if(!ReadProcessMemory(GetCurrentProcess(),(void *)(uintptr_t)(sp+32),saved,sizeof saved,&got) || got!=sizeof saved) {
        ap_fail(AP_READ);return 0;
    }
    if(c->fn!=(edge==1?0x7103964b70ULL:0x7103964db0ULL) || c->x[29]!=body-16 ||
       c->x[8]!=addr || saved[0]!=fp || saved[1]!=(edge==1?0x710398b4b4ULL:0x710398b61cULL)) {
        ap_fail(AP_FRAME);return 0;
    }
    if(!ap_member(c,body,fp))return 0;
    if(g_ap_producer || (ap_pending()&12) || (g_ap_region.entered&edge) ||
       (edge==1 && g_ap_region.entered)) { ap_fail(AP_OVERLAP);return 0; }
    ApTicket *t=ap_mint(c,0);if(!t)return 0;t->edge=edge;t->sym=addr;
    g_ap_region.entered|=edge;
    ApRecord *r=ap_event(AP_AUDIO_ENTER,c,0);
    if(r){r->ticket=t->id;r->edge=edge;r->target=addr;r->read_mask=3;r->saved_fp=saved[0];r->saved_lr=saved[1];}
    ap_publish(r);return t->id;
}
static void ap_indirect_return(const Ctx *c,AudioTicket id) {
    ApTicket *t=ap_ticket(id,c,0);if(!t)return;
    if(t->region!=g_ap_region.id || !ap_open() || c->x[31]!=t->sp || c->x[29]!=t->fp) { ap_fail(AP_FRAME);return; }
    if(t->binds!=1)ap_fail(AP_BINDING);
    g_ap_region.returned|=(unsigned)t->edge;ap_ticket_event(AP_AUDIO_RETURN,c,t);t->id=0;
}
/* Public wrappers do not dereference anything or read actor identity off-mode. */
AudioTicket r1_audio_import_enter(const Ctx *c,int sym) {
    if(!qp_read(&g_ap_on))return 0;
    if(!((sym==1884 && c->x[30]==0x7103987f94ULL) ||
         (sym==1887 && c->x[30]==0x710398b68cULL)))return 0;
    DWORD e=GetLastError();AudioTicket id=0;if(ap_lock()){id=ap_import_enter(c,sym);ap_unlock();}SetLastError(e);return id;
}
void r1_audio_import_return(const Ctx *c,int sym,AudioTicket id) {
    if(!id || !qp_read(&g_ap_on))return;
    DWORD e=GetLastError();audio_release_probe_late(id);if(ap_lock()){ap_import_return(c,sym,id);ap_unlock();}SetLastError(e);
}
AudioTicket r1_audio_indirect_enter(const Ctx *c,uint64_t addr) {
    if(!qp_read(&g_ap_on))return 0;
    if(c->x[30]!=0x7103964ba0ULL && c->x[30]!=0x7103964de0ULL)return 0;
    DWORD e=GetLastError();AudioTicket id=0;if(ap_lock()){id=ap_indirect_enter(c,addr);ap_unlock();}SetLastError(e);return id;
}
void r1_audio_indirect_return(const Ctx *c,AudioTicket id) {
    if(!id || !qp_read(&g_ap_on))return;
    DWORD e=GetLastError();if(ap_lock()){ap_indirect_return(c,id);ap_unlock();}SetLastError(e);
}
void r1_audio_binding(const Ctx *c,AudioTicket id,const AudioBinding *b) {
    if(!id || !qp_read(&g_ap_on))return;
    DWORD error=GetLastError();if(ap_lock()) {
        ApTicket *t=NULL;
        for(int i=0;i<AP_TICKETS;i++)if(g_ap_tickets[i].id==id)t=ap_ticket(id,c,(unsigned)g_ap_tickets[i].purpose);
        if(!t)ap_fail(AP_STALE);
        else if(t->binds++)ap_fail(AP_BINDING);
        else {
            t->binding=*b;memcpy(&t->bind_ctx,c,sizeof *c);
            ApRecord *r=ap_event(t->purpose?AP_IMPORT_BIND:AP_AUDIO_BIND,c,0);
            if(r){r->ticket=id;r->purpose=t->purpose;r->edge=t->edge;r->target=t->sym;r->region=t->region;r->binding=*b;
                if(!t->purpose && b->family==AB_IMPORT) {
                    r->binding.guest=t->sym;r->binding.offset=(t->sym-IMPORT_BASE)%IMPORT_SLOT;
                }
            }
            ap_publish(r);
            t->bind_event=r?r->id:0;
            /* Unresolved bindings are retained, analyzer stops semantic claims. */
            if(b->status!=AB_RAW || !b->fn)ap_fail(AP_BINDING);
        }
        ap_unlock();
    }SetLastError(error);
}
void r1_audio_selected(const Ctx *c,AudioTicket id,uint64_t family,uint64_t addr,ImportFn fn,
                       void (*fnu)(Ctx *,void *),void *user,uint64_t index,uint64_t offset,const char *name) {
    if(!id || !qp_read(&g_ap_on))return;
    DWORD error=GetLastError();AudioBinding b={0};
    b.family=family;b.status=(fn || fnu)?AB_RAW:AB_MISSING;b.guest=addr;
    b.fn=(uintptr_t)(fnu?(void *)fnu:(void *)fn);b.user=(uintptr_t)user;b.index=index;b.offset=offset;
    audio_binding_name(&b,name);
    if(family==AB_MAIN || family==AB_NRO)hook_audio_binding(&b);
    if(family==AB_IMPORT) { host_audio_import_binding(&b,(int)index);sdk_audio_import_binding(&b,fn); }
    /* Host closures (including HostPrev) are not represented by a plain entry. */
    if(fnu)b.status=AB_HOOK_UNRESOLVED;
    r1_audio_binding(c,id,&b);SetLastError(error);
}
static void ap_archive(unsigned coverage) {
    if(ap_open()) { g_ap_region.coverage|=coverage;ap_simple(AP_REGION_PARTIAL,NULL,1);ap_next(&g_ap_partial); }
}
static void ap_invalidate(void) {
    memset(g_ap_tickets,0,sizeof g_ap_tickets);g_ap_producer=0;
    memset(&g_ap_region,0,sizeof g_ap_region);ap_next(&g_ap_epoch);
}
static void ap_error_held(void) {
    LONG errors=qp_read(&g_ap_errors);
    if(errors && errors!=g_ap_enveloped_errors) {
        /* At most one error summary at each of the three capture endpoints;
         * use the reserved envelope, never recursively log hot failures. */
        ap_simple(AP_ERROR,NULL,1);g_ap_enveloped_errors=errors;
    }
}
/* AUDIO_RELEASE_AP_BEGIN. Accessor runs once before the original audio Enter. */
int r1_audio_release_stamp(const Ctx *c,ImportFn actual,ArStamp *out) {
    if(!audio_release_probe_enabled())return AR_STAMP_DISABLED;
    DWORD error=GetLastError();memset(out,0,sizeof *out);int result=AR_STAMP_INVALID;
    if(!ap_lock()){out->status=result;SetLastError(error);return result;}
    if(g_ap_stage==4)result=AR_STAMP_DISABLED;
    else if(g_ap_stage==2)result=AR_STAMP_GAP;
    else if(c->x[30]!=0x7103987f94ULL)result=AR_STAMP_OTHER_CALL;
    else {
        DWORD actor=GetCurrentThreadId();ApTicket *found=NULL;unsigned matches=0;
        for(unsigned i=0;i<AP_TICKETS;i++) {
            ApTicket *t=&g_ap_tickets[i];
            if(t->id && t->actor==actor && t->ctx==c && t->purpose==1 && t->sym==1884){found=t;matches++;}
        }
        if(matches==1) {
            ApTicket *t=ap_ticket(found->id,c,1);AudioBinding *b=&found->binding;
            if(t && !qp_read(&g_ap_errors) && actor==g_ap_actor && c==g_ap_ctx && t->binds==1 &&
               t->lr==c->x[30] && t->sp==c->x[31] && t->fp==c->x[29] &&
               t->sp<=UINT64_MAX-2336 && t->fp==t->sp+2336 && t->entry_ctx.x[0]==c->x[0] &&
               b->family==AB_IMPORT && b->status==AB_RAW && b->index==1884 && b->offset==0 &&
               b->guest==IMPORT_BASE+1884ULL*IMPORT_SLOT && b->fn==(uintptr_t)(void *)actual &&
               !b->user && !b->hook && !b->repl && !b->hook_user && !b->top && b->registry) {
                out->ticket=t->id;out->epoch=t->epoch;out->generation=t->generation;out->stage=g_ap_stage;
                out->actor=t->actor;out->ctx=(uintptr_t)c;out->lr=t->lr;out->sp=t->sp;out->fp=t->fp;
                out->audio_out=c->x[0];out->fn=b->fn;out->enter_event=t->enter_event;out->bind_event=t->bind_event;
                result=(!g_ap_stage || !t->enter_event || !t->bind_event)?AR_STAMP_PREFIX:AR_STAMP_VALID;
            }
        }
        if(result==AR_STAMP_INVALID)ap_fail(AP_BINDING);
    }
    /* GAP/OTHER have no invented AP token. Retain contextual stage only. */
    if(result!=AR_STAMP_VALID && result!=AR_STAMP_PREFIX) {
        out->stage=g_ap_stage;out->epoch=g_ap_epoch;out->generation=g_ap_generation;
        if(result!=AR_STAMP_DISABLED){out->actor=GetCurrentThreadId();out->ctx=(uintptr_t)c;out->lr=c->x[30];out->audio_out=c->x[0];}
    }
    out->status=result;ap_unlock();SetLastError(error);return result;
}
static void ar_ap_boundary(unsigned slot,long long frame,uint64_t event) {
    if(!audio_release_probe_enabled())return;
    DWORD error=GetLastError();ArBoundaryStamp s={0};s.slot=slot;s.frame=(uint64_t)frame;
    s.event=event;s.transition=g_ap_transitions;s.stage=g_ap_stage;s.epoch=g_ap_epoch;s.generation=g_ap_generation;
    s.actor=GetCurrentThreadId();s.hold=slot==2?AR_DEC_LOAD_MARKER_NOT_QUIET:slot==3?AR_DEC_HELD_LOAD_READY:AR_DEC_HELD_CAPTURE;
    s.valid=event && !qp_read(&g_ap_errors) && !qp_read(&g_qp_errors);
    if(slot!=2) {
        s.valid=s.valid && qp_actor_held((DWORD)qp_read(&g_qp_producer.actor)) &&
            qp_actor_held((DWORD)qp_read(&g_qp_consumer.actor)) &&
            !qp_read(&g_qp_producer.active) && !qp_read(&g_qp_consumer.active) &&
            (!g_ap_actor || qp_actor_held(g_ap_actor));
    }
    audio_release_probe_boundary(&s);SetLastError(error);
}
static int g_ar_exported;static uint64_t g_ar_exported_late,g_ar_exported_errors;
static void ar_ap_drain(uint64_t ap_hash) {
    if(!audio_release_probe_enabled())return;
    DWORD error=GetLastError();ArView v={0};
    if(!audio_release_probe_view(&v)){SetLastError(error);return;}
    if(g_ar_exported) {
        if(v.late_invalid!=g_ar_exported_late || v.errors!=g_ar_exported_errors) {
            LOG("r1: AUDIO_RELEASE_QUEUE_LATE_ERROR v=1 late=%llu errors=%llu resolved=0 authoritative=0\n",
                (unsigned long long)v.late_invalid,(unsigned long long)v.errors);
            g_ar_exported_late=v.late_invalid;
            g_ar_exported_errors=v.errors;
        }
        SetLastError(error);return;
    }
    /* Set before LOG: reentrant drain cannot publish a second envelope. */
    g_ar_exported=1;g_ar_exported_late=v.late_invalid;g_ar_exported_errors=v.errors;
    LOG("r1: AUDIO_RELEASE_QUEUE_BEGIN v=1 layout=ar48le-v1 record=384 boundary=5504 capacity=4096 boundaries=8 resolved=0 authoritative=0\n");
    static const char hex[]="0123456789abcdef";uint64_t hash=0xcbf29ce484222325ULL;
    char row[2*sizeof(ArBoundary)+1];
    for(unsigned group=0;group<2;group++) {
        unsigned count=group?8:v.available?(unsigned)v.footer->record_count:0;
        for(unsigned i=0;i<count;i++) {
            const unsigned char *p=group?(const unsigned char *)&v.boundaries[i].b:(const unsigned char *)&v.events[i].r;
            unsigned ready=(unsigned)qp_read((volatile LONG *)(group?&v.boundaries[i].ready:&v.events[i].ready));
            size_t bytes=group?sizeof(ArBoundary):sizeof(ArRecord);
            /* Unready boundary storage may still be mutable: never read it. */
            if(!ready){LOG("r1: AUDIO_RELEASE_QUEUE_UNREADY group=%u i=%u\n",group,i);continue;}
            for(size_t j=0;j<bytes;j++){row[2*j]=hex[p[j]>>4];row[2*j+1]=hex[p[j]&15];}row[bytes*2]=0;
            hash=ap_digest(hash,(const char *)p,bytes);
            if(group)LOG("r1: AUDIO_RELEASE_QUEUE_BOUNDARY i=%u ready=%u data=%s\n",i,ready,row);
            else LOG("r1: AUDIO_RELEASE_QUEUE_EVENT i=%u ready=%u data=%s\n",i,ready,row);
        }
    }
    if(v.available) {
        const unsigned char *p=(const unsigned char *)v.footer;
        for(size_t j=0;j<sizeof(ArFooter);j++){row[2*j]=hex[p[j]>>4];row[2*j+1]=hex[p[j]&15];}row[2*sizeof(ArFooter)]=0;
    } else row[0]=0;
    LOG("r1: AUDIO_RELEASE_QUEUE_END v=1 available=%llu data=%s base_ap_digest=%016llx qp_stage=%ld qp_record_count=%ld qp_errors=%ld payload_digest=%016llx late_invalid=%llu errors=%llu resolved=0 authoritative=0\n",
        (unsigned long long)v.available,row,(unsigned long long)ap_hash,(long)qp_read(&g_qp_stage),(long)qp_read(&g_qp_count),
        (long)qp_read(&g_qp_errors),(unsigned long long)hash,(unsigned long long)v.late_invalid,(unsigned long long)v.errors);
    SetLastError(error);
}
/* AUDIO_RELEASE_AP_END */

static void ap_capture_held(long long frame,int old) {
    if(!ap_lock())return;
    if((frame==118 && old==0 && g_ap_stage==0) ||
       (frame==119 && (old==1 || old==3) && g_ap_stage==old)) {
        if(g_ap_actor && !qp_actor_held(g_ap_actor))ap_fail(AP_BOUNDARY);
        ap_next(&g_ap_transitions);
        if(old==0) {
            g_ap_stage=1;g_ap_arm_ordinal=0;
            al_open_held();
            ap_simple(AP_INTERVAL_BEGIN,NULL,1);
            ar_ap_boundary(0,frame,g_ap_id);
            /* A checkpoint import can span capture118. Retain its actual
             * pre-window entry/bind copies rather than inventing a new entry
             * at its post-window return or dereferencing the suspended Ctx. */
            for(unsigned i=0;i<AP_TICKETS;i++) {
                ApTicket *t=&g_ap_tickets[i];if(!t->id)continue;
                ApRecord *r=ap_event(AP_IMPORT_ENTER,&t->entry_ctx,1);
                if(r){r->ctx=(uintptr_t)t->ctx;r->ticket=t->id;r->purpose=t->purpose;
                    r->target=t->sym;r->region=t->region;r->coverage|=AP_BEFORE_WINDOW;}
                ap_publish(r);
                if(t->binds) {
                    r=ap_event(AP_IMPORT_BIND,&t->bind_ctx,1);
                    if(r){r->ctx=(uintptr_t)t->ctx;r->ticket=t->id;r->purpose=t->purpose;
                        r->target=t->sym;r->region=t->region;r->coverage|=AP_BEFORE_WINDOW;r->binding=t->binding;}
                    ap_publish(r);
                }
            }
            if(ap_open()) {
                g_ap_region.coverage|=AP_BEFORE_WINDOW;
                g_ap_region.attempts=g_ap_region.returns=g_ap_region.latest_return=0;
                g_ap_region.first_qp=g_ap_region.last_qp=0;
                ap_simple(AP_REGION_RESUME,NULL,1);
            }
        } else {
            al_end_held(old); /* separate suffix pending, before epoch invalidation */
            ap_archive(AP_SUFFIX_HELD);ap_simple(AP_INTERVAL_END,NULL,1);
            ar_ap_boundary(old==1?1:4,frame,g_ap_id);
            uint64_t pending=ap_pending();
            if(pending&14)ap_fail(AP_PENDING);
            if(old==3) {
                g_ap_pending_seal=pending;
                g_ap_pending_category[0]=ap_open()?1:0;g_ap_pending_category[1]=g_ap_producer?1:0;
                for(unsigned i=0;i<AP_TICKETS;i++)if(g_ap_tickets[i].id)
                    g_ap_pending_category[g_ap_tickets[i].purpose?3:2]++;
            }
            ap_error_held(); /* publish while the old observation arm is held */
            ap_invalidate();g_ap_stage=old==3?4:2;
            g_ap_region.state=old==3?AP_SEALED:AP_GAP;
        }
    } else ap_fail(AP_BOUNDARY);
    if(g_ap_stage!=4)ap_error_held();
    ap_unlock();
}
static void ap_load_begin(long long frame,int old) {
    if(!ap_lock())return;
    al_cancel(AL_LOAD_BEGIN_CUT); /* revoke even when restoration preparation refuses */
    if(frame!=118 || old!=2 || g_ap_stage!=2 || g_ap_region.state!=AP_GAP)ap_fail(AP_BOUNDARY);
    else { ap_next(&g_ap_transitions);ap_invalidate();ap_simple(AP_GAP_BEGIN,NULL,1);
        ar_ap_boundary(2,frame,g_ap_id);
        al_boundary(AL_GAP_BEGIN);g_ap_region.state=AP_GAP; }
    ap_unlock();
}
static void ap_load_ready_held(long long frame,int old) {
    if(!ap_lock())return;
    al_cancel(AL_LOAD_READY_CUT);
    if(frame!=118 || old!=2 || g_ap_stage!=2 || !g_ap_transitions ||
       g_ap_events[g_ap_count?g_ap_count-1:0].r.kind!=AP_GAP_BEGIN)ap_fail(AP_BOUNDARY);
    else {
        if(g_ap_actor && !qp_actor_held(g_ap_actor))ap_fail(AP_BOUNDARY);
        ap_next(&g_ap_transitions);ap_invalidate();ap_next(&g_ap_generation);
        g_ap_stage=3;g_ap_arm_ordinal=0;g_ap_region.state=AP_AWAIT_PREFIX;
        ap_simple(AP_LOAD_READY,NULL,1);
        ar_ap_boundary(3,frame,g_ap_id);
        al_boundary(AL_LOAD_READY);
    }ap_unlock();
}
static void ap_init(void) {
    const char *ar=getenv("SSBU_RB_AUDIO_RELEASE_QUEUE");
    int ar_requested=ar && strcmp(ar,"0");
    const char *e=getenv("SSBU_RB_AUDIO_CONTINUATION");
    if(ar_requested && (strcmp(ar,"1") || !e || strcmp(e,"1")))r1_hold_fatal("audio release requires option=1 and admitted AP/QP");
    if(!e || !strcmp(e,"0"))return;
    if(strcmp(e,"1") || !qp_read(&g_qp_on) || !g_qp_original)r1_hold_fatal("audio continuation requires queue probe=1");
    const char *sky=getenv("SSBU_SKYLINE");
    if(!sky || strcmp(sky,"0"))r1_hold_fatal("audio continuation requires the admitted base-game Skyline=0 fixture");
    const char *blocked[]={"SSBU_EXPERIMENT_POKE","SSBU_IMPORT_WATCH","SSBU_ICALLS","SSBU_MODS","SSBU_HOOK_COUNT","SSBU_HOOK_SELFTEST"};
    for(unsigned i=0;i<sizeof blocked/sizeof blocked[0];i++) {
        const char *v=getenv(blocked[i]);if(v && *v)r1_hold_fatal("audio continuation unvalidated active observer/mutator");
    }
    if(getenv("SSBU_HOOK_SELFTEST"))r1_hold_fatal("audio continuation hook selftest presence is active");
    host_audio_require_handlers();hook_require_audio_sites();game_require_audio_postload_site();
    g_ap_region.state=AP_AWAIT_PREFIX;
    InterlockedExchange(&g_ap_on,1);
    if(ar_requested && !audio_release_probe_configure())r1_hold_fatal("audio release observer initialization refused");
}
static uint64_t ap_digest(uint64_t h,const char *s,size_t n) {
    for(size_t i=0;i<n;i++)h=(h^(unsigned char)s[i])*0x100000001b3ULL;return h;
}
static void ap_drain(void) {
    if(!qp_read(&g_ap_on) || g_ap_stage!=4 || g_rg_kept)return;
    for(int i=0;i<g_nth;i++)if(g_th[i].held)return;
    if(qp_read(&g_ap_owner))return; /* Busy post-seal entry: defer, not lost publication. */
    if(g_ap_reported) {
        ar_ap_drain(0);
        al_drain(0,g_ap_reported_errors); /* late suffix errors do not rewrite either seal */
        LONG errors=qp_read(&g_ap_errors);
        if(errors!=g_ap_reported_errors) {
            /* Deferred invalidation of an already emitted packet. Analyzer
             * rejects this marker; never rewrite its old terminal digest. */
            LOG("r1: AUDIO_CONTINUATION_LATE_ERROR v=1 authoritative=0 errors=%u\n",(unsigned)errors);
            g_ap_reported_errors=errors;
        }
        return;
    }
    g_ap_reported=1;unsigned ready=0;
    for(unsigned i=0;i<g_ap_count;i++)if(qp_read(&g_ap_events[i].ready))ready++;else ap_fail(AP_UNREADY);
    LOG("r1: AUDIO_CONTINUATION_BEGIN v=1 authoritative=0 layout=ctx848le-v1 record=1560 binding=320 capacity=512 interior=496 tickets=8\n");
    uint64_t hash=0xcbf29ce484222325ULL;
    for(unsigned i=0;i<g_ap_count;i++) {
        char row[2*sizeof(ApRecord)+128];
        int n=snprintf(row,sizeof row,"i=%u ready=%u data=",i,(unsigned)qp_read(&g_ap_events[i].ready));
        const unsigned char *p=(const unsigned char *)&g_ap_events[i].r;
        static const char hex[]="0123456789abcdef";
        for(size_t j=0;j<sizeof(ApRecord);j++){row[n++]=hex[p[j]>>4];row[n++]=hex[p[j]&15];}row[n++]=0;
        hash=ap_digest(hash,row,(size_t)n-1);
        LOG("r1: AUDIO_CONTINUATION_EVENT %s\n",row);
    }
    LONG serialized_errors=qp_read(&g_ap_errors);
    LOG("r1: AUDIO_CONTINUATION_END v=1 authoritative=0 count=%llu ready=%u interior=%llu boundaries=%llu drops=%llu errors=%u stage=%ld epoch=%llu generation=%llu transitions=%llu complete=%llu partial=%llu pending=%llu pending_region=%llu pending_producer=%llu pending_audio=%llu pending_import=%llu peak_tickets=%llu gap_activity=%llu digest=%016llx sealed=1\n",
        (unsigned long long)g_ap_count,ready,(unsigned long long)g_ap_interior,(unsigned long long)g_ap_boundary_count,
        (unsigned long long)g_ap_drops,(unsigned)serialized_errors,(long)g_ap_stage,(unsigned long long)g_ap_epoch,
        (unsigned long long)g_ap_generation,(unsigned long long)g_ap_transitions,(unsigned long long)g_ap_complete,
        (unsigned long long)g_ap_partial,(unsigned long long)g_ap_pending_seal,
        (unsigned long long)g_ap_pending_category[0],(unsigned long long)g_ap_pending_category[1],
        (unsigned long long)g_ap_pending_category[2],(unsigned long long)g_ap_pending_category[3],(unsigned long long)g_ap_peak_tickets,
        (unsigned long long)g_ap_gap_activity,(unsigned long long)hash);
    g_ap_reported_errors=serialized_errors;
    al_drain(hash,serialized_errors);
    ar_ap_drain(hash);
}
