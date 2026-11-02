/* Included in replay_audio_probe.h after its v1 helpers. Independent companion
 * accounting under the SAME nonblocking AP CAS. No guest-memory count read. */
#define AL_CAP 64
#define AL_INTERIOR 48
enum { AL_POSTLOAD=1,AL_CUT,AL_BEGIN,AL_END,AL_GAP_BEGIN,AL_LOAD_READY,AL_ERROR };
enum { AL_INTERVAL_END=1,AL_LOAD_BEGIN_CUT,AL_LOAD_READY_CUT,AL_MISSING,
       AL_BEFORE_WINDOW,AL_PREFIX,AL_ORPHAN,AL_RESTORED,AL_INVALID };
typedef struct {
    uint64_t seq,kind,stage,epoch,generation,origin_stage,origin_epoch,origin_generation;
    uint64_t actor,ctx_pointer,region,region_coverage,end_ticket,region_end_event;
    uint64_t import_enter_event,import_bind_event,import_return_event,latest_producer_return_event;
    uint64_t arm_ordinal,region_ordinal,buffer,body_sp,parent_fp,load_pc,observation_pc;
    uint64_t effective_address,width,loaded_value,site_id,cut_reason,ctx_valid,metadata_status;
    uint64_t errors,pending,reserved0,reserved1;
    Ctx full;unsigned char import_name[96];
} AlRecord;
typedef struct { volatile LONG ready;AlRecord r; } AlEvent;
typedef struct { int live,eligible;AlRecord origin; } AlSuffix;
static AlEvent g_al_events[AL_CAP];
static AlSuffix g_al_suffix;
static AlRecord g_al_tombstone;
static volatile LONG g_al_errors;
static uint64_t g_al_count,g_al_id,g_al_interior,g_al_boundaries,g_al_drops;
static uint64_t g_al_expected,g_al_eligible,g_al_completed,g_al_positive,g_al_zero;
static uint64_t g_al_partial,g_al_canceled,g_al_missing,g_al_duplicate,g_al_orphan;
static uint64_t g_al_pending_seal,g_al_gap,g_al_outside;
static int g_al_reported;static LONG g_al_reported_errors;
_Static_assert(sizeof(AlRecord)==1232 && offsetof(AlRecord,full)==288 &&
    offsetof(AlRecord,import_name)==1136,"audio postload wire changed");
static void al_fail(LONG error) { InterlockedOr(&g_al_errors,error); }
static uint64_t al_next(uint64_t *n) {
    if(*n==UINT64_MAX){al_fail(AP_WRAP);return 0;}return ++*n;
}
static AlRecord *al_event(unsigned kind,const AlRecord *origin,int boundary) {
    if(!ap_recording() && !boundary)return NULL;
    if(g_al_count>=AL_CAP || (boundary?g_al_boundaries>=16:g_al_interior>=AL_INTERIOR)) {
        al_fail(AP_CAPACITY);al_next(&g_al_drops);return NULL;
    }
    uint64_t id=al_next(&g_al_id);if(!id)return NULL;
    AlEvent *e=&g_al_events[g_al_count++];memset(&e->r,0,sizeof e->r);
    if(boundary)g_al_boundaries++;else g_al_interior++;
    AlRecord *r=&e->r;
    if(origin) {
        /* Origin full is authority for comparison only, never a site witness. */
        memcpy(r,origin,offsetof(AlRecord,full));
        memcpy(r->import_name,origin->import_name,sizeof r->import_name);
    }
    r->seq=id;r->kind=kind;r->stage=g_ap_stage;r->epoch=g_ap_epoch;r->generation=g_ap_generation;
    r->site_id=AUDIO_POSTLOAD_SITE_ID;r->ctx_valid=0;
    r->errors=(unsigned)qp_read(&g_al_errors);r->pending=g_al_suffix.live?1:0;
    return r;
}
static void al_publish(AlRecord *r) {
    if(r)InterlockedExchange(&((AlEvent *)((unsigned char *)r - offsetof(AlEvent,r)))->ready,1);
}
static void al_boundary(unsigned kind) { al_publish(al_event(kind,NULL,1)); }
static int al_name(AlRecord *r,const Ctx *c) {
    if(!c->in_import)return 1;
    SIZE_T got=0;r->metadata_status=2;
    if(!ReadProcessMemory(GetCurrentProcess(),c->in_import,r->import_name,sizeof r->import_name,&got) ||
       got!=sizeof r->import_name){al_fail(AP_READ);return 0;}
    unsigned char *end=memchr(r->import_name,0,sizeof r->import_name);
    if(!end){al_fail(AP_BINDING);return 0;}
    memset(end,0,sizeof r->import_name-(size_t)(end-r->import_name));r->metadata_status=1;return 1;
}
static void al_cancel(unsigned reason) {
    if(!g_al_suffix.live)return;
    if(g_ap_stage>=1 && g_ap_stage<=3) {
        AlRecord *r=al_event(AL_CUT,&g_al_suffix.origin,1);
        if(r){r->cut_reason=reason;r->pending=1;}al_publish(r);
        al_next(&g_al_partial);al_next(&g_al_canceled);
    } else al_next(&g_al_outside);
    /* A boundary can revoke authority even if recording failed. Sticky errors
     * and counters retain the lost coverage; cancellation never counts complete. */
    g_al_tombstone=g_al_suffix.origin;g_al_suffix.live=0;
}
static void al_conflict(void) {
    if(!g_al_suffix.live)return;
    if(ap_recording()) {al_fail(AP_STALE);al_next(&g_al_missing);al_cancel(AL_MISSING);}
    else al_cancel(AL_INVALID);
}
static void al_origin(const Ctx *c,ApTicket *t,uint64_t return_event) {
    if(g_ap_stage==2 || g_ap_stage==4)return;
    if(g_al_suffix.live){al_conflict();al_fail(AP_OVERLAP);return;}
    AlRecord *o=&g_al_suffix.origin;memset(o,0,sizeof *o);
    o->origin_stage=g_ap_stage;o->origin_epoch=g_ap_epoch;o->origin_generation=g_ap_generation;
    o->actor=t->actor;o->ctx_pointer=(uintptr_t)t->ctx;o->region=t->region;
    o->region_coverage=g_ap_region.coverage;o->end_ticket=t->id;
    o->region_end_event=t->end_event;o->import_enter_event=t->enter_event;
    o->import_bind_event=t->bind_event;o->import_return_event=return_event;
    o->latest_producer_return_event=g_ap_region.latest_return;
    o->arm_ordinal=g_ap_arm_ordinal;o->region_ordinal=g_ap_region.attempts;
    o->buffer=g_ap_region.buffer;o->body_sp=g_ap_region.body_sp;o->parent_fp=g_ap_region.fp;
    memcpy(&o->full,c,sizeof *c);g_al_suffix.live=1;
    int valid=t->binds==1 && t->binding.status==AB_RAW && t->binding.fn &&
        t->binding.family==AB_IMPORT && t->binding.index==1887 &&
        t->binding.guest==IMPORT_BASE+1887*IMPORT_SLOT && !t->binding.offset && !t->binding.user &&
        t->epoch==g_ap_epoch && t->generation==g_ap_generation && t->region==g_ap_region.id &&
        g_ap_region.state==AP_AFTER_END && t->lr==0x710398b68cULL && c->x[30]==t->lr &&
        c->x[31]==o->body_sp && c->x[29]==o->parent_fp && o->body_sp<=UINT64_MAX-2336 &&
        o->parent_fp==o->body_sp+2336 && c->x[20]==o->buffer && c->x[27]==0x7106dd5000ULL;
    if(return_event && g_ap_count) {
        const ApRecord *r=&g_ap_events[g_ap_count-1].r;
        if(r->id!=return_event || r->kind!=AP_IMPORT_RETURN || r->ticket!=t->id ||
           memcmp(&r->full,&o->full,sizeof o->full))valid=0;
        o->metadata_status=r->metadata_status;memcpy(o->import_name,r->import_name,sizeof o->import_name);
        if(o->metadata_status!=(c->in_import?1:0))valid=0;
    } else if(!al_name(o,c))valid=0; /* pre-window return has no v1 publication */
    if(ap_recording() && (!o->region_end_event || !o->import_enter_event ||
        !o->import_bind_event || !o->import_return_event || qp_read(&g_ap_errors)))valid=0;
    if(!valid)al_fail(AP_BINDING);
    g_al_suffix.eligible=ap_recording() && valid && !o->region_coverage;
    if(ap_recording()) {al_next(&g_al_expected);if(g_al_suffix.eligible)al_next(&g_al_eligible);}
}
static int al_continuity(const Ctx *c,const Ctx *origin) {
    const unsigned char *a=(const unsigned char *)c,*b=(const unsigned char *)origin;
    /* Exactly x10 and x12 may change. All 848 bytes, including ex_val2 and
     * restored import metadata, participate in the continuity witness. */
    return !memcmp(a,b,80) && !memcmp(a+88,b+88,8) && !memcmp(a+104,b+104,sizeof *c-104);
}
void r1_audio_postload(const Ctx *c,uint64_t pc) {
    if(!qp_read(&g_ap_on) || pc!=AUDIO_POSTLOAD_PC)return; /* no Ctx/actor read off */
    DWORD error=GetLastError();
    if(!ap_lock()){al_fail(AP_OVERLAP);SetLastError(error);return;}
    if(g_ap_stage==4)goto done; /* Ordinary later execution is outside scope. */
    if(g_ap_stage==2){al_next(&g_al_gap);goto done;}
    if(!g_al_suffix.live) {
        if(ap_recording()) {
            int duplicate=g_al_tombstone.end_ticket && g_al_tombstone.actor==GetCurrentThreadId() &&
                g_al_tombstone.ctx_pointer==(uintptr_t)c && g_al_tombstone.origin_epoch==g_ap_epoch &&
                g_al_tombstone.origin_generation==g_ap_generation;
            al_fail(AP_STALE);al_next(duplicate?&g_al_duplicate:&g_al_orphan);al_next(&g_al_partial);
            AlRecord *r=al_event(AL_CUT,duplicate?&g_al_tombstone:NULL,1);
            if(r){r->cut_reason=duplicate?AL_INVALID:(g_ap_stage==3?AL_RESTORED:AL_ORPHAN);
                r->actor=GetCurrentThreadId();r->ctx_pointer=(uintptr_t)c;r->pending=0;}
            al_publish(r);
        } else al_next(&g_al_outside);
        goto done;
    }
    AlRecord *o=&g_al_suffix.origin;
    /* Check identity before dereferencing Ctx, so a foreign numeric pointer
     * cannot be attached to a newer region at a recycled buffer address. */
    if(o->actor!=GetCurrentThreadId() || o->ctx_pointer!=(uintptr_t)c || !ap_actor(c)) {
        al_fail(AP_IDENTITY);goto done;
    }
    if((o->origin_stage!=g_ap_stage || o->origin_epoch!=g_ap_epoch ||
        o->origin_generation!=g_ap_generation) && !(o->origin_stage==0 && g_ap_stage==1 &&
        o->origin_epoch==g_ap_epoch && o->origin_generation==g_ap_generation)) {
        al_fail(AP_STALE);goto done;
    }
    if(g_ap_region.state!=AP_AFTER_END || g_ap_region.id!=o->region || g_ap_producer || ap_pending()) {
        al_fail(AP_PENDING);goto done;
    }
    Ctx full;memcpy(&full,c,sizeof full); /* one actual site Ctx copy; never written back */
    if(full.x[31]!=o->body_sp || full.x[29]!=o->parent_fp || o->body_sp>UINT64_MAX-2336 ||
       o->parent_fp!=o->body_sp+2336 || full.x[30]!=0x710398b68cULL ||
       full.x[27]!=0x7106dd5000ULL || full.x[12]!=0x7106dd5000ULL || full.x[20]!=o->buffer ||
       full.x[10]>UINT32_MAX || !al_continuity(&full,&o->full)) {
        al_fail(AP_FRAME);goto done;
    }
    if(!ap_recording()){al_next(&g_al_outside);g_al_tombstone=*o;g_al_suffix.live=0;goto done;}
    if(!g_al_suffix.eligible) {al_cancel(o->origin_stage==0?AL_BEFORE_WINDOW:AL_PREFIX);goto done;}
    if(qp_read(&g_al_errors) || qp_read(&g_ap_errors))goto done;
    AlRecord *r=al_event(AL_POSTLOAD,o,0);if(!r)goto done;
    r->load_pc=0x710398b68cULL;r->observation_pc=pc;r->effective_address=full.x[27]+1972;
    r->width=4;r->loaded_value=full.x[10];r->ctx_valid=1;r->pending=0;
    memcpy(&r->full,&full,sizeof full);
    /* Raw metadata/from bytes were included in continuity; origin's bounded
     * copied name is used, never a second potentially changed name read. */
    al_publish(r);al_next(&g_al_completed);al_next(r->loaded_value?&g_al_positive:&g_al_zero);
    g_al_tombstone=*o;g_al_suffix.live=0;
done:
    ap_unlock();SetLastError(error);
}
static void al_open_held(void) {
    if(g_al_suffix.live && g_al_suffix.origin.origin_stage==0) {
        g_al_suffix.origin.region_coverage|=AP_BEFORE_WINDOW;g_al_suffix.eligible=0;al_next(&g_al_expected);
    }
    al_boundary(AL_BEGIN);
}
static void al_end_held(int stage) {
    unsigned pending=g_al_suffix.live?1:0;
    if(stage==3)g_al_pending_seal=pending;
    al_cancel(AL_INTERVAL_END);
    AlRecord *r=al_event(AL_END,NULL,1);if(r)r->pending=pending;al_publish(r);
}
static void al_drain(uint64_t base_digest,LONG base_errors) {
    LONG errors=qp_read(&g_al_errors);
    if(g_al_reported) {
        if(errors!=g_al_reported_errors) {
            LOG("r1: AUDIO_POSTLOAD_LATE_ERROR v=1 authoritative=0 errors=%u\n",(unsigned)errors);
            g_al_reported_errors=errors;
        }return;
    }
    g_al_reported=1;unsigned ready=0;
    for(unsigned i=0;i<g_al_count;i++)if(qp_read(&g_al_events[i].ready))ready++;else al_fail(AP_UNREADY);
    const AudioPostloadIdentity *identity=game_audio_postload_identity();
    int admitted=identity!=NULL;
    AudioPostloadIdentity empty={0};if(!identity){al_fail(AP_IDENTITY);identity=&empty;}
    LOG("r1: AUDIO_POSTLOAD_SITE v=1 authoritative=0 site_id=%016llx module=%llx table=%llx caller=%llx table_module=%llx caller_module=%llx count=%d kind=2 word=0 pinned=%d mutation_coverage=0\n",
        (unsigned long long)AUDIO_POSTLOAD_SITE_ID,(unsigned long long)identity->module,
        (unsigned long long)identity->table,(unsigned long long)identity->caller,
        (unsigned long long)identity->table_module,(unsigned long long)identity->caller_module,admitted,admitted);
    LOG("r1: AUDIO_POSTLOAD_BEGIN v=1 authoritative=0 layout=ctx848le-postload-v1 record=1232 capacity=64 interior=48\n");
    uint64_t hash=0xcbf29ce484222325ULL;
    for(unsigned i=0;i<g_al_count;i++) {
        char row[2*sizeof(AlRecord)+128];int n=snprintf(row,sizeof row,"i=%u ready=%u data=",i,(unsigned)qp_read(&g_al_events[i].ready));
        const unsigned char *p=(const unsigned char *)&g_al_events[i].r;static const char hex[]="0123456789abcdef";
        for(size_t j=0;j<sizeof(AlRecord);j++){row[n++]=hex[p[j]>>4];row[n++]=hex[p[j]&15];}row[n++]=0;
        hash=ap_digest(hash,row,(size_t)n-1);LOG("r1: AUDIO_POSTLOAD_EVENT %s\n",row);
    }
    errors=qp_read(&g_al_errors);
    LOG("r1: AUDIO_POSTLOAD_END v=1 authoritative=0 count=%llu ready=%u interior=%llu boundaries=%llu drops=%llu errors=%u base_errors=%u stage=%ld epoch=%llu generation=%llu expected=%llu eligible=%llu completed=%llu positive=%llu zero=%llu partial=%llu pending_now=%d pending_at_seal=%llu canceled=%llu missing=%llu duplicate=%llu orphan=%llu gap=%llu outside=%llu base_digest=%016llx digest=%016llx sealed=1\n",
        (unsigned long long)g_al_count,ready,(unsigned long long)g_al_interior,(unsigned long long)g_al_boundaries,
        (unsigned long long)g_al_drops,(unsigned)errors,(unsigned)base_errors,(long)g_ap_stage,
        (unsigned long long)g_ap_epoch,(unsigned long long)g_ap_generation,(unsigned long long)g_al_expected,
        (unsigned long long)g_al_eligible,(unsigned long long)g_al_completed,(unsigned long long)g_al_positive,
        (unsigned long long)g_al_zero,(unsigned long long)g_al_partial,g_al_suffix.live,
        (unsigned long long)g_al_pending_seal,(unsigned long long)g_al_canceled,(unsigned long long)g_al_missing,
        (unsigned long long)g_al_duplicate,(unsigned long long)g_al_orphan,(unsigned long long)g_al_gap,
        (unsigned long long)g_al_outside,(unsigned long long)base_digest,(unsigned long long)hash);
    g_al_reported_errors=errors;
}
