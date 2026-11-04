/* Diagnostic ABI only. No Ctx/GameDataHost changes. All storage is host-owned. */
#ifndef AUDIO_CONTINUATION_H
#define AUDIO_CONTINUATION_H
#include <stdint.h>
typedef uint64_t AudioTicket;
enum { AB_MAIN=1, AB_HOST, AB_IMPORT, AB_NRO, AB_SDK };
enum { AB_RAW=1, AB_MISSING, AB_HOOK_UNRESOLVED, AB_NRO_DELEGATED_UNRESOLVED,
       AB_AMBIGUOUS, AB_MUTATED };
/* Fixed little-endian wire descriptor, 320 bytes. Names are copied, never
 * dereferenced at drain. RAW means selected pointer known, body/module/freeze
 * provenance still requires deferred independent inventory evidence. */
typedef struct {
    uint64_t family,status,guest,fn,user,index,offset,owner,base,size,loaded;
    uint64_t hook,target,head,top,state,repl,hook_user,orig;
    uint64_t sdk_addr,sdk_matches,mutation_coverage,registry,reserved;
    unsigned char name[96],build_id[32];
} AudioBinding;
static inline void audio_binding_name(AudioBinding *b,const char *name) {
    if(!name)return;
    unsigned n=0;while(n<sizeof b->name && name[n])n++;
    if(n==sizeof b->name)b->status=AB_AMBIGUOUS;
    memcpy(b->name,name,n);
}
AudioTicket r1_audio_indirect_enter(const Ctx *,uint64_t);
void r1_audio_indirect_return(const Ctx *,AudioTicket);
AudioTicket r1_audio_import_enter(const Ctx *,int);
void r1_audio_import_return(const Ctx *,int,AudioTicket);
void r1_audio_binding(const Ctx *,AudioTicket,const AudioBinding *);
void r1_audio_producer_return(const Ctx *,long,int);
/* Single inline seam; the value is already in x10, never reloaded by the host. */
#define AUDIO_POSTLOAD_PC 0x710398b694ULL
#define AUDIO_POSTLOAD_SITE_ID 0x7367c78de95eecf6ULL
void r1_audio_postload(const Ctx *,uint64_t);
void game_require_audio_postload_site(void);
typedef struct { uint64_t module,table,caller,table_module,caller_module; } AudioPostloadIdentity;
const AudioPostloadIdentity *game_audio_postload_identity(void);
void hook_require_audio_sites(void);
void hook_audio_binding(AudioBinding *);
void host_audio_require_handlers(void);
void host_audio_import_binding(AudioBinding *,int);
void sdk_audio_import_binding(AudioBinding *,ImportFn);
void sdk_dispatch_observed(Ctx *,uint64_t,AudioTicket);
int nro_call_indirect_observed(Ctx *,uint64_t,AudioTicket);
/* Preserves both entry and callee last-error: all observer entry points save
 * and restore it internally, including no-op/failed paths. */
void r1_audio_selected(const Ctx *,AudioTicket,uint64_t,uint64_t,ImportFn,
                       void (*)(Ctx *,void *),void *,uint64_t,uint64_t,const char *);

/* Bounded host release observer v1. Diagnostic ABI, never restored. */
enum { AR_PRECOLLECT=1,AR_POSTCOLLECT=2,AR_POP=3,AR_COLLECT_BEGIN=4,AR_CHECK=5,AR_PUBLISH=6,AR_COLLECT_END=7,AR_APPEND_BEGIN=8,AR_APPEND=9,AR_APPEND_REFUSE=10,AR_START_BEGIN=11,AR_START_SLOT=12,AR_START_COMMIT=13,AR_OPEN_BEFORE=14,AR_OPEN_RESET=15,AR_RESET_INTENT=16,AR_RESET_COMMIT=17,AR_LIFECYCLE_COMMIT=18,AR_BOUNDARY=19,AR_ERROR=20,AR_THREAD_POLL=21,AR_START_STATE=22 };
enum { AR_PHASE_ARMED=0,AR_PHASE_ORIGINAL=1,AR_PHASE_GAP=2,AR_PHASE_GAP_LOAD=3,AR_PHASE_REPLAY=4,AR_PHASE_SEALED=5 };
enum { AR_CALL_NONE=0,AR_CALL_GETTER=1,AR_CALL_AUDIO_THREAD=2,AR_CALL_STOP_FORCE=3,AR_CALL_CLOSE_FORCE=4,AR_CALL_OPEN=5,AR_CALL_START=6,AR_CALL_APPEND=7,AR_CALL_BOUNDARY=8 };
enum { AR_STAMP_DISABLED=0,AR_STAMP_VALID=1,AR_STAMP_PREFIX=2,AR_STAMP_GAP=3,AR_STAMP_OTHER_CALL=4,AR_STAMP_INVALID=5 };
enum { AR_DEC_NONE=0,AR_DEC_COLLECT_CALLED=1,AR_DEC_COLLECT_SKIPPED_CLOSED=2,AR_DEC_FORCED=3,AR_DEC_PASS_DEVICE=4,AR_DEC_BLOCK_DEVICE=5,AR_DEC_PASS_FALLBACK=6,AR_DEC_BLOCK_STOPPED=7,AR_DEC_BLOCK_NOT_DUE=8,AR_DEC_ACCEPTED=9,AR_DEC_REFUSED=10,AR_DEC_HELD_CAPTURE=11,AR_DEC_LOAD_MARKER_NOT_QUIET=12,AR_DEC_HELD_LOAD_READY=13 };
enum { AR_V_QUEUE_FIELDS_READ=1,AR_V_FRONT_READ=2,AR_V_PLAYING_SLOT_READ=4,AR_V_FLAGS_ACTUALLY_TESTED=8,AR_V_NOW_USED_IN_FALLBACK_COMPARE=16,AR_V_DUE_USED_IN_FALLBACK_COMPARE=32,AR_V_STARTED_ACTUALLY_TESTED=64,AR_V_ORIGINAL_COLLECT_NOW_READ=128,AR_V_AP_STAMP_VALID=256,AR_V_PREFIX=512,AR_V_GAP=1024,AR_V_POP_LOAD_VALID=2048,AR_V_BOUNDARY_STAMP_VALID=4096,AR_V_CONTROL_VALID=8192,AR_V_RESET_RETURN_VALID=16384,AR_V_OWNER_FIELDS_READ=32768,AR_V_HOST_ORDER_VALID=65536,AR_V_DIAGNOSTIC_TRUNCATED=131072,AR_V_QUEUE_GEOMETRY_VALID=262144 };
enum { AR_E_INIT_BUSY=1,AR_E_INIT_STATE=2,AR_E_UNINITIALIZED=4,AR_E_BOUNDARY_BUSY=8,AR_E_BOUNDARY_INFLIGHT=16,AR_E_BOUNDARY_INVALID=32,AR_E_REENTRANT=64,AR_E_AP_STAMP=128,AR_E_OBSERVER_OVERFLOW=256,AR_E_RELEASE_OVERRUN=512,AR_E_PLAY_GEOMETRY=1024,AR_E_OCCURRENCE=2048,AR_E_WRAP=4096,AR_E_CONTROL_OVERFLOW=8192,AR_E_CONTROL_AMBIGUOUS=16384,AR_E_CONTEXT_OVERLAP=32768,AR_E_UNREADY=65536,AR_E_END_BUSY=131072,AR_E_LATE_INVALID=262144 };
enum { AR_B_OK=1,AR_B_BUSY=2,AR_B_INFLIGHT=3,AR_B_INVALID=4,AR_B_REENTRANT=5,AR_B_UNINITIALIZED=6,AR_B_NOT_REACHED=7,AR_B_INIT_BUSY=8,AR_B_INIT_STATE=9 };
#define AR_CAP 4096
#define AR_BOUNDARIES 8
typedef struct {
    uint64_t ticket,epoch,generation,stage,actor,ctx,lr,sp,fp,audio_out,fn,enter_event,bind_event,status;
} ArStamp;
typedef struct {
    uint64_t slot,frame,event,transition,stage,epoch,generation,actor,hold,valid;
} ArBoundaryStamp;
typedef struct { uint64_t record_id,kind,valid_mask,errors,stream_id,phase,op_id,collect_id,write_seq,device_epoch,actor,ctx,ap_ticket,ap_epoch,ap_generation,ap_stage,ap_enter_event,ap_bind_event,lr,audio_out_arg,audio_out_owner,open,started,wave,play_head,play_tail,rel_head,rel_tail,play_id,release_id,guest,slot,prepared,flags,due,now,everything,decision,n,popped,returned,front_guest,front_release_id,front_play_id,control_id,stamp_status,caller_kind,detail; } ArRecord;
typedef struct { ArRecord r; volatile int32_t ready; uint32_t padding; } ArEvent;
typedef struct { uint64_t cursor,release_id,play_id,guest; } ArReleased;
typedef struct { uint64_t cursor,play_id,guest,prepared,due,frames; } ArPlaying;
typedef struct { ArRecord r; ArReleased released[64]; ArPlaying playing[64]; } ArBoundary;
typedef struct { ArBoundary b; volatile int32_t ready; uint32_t padding; } ArBoundaryEvent;
typedef struct {
    uint64_t version,layout,record_bytes,boundary_bytes,capacity,boundary_capacity,stream_id;
    uint64_t sealed,failed,record_count,ready_count,attempted_records,dropped_records,first_record_id,last_attempted_record_id;
    uint64_t kind_counts[23];
    uint64_t first_op_id,last_op_id,first_write_seq,last_write_seq,last_collect_id,device_epoch,phase,errors,late_invalid;
    uint64_t boundary_statuses[8];
    uint64_t pending_control_count,pending_getter_count,pending_collect_count;
    /* Drain-time external bindings are serialized separately, never written into this frozen object. */
    uint64_t resolved,authoritative;
} ArFooter;
typedef struct {
    const ArEvent *events; const ArBoundaryEvent *boundaries; const ArFooter *footer;
    uint64_t available,late_invalid,errors;
} ArView;
int audio_release_probe_configure(void);
int audio_release_probe_enabled(void);
int audio_release_probe_boundary(const ArBoundaryStamp *);
int audio_release_probe_view(ArView *);
void audio_release_probe_late(uint64_t);
int r1_audio_release_stamp(const Ctx *,ImportFn,ArStamp *);

#endif
