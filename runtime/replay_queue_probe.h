/* Audio lifecycle is separate; declarations permit inclusion after QP. */
static void ap_init(void);
static void ap_capture_held(long long,int);
static void ap_load_begin(long long,int);
static void ap_load_ready_held(long long,int);
static void ap_producer_enter(const Ctx *,long,int);
static void ap_drain(void);
/* Bounded 13.0.5 queue observer, included by r1_ring.c. Host-only receipts;
 * no guest writes, scheduling intervention or clock substitution. */
#define QP_Q 0x710529b840ULL
#define QP_CAP 512
enum { QP_OVERLAP=1, QP_STALE=2, QP_IDENTITY=4, QP_PENDING=8,
       QP_READ=16, QP_OVERFLOW=32, QP_BOUNDARY=64, QP_SIGNAL=128 };
typedef struct {
    volatile LONG ready;
    LONG stage, kind, token;
    DWORD actor;
    uint64_t ctx, target, lr, a, b, arg;
    uint32_t p, c, value, payload[8];
} QpEvent;
typedef struct {
    volatile LONG active;
    LONG token, stage;
    volatile LONG actor;
    const Ctx *ctx;
    uint32_t cursor;
    int accepted, pending;
} QpOperation;
static QpEvent g_qp_events[QP_CAP];
static QpOperation g_qp_producer, g_qp_consumer;
static volatile LONG g_qp_on, g_qp_stage, g_qp_seq, g_qp_count, g_qp_errors;
static ImportFn g_qp_original;
static int g_qp_reported;
static LONG qp_read(volatile LONG *p) { return InterlockedCompareExchange(p,0,0); }
static void qp_fail(LONG error) { InterlockedOr(&g_qp_errors,error); }
static int qp_running(void) { return qp_read(&g_qp_on) && qp_read(&g_qp_stage)<4; }
static QpEvent *qp_event(int kind,LONG token,const Ctx *c) {
    LONG stage=qp_read(&g_qp_stage);
    if (!stage || stage>=4) return NULL;
    LONG index=InterlockedIncrement(&g_qp_count)-1;
    if (index>=QP_CAP) { qp_fail(QP_OVERFLOW); return NULL; }
    QpEvent *e=&g_qp_events[index];
    e->stage=stage; e->kind=kind; e->token=token; e->actor=GetCurrentThreadId();
    e->ctx=(uint64_t)(uintptr_t)c;
    if(c) { e->lr=c->x[30];e->a=c->x[0];e->b=c->x[1];e->arg=c->x[2]; }
    e->p=rd32(QP_Q+4); e->c=rd32(QP_Q+8);
    return e;
}
static void qp_publish(QpEvent *e) { if(e) InterlockedExchange(&e->ready,1); }
static int qp_copy(uint32_t *out,uint64_t address,size_t size) {
    MEMORY_BASIC_INFORMATION mi;
    if(address>UINT64_MAX-size || !VirtualQuery((void *)(uintptr_t)address,&mi,sizeof mi) ||
       mi.State!=MEM_COMMIT || (mi.Protect&(PAGE_GUARD|PAGE_NOACCESS)) ||
       (uint64_t)(uintptr_t)mi.BaseAddress+mi.RegionSize<address+size) { qp_fail(QP_READ);return 0; }
    memcpy(out,(const void *)(uintptr_t)address,size);return 1;
}
static LONG qp_enter(QpOperation *op,const Ctx *c) {
    LONG token=InterlockedIncrement(&g_qp_seq);
    if(token<=0 || InterlockedCompareExchange(&op->active,1,0)) { qp_fail(QP_OVERLAP);return 0; }
    DWORD actor=GetCurrentThreadId();
    LONG prior=InterlockedCompareExchange(&op->actor,(LONG)actor,0);
    if((prior && prior!=(LONG)actor) || (op->ctx && op->ctx!=c)) {
        qp_fail(QP_IDENTITY);InterlockedExchange(&op->active,0);return 0;
    }
    op->ctx=c;op->token=token;op->stage=qp_read(&g_qp_stage);op->accepted=0;
    return token;
}
static int qp_matches(QpOperation *op,LONG token,const Ctx *c) {
    if(!token || !qp_read(&op->active) || op->token!=token || op->ctx!=c ||
       op->actor!=GetCurrentThreadId() || op->stage!=qp_read(&g_qp_stage)) {
        qp_fail(QP_STALE);return 0;
    }
    return 1;
}
static void qp_confirm(const Ctx *c) {
    QpOperation *op=&g_qp_consumer;
    LONG actor=qp_read(&op->actor);
    if(c && actor && (DWORD)actor!=GetCurrentThreadId()) { qp_fail(QP_IDENTITY);return; }
    if(!op->pending) return;
    if(qp_read(&op->active) || op->stage!=qp_read(&g_qp_stage) ||
       (c && (op->ctx!=c || op->actor!=GetCurrentThreadId())) ||
       rd32(QP_Q+8)!=(uint32_t)(op->cursor+1)) { qp_fail(QP_PENDING);return; }
    QpEvent *e=qp_event(8,op->token,c);if(e)e->value=op->cursor+1;qp_publish(e);
    op->pending=0;
}
static void qp_producer_hook(Ctx *c,void *user) {
    (void)user;
    if(!qp_running() || c->x[2]!=QP_Q) { g_qp_original(c);return; }
    DWORD error=GetLastError();
    LONG token=qp_enter(&g_qp_producer,c);
    QpEvent *e=qp_event(1,token,c);
    if(e) {
        uint32_t a[4]={0},b[4]={0};
        /* Only read inputs in the pinned caller's live guest stack, including
         * rejected attempts whose original producer would not dereference them. */
        int known=c->x[30]==0x710398b444ULL && c->x[31]<=UINT64_MAX-1300 &&
            c->x[0]==c->x[31]+1284 && c->x[1]==c->x[31]+640;
        if(!known)qp_fail(QP_IDENTITY);
        if(known && qp_copy(a,c->x[0],sizeof a) && qp_copy(b,c->x[1],sizeof b))
            for(int i=0;i<4;i++){e->payload[2*i]=b[i];e->payload[2*i+1]=a[i];}
        qp_publish(e);
    }
    if(token)ap_producer_enter(c,token,g_qp_producer.stage);
    SetLastError(error);g_qp_original(c);error=GetLastError();
    if(token && qp_matches(&g_qp_producer,token,c)) {
        if(!g_qp_producer.accepted) {
            if((uint32_t)c->x[8]<=3 || !cond((Ctx *)c,8)) qp_fail(QP_SIGNAL);
            e=qp_event(3,token,c);
            if(e){e->value=(uint32_t)c->x[8];e->c=(uint32_t)c->x[9];e->p=e->c+e->value;}
            qp_publish(e);
        }
        qp_publish(qp_event(4,token,c));
        r1_audio_producer_return(c,token,g_qp_producer.accepted);
        InterlockedExchange(&g_qp_producer.active,0);
    }
    SetLastError(error);
}
void r1_queue_signal(const Ctx *c,int sym) {
    if(!qp_running() || sym!=1401 || c->x[0]!=0x7106df60d0ULL || c->x[2]!=QP_Q) return;
    QpOperation *op=&g_qp_producer;
    if((DWORD)qp_read(&op->actor)!=GetCurrentThreadId()) { qp_fail(QP_SIGNAL);return; }
    if(!qp_matches(op,op->token,c) || op->accepted) { qp_fail(QP_SIGNAL);return; }
    op->accepted=1;
    QpEvent *e=qp_event(2,op->token,c);
    if(e){e->value=(uint32_t)c->x[8];qp_copy(e->payload,QP_Q+0x138+(((e->value-1)&3)<<5),32);}
    qp_publish(e);
}
/* Called around the complete dispatch, including all target families. The
 * returned token is never reused; a restored native local cannot claim a new op. */
long r1_queue_dispatch_enter(const Ctx *c,uint64_t target) {
    if(!qp_running())return 0;
    if(c->x[30]==0x710398b444ULL) {
        QpEvent *e=qp_event(5,0,c);if(e)e->target=target;qp_publish(e);
        if(target!=0x710398bc70ULL || c->x[2]!=QP_Q)qp_fail(QP_IDENTITY);
    }
    if(c->x[30]!=0x710398b968ULL)return 0;
    LONG actor=qp_read(&g_qp_consumer.actor);
    if(actor && (DWORD)actor!=GetCurrentThreadId()) { qp_fail(QP_IDENTITY);return 0; }
    qp_confirm(c);
    if(g_qp_consumer.pending)qp_fail(QP_PENDING);
    LONG token=qp_enter(&g_qp_consumer,c);
    if(!token)return 0;
    g_qp_consumer.cursor=rd32(QP_Q+8);
    uint64_t slot=QP_Q+0x138+((g_qp_consumer.cursor&3)<<5);
    if(c->x[25]!=QP_Q || c->x[0]!=slot || c->x[1]!=slot+16)qp_fail(QP_IDENTITY);
    QpEvent *e=qp_event(6,token,c);
    if(e){e->target=target;e->value=g_qp_consumer.cursor;qp_copy(e->payload,slot,32);}qp_publish(e);
    return token;
}
void r1_queue_dispatch_exit(const Ctx *c,long token) {
    if(!token)return;
    if(!qp_matches(&g_qp_consumer,token,c))return;
    if(rd32(QP_Q+8)!=g_qp_consumer.cursor)qp_fail(QP_PENDING);
    qp_publish(qp_event(7,token,c));
    g_qp_consumer.pending=1;InterlockedExchange(&g_qp_consumer.active,0);
}
void r1_queue_tick(const Ctx *c) {
    if(qp_running() && c->x[30]==0x710398bbf0ULL)qp_confirm(c);
}
static int qp_actor_held(DWORD actor) {
    if(!actor)return 0;
    for(int i=0;i<g_nth;i++)if(GetThreadId(g_th[i].h)==actor)return g_th[i].held;
    return 0;
}
static int qp_quiet(void) {
    if(!qp_actor_held((DWORD)qp_read(&g_qp_producer.actor)) ||
       !qp_actor_held((DWORD)qp_read(&g_qp_consumer.actor)) ||
       qp_read(&g_qp_producer.active) || qp_read(&g_qp_consumer.active)) {
        qp_fail(QP_BOUNDARY);return 0;
    }
    return 1;
}
static void qp_boundary(int kind) {
    if(!qp_quiet())return;
    qp_confirm(NULL);
    QpEvent *e=qp_event(9,0,NULL);
    if(e){e->value=kind;e->lr=rd8(QP_Q);e->target=rd64(QP_Q+0x130);e->arg=rd64(QP_Q+0x10);
        e->a=rd64(QP_Q+0x120);e->b=rd64(QP_Q+0x128);}
    qp_publish(e);
    for(int i=0;i<4;i++) {e=qp_event(10,0,NULL);if(e){e->value=i;qp_copy(e->payload,QP_Q+0x138+i*32,32);}qp_publish(e);}
}
static void qp_capture(long long frame) {
    if(!qp_read(&g_qp_on))return;
    LONG stage=qp_read(&g_qp_stage);
    if(frame==118 && stage==0) {
        if(qp_quiet())qp_confirm(NULL);
        ap_capture_held(frame,stage);
        InterlockedExchange(&g_qp_stage,1);qp_boundary(1);
    } else if(frame==119 && stage==1) {ap_capture_held(frame,stage);qp_boundary(2);InterlockedExchange(&g_qp_stage,2);}
    else if(frame==119 && stage==3) {ap_capture_held(frame,stage);qp_boundary(4);InterlockedExchange(&g_qp_stage,4);}
}
static void qp_load_begin(long long frame) {
    if(qp_read(&g_qp_on) && frame==118 && qp_read(&g_qp_stage)==2) {
        ap_load_begin(frame,2);
        /* No queue read: continuation preparation may release/reacquire workers. */
        LONG i=InterlockedIncrement(&g_qp_count)-1;
        if(i>=QP_CAP)qp_fail(QP_OVERFLOW);
        else {QpEvent *e=&g_qp_events[i];e->stage=2;e->kind=11;qp_publish(e);}
    }
}
static void qp_load_ready(long long frame) {
    if(!qp_read(&g_qp_on) || frame!=118 || qp_read(&g_qp_stage)!=2)return;
    /* The gap is reported, but cannot carry an operation through rewound memory. */
    if(!qp_quiet() || g_qp_consumer.pending)qp_fail(QP_BOUNDARY);
    ap_load_ready_held(frame,2);
    InterlockedExchange(&g_qp_stage,3);qp_boundary(3);
}
static void qp_init(void) {
    const char *e=getenv("SSBU_RB_QUEUE_PROBE");if(!e || !strcmp(e,"0"))return;
    const char *sim=getenv("SSBU_RB_SIM"),*verify=getenv("SSBU_RB_SIM_VERIFY"),*net=getenv("SSBU_RB_NET");
    const char *skip=getenv("SSBU_RB_SIM_SKIP"),*lite=getenv("SSBU_RB_SIM_LITE");
    if(strcmp(e,"1") || g_game_build!=GAME_13_0_5 || !sim || strcmp(sim,"120,1,60") ||
       !verify || strcmp(verify,"2") || !net || strcmp(net,"0") || !skip || strcmp(skip,"0") || !lite || strcmp(lite,"0"))
        r1_hold_fatal("queue probe requires the pinned offline depth-one fixture");
    if(dyn_sym_count<=1401 || strcmp(dyn_syms[1401].name,"_ZN2nn2os11SignalEventEPNS0_9EventTypeE"))
        r1_hold_fatal("queue signal import identity");
    hook_install_queue_probe(qp_producer_hook,&g_qp_original);
    InterlockedExchange(&g_qp_on,1);
}
static void qp_drain(void) {
    if(!qp_read(&g_qp_on) || g_qp_reported || qp_read(&g_qp_stage)!=4 || g_rg_kept)return;
    for(int i=0;i<g_nth;i++)if(g_th[i].held)return;
    g_qp_reported=1;LONG n=qp_read(&g_qp_count);
    LOG("r1: QUEUE_PROBE_BEGIN v=1 target=119 queue=710529b840 capacity=512 authoritative=0\n");
    for(LONG i=0;i<n && i<QP_CAP;i++) {
        QpEvent *e=&g_qp_events[i];
        if(!qp_read(&e->ready)) { LOG("r1: QUEUE_PROBE_EVENT i=%ld ready=0\n",(long)i);continue; }
        LOG("r1: QUEUE_PROBE_EVENT i=%ld ready=%ld stage=%ld kind=%ld token=%ld actor=%lu ctx=%llx target=%llx lr=%llx a=%llx b=%llx arg=%llx p=%x c=%x value=%x data=%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x\n",
            (long)i,(long)qp_read(&e->ready),(long)e->stage,(long)e->kind,(long)e->token,(unsigned long)e->actor,
            (unsigned long long)e->ctx,(unsigned long long)e->target,(unsigned long long)e->lr,
            (unsigned long long)e->a,(unsigned long long)e->b,(unsigned long long)e->arg,e->p,e->c,e->value,
            e->payload[0],e->payload[1],e->payload[2],e->payload[3],e->payload[4],e->payload[5],e->payload[6],e->payload[7]);
    }
    LOG("r1: QUEUE_PROBE_END count=%ld errors=%ld producer_active=%ld consumer_active=%ld pending=%d stage=%ld\n",
        (long)n,(long)qp_read(&g_qp_errors),(long)qp_read(&g_qp_producer.active),(long)qp_read(&g_qp_consumer.active),
        qp_read(&g_qp_consumer.active)?-1:g_qp_consumer.pending,(long)qp_read(&g_qp_stage));
}
void r1_queue_init(void) { qp_init();ap_init(); }
