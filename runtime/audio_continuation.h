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
#endif
