/* Synthetic guest/service environment only. Observer and wrappers are injected
 * verbatim by test_replay_queue_source.py; Ctx/memory/conditions use runtime.h. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "hostrt.h"

#define IMAGE_SIZE 0x7500000ULL
#define PRODUCER 0x710398bc70ULL
#define SUBMIT_LR 0x710398b444ULL
#define CALLBACK_LR 0x710398b968ULL
#define TICK_LR 0x710398bbf0ULL
#define SINK_TARGET 0x710373e620ULL
#define NRO_CALLBACK 0x7200001230ULL
#define SDK_CALLBACK 0x7500001230ULL
#define FALLBACK_CALLBACK 0x7600001230ULL
#define EVENT 0x7106df60d0ULL
#define ENTRY_ERROR 711
#define RESULT_ERROR 913

int g_game_build=GAME_13_0_5;
static DWORD tid=101;
static int g_nth=2,g_rg_kept,installs,original_calls,callback_calls,signal_calls;
static struct { HANDLE h; int held; } g_th[2];
static Ctx producer,consumer,foreign;
static unsigned char input_storage[8192];
#define input_stack (input_storage+64)
static char signal_name[96]="_ZN2nn2os11SignalEventEPNS0_9EventTypeE";
const DynSym dyn_syms[1890] = {
    [42]={"fixture_callback",0,0}, [43]={"fixture_other",0,0}, [1401]={signal_name,0,0},
    [1884]={"_ZN2nn5audio25GetReleasedAudioOutBufferEPNS0_8AudioOutE",0,0},
    [1887]={"_ZN2nn5audio28GetAudioOutBufferDataPointerEPKNS0_14AudioOutBufferE",0,0}
};
const int dyn_sym_count=1890;
static char log_text[2*1024*1024];
static size_t log_length;
static int log_count,query_reads;
static void fixture_producer(Ctx *c);
static void fixture_callback(Ctx *c);
static void fixture_signal(Ctx *c);
static void (*installed_hook)(Ctx *,void *);

/* Thread identities and clock are deterministic OS boundaries. Interlocked
 * operations, VirtualQuery/protection and the guest mapping are real Windows. */
static DWORD fixture_tid(void) { SetLastError(0xade); return tid; }
static DWORD fixture_thread_id(HANDLE h) { SetLastError(0xadd); return (DWORD)(uintptr_t)h; }
static SIZE_T fixture_query(LPCVOID p,PMEMORY_BASIC_INFORMATION mi,SIZE_T n) {
    query_reads++; SIZE_T result=VirtualQuery(p,mi,n); SetLastError(0xadc); return result;
}
#define GetCurrentThreadId fixture_tid
#define GetThreadId fixture_thread_id
#define VirtualQuery fixture_query
static void r1_hold_fatal(const char *s) { fprintf(stderr,"fixture refusal: %s\n",s); exit(74); }
void hook_install_queue_probe(void (*hook)(Ctx *,void *),ImportFn *orig) {
    installs++; installed_hook=hook; *orig=fixture_producer;
}
static void (*log_inject)(void);
static int fixture_log(const char *fmt,...) {
    assert(!g_rg_kept && !g_th[0].held && !g_th[1].held);
    va_list ap;va_start(ap,fmt);
    int n=vsnprintf(log_text+log_length,sizeof log_text-log_length,fmt,ap);va_end(ap);
    assert(n>=0 && (size_t)n<sizeof log_text-log_length);log_length+=(size_t)n;log_count++;
    if(log_inject && strstr(fmt,"AUDIO_CONTINUATION_END")){void (*f)(void)=log_inject;log_inject=NULL;f();}
    SetLastError(0xbad);
    return n;
}
#define LOG fixture_log
void hook_require_audio_sites(void) {}
void hook_audio_binding(AudioBinding *b) { (void)b; }
void sdk_audio_import_binding(AudioBinding *b,ImportFn fn) { (void)b;(void)fn; }
/* QUEUE_OBSERVER_SOURCE */
/* AUDIO_OBSERVER_SOURCE */

static int audio_fixture_regions,audio_fixture_log_identity;
static int g_icall_mode,g_hostfn_count=2,t_hostfn;
static LONG64 g_hostfn_seq;
static struct {char name[72];ImportFn fn;volatile LONG64 calls;LONG64 first;
    void (*fnu)(Ctx *,void *);void *user;} g_hostfn[2];
static int g_watch_sym=-1,g_guest_frozen,g_import_count_all,g_import_order_count;
static uint64_t g_import_calls[1890],g_trace_seq;
static int g_import_order[1890],*g_import_open;
static ImportFn g_handlers[1890];
static void icall_record(Ctx *c,uint64_t address) { (void)c;(void)address; }
static int audit_path_hostfn(const char *name) { (void)name;return 0; }
static void audit_path_hit(const char *kind,const char *name,uint64_t from) { (void)kind;(void)name;(void)from; }
static int audit_strict_on(void) { return 1; }
void trace_printf(const char *fmt,...) { (void)fmt; }
void guest_trap(const char *what,uint64_t address) {
    fprintf(stderr,"unexpected trap: %s %llx\n",what,(unsigned long long)address);exit(75);
}
static void guest_freeze_wait(void) { assert(0); }
static void audio_body(Ctx *c);
static void audio_hook_adapter(Ctx *c) { qp_producer_hook(c,NULL); }
static ImportFn lookup_guest(uint64_t addr) {
    if(addr==0x7101000100ULL || addr==0x7600009990ULL)return audio_body;
    if(addr==PRODUCER)return audio_fixture_log_identity?audio_hook_adapter:fixture_producer;
    if(addr==SINK_TARGET || addr==FALLBACK_CALLBACK)return fixture_callback;
    return NULL;
}
static int nro_call_indirect(Ctx *c,uint64_t address) {
    if(address!=NRO_CALLBACK)return 0;fixture_callback(c);return 1;
}
static void sdk_dispatch(Ctx *c,uint64_t address) { assert(address==SDK_CALLBACK);fixture_callback(c); }
long long nvn_front_frame_next(void) { return 119; }
static void host_import_real(Ctx *c,int sym,AudioTicket,AudioTicket);
#define IMPHK_N 1
static ImportFn g_imphk_fn[IMPHK_N];
static struct {void (*fn)(Ctx *,void *);void *user;} g_imphk[IMPHK_N];
static void host_import_binding(Ctx *,int,ImportFn,AudioTicket,AudioTicket);
static void host_import_watch(Ctx *,int,AudioTicket,AudioTicket);
static BOOL fixture_qpc(LARGE_INTEGER *n) { n->QuadPart=123;return 1; }
static BOOL fixture_qpf(LARGE_INTEGER *n) { n->QuadPart=1000;SetLastError(444);return 1; }
#define QueryPerformanceCounter fixture_qpc
#define QueryPerformanceFrequency fixture_qpf
static void host_import_observed(Ctx *,int,AudioTicket);
int nro_call_indirect_observed(Ctx *c,uint64_t a,AudioTicket t) { (void)t;return nro_call_indirect(c,a); }
void sdk_dispatch_observed(Ctx *c,uint64_t a,AudioTicket t) { (void)t;sdk_dispatch(c,a); }
/* DISPATCH_SOURCE */
/* IMPORT_SOURCE */
static void host_clock_caller(const char *what,uint64_t lr) { (void)what;(void)lr; }
static int host_fixed_clock(uint64_t lr) { (void)lr;return 0; }
static void r1_clock_probe(uint64_t lr,uint64_t tick) { (void)lr;(void)tick;SetLastError(0xadb); }
#define TICK_HZ 19200000ULL
#define RET(v) (c->x[0]=(uint64_t)(v))
/* TICK_SOURCE */

enum { NORMAL, OMIT_SIGNAL, BAD_HI, NEST_PRODUCER, NEST_CONSUMER, DOUBLE_SIGNAL };
static int behavior,preserve_check;
static uint32_t payload_word(unsigned seed,unsigned i) { return 0x3e800000U+seed*32+i; }
static void fill_inputs(unsigned seed) {
    for(int i=0;i<4;i++) {
        uint32_t a=payload_word(seed,(unsigned)i*2+1),b=payload_word(seed,(unsigned)i*2);
        memcpy(input_stack+1284+i*4,&a,4);memcpy(input_stack+640+i*4,&b,4);
    }
}
static void prepare_producer(Ctx *c,unsigned seed) {
    fill_inputs(seed);
    c->x[31]=(uint64_t)(uintptr_t)input_stack;c->x[0]=c->x[31]+1284;c->x[1]=c->x[31]+640;
    c->x[2]=QP_Q;c->x[30]=SUBMIT_LR;
}
static void prepare_consumer(Ctx *c) {
    uint64_t slot=QP_Q+0x138+((rd32(QP_Q+8)&3)*32);
    c->x[0]=slot;c->x[1]=slot+16;c->x[2]=0x1234abcd;c->x[25]=QP_Q;c->x[30]=CALLBACK_LR;
}
static int events(int kind,int stage) {
    int n=0;for(int i=0;i<g_qp_count && i<QP_CAP;i++)
        if(g_qp_events[i].kind==kind && (!stage || g_qp_events[i].stage==stage))n++;
    return n;
}
static QpEvent *last_event(int kind) {
    for(int i=(g_qp_count<QP_CAP?g_qp_count:QP_CAP)-1;i>=0;i--)
        if(g_qp_events[i].kind==kind)return &g_qp_events[i];
    assert(0);return NULL;
}
static void assert_payload(const QpEvent *e,unsigned seed) {
    for(int i=0;i<8;i++)assert(e->payload[i]==payload_word(seed,(unsigned)i));
}
static void fixture_callback(Ctx *c) {
    if(preserve_check)assert(GetLastError()==ENTRY_ERROR);
    callback_calls++;c->x[5]^=0x123456789ULL;c->v[7].w[2]^=0x9324;c->N^=1;c->V^=1;
    c->ex_addr^=0x123;c->ex_val2^=0x789;SetLastError(RESULT_ERROR);
}
static void closure_callback(Ctx *c,void *user) { assert(user==input_stack);fixture_callback(c); }
static void fixture_signal(Ctx *c) {
    if(preserve_check)assert(GetLastError()==ENTRY_ERROR);
    if(qp_running() && !g_qp_errors)assert(g_qp_producer.accepted);
    assert(c->x[0]==EVENT && c->x[2]==QP_Q && c->x[30]==SUBMIT_LR);
    signal_calls++;c->x[4]^=0x442;c->v[2].w[1]^=0x334;c->ex_val^=0x556;
    SetLastError(RESULT_ERROR);
}
static void fixture_producer(Ctx *c) {
    if(preserve_check)assert(GetLastError()==ENTRY_ERROR);
    original_calls++;
    if(behavior==NEST_PRODUCER) {
        int saved=behavior;behavior=NORMAL;DWORD saved_tid=tid;Ctx *other=&foreign;
        prepare_producer(other,77);tid=404;SetLastError(ENTRY_ERROR);qp_producer_hook(other,NULL);
        tid=saved_tid;behavior=saved;
    }
    uint32_t p=rd32(QP_Q+4),n=rd32(QP_Q+8),used=p-n;
    c->x[8]=used;c->x[9]=n;c->C=used>=4;c->Z=used==3;
    if(used>3) { if(behavior==BAD_HI)c->C=0;SetLastError(RESULT_ERROR);return; }
    uint32_t a[4],b[4];memcpy(a,(void *)(uintptr_t)c->x[0],16);memcpy(b,(void *)(uintptr_t)c->x[1],16);
    uint64_t slot=QP_Q+0x138+((p&3)*32);
    for(int i=0;i<4;i++){wr32(slot+i*8,b[i]);wr32(slot+i*8+4,a[i]);}
    wr32(QP_Q+4,p+1);c->x[8]=(uint32_t)(p+1);c->x[0]=EVENT;
    if(behavior==NEST_CONSUMER) {
        DWORD saved=tid;tid=202;prepare_consumer(&consumer);call_indirect(&consumer,SINK_TARGET);
        wr32(QP_Q+8,rd32(QP_Q+8)+1);consumer.x[30]=TICK_LR;r1_queue_tick(&consumer);tid=saved;
    }
    if(behavior==OMIT_SIGNAL) { c->x[8]=1;c->C=0;SetLastError(RESULT_ERROR);return; }
    SetLastError(ENTRY_ERROR);host_import(c,1401);
    if(behavior==DOUBLE_SIGNAL) { r1_queue_signal(c,1401);SetLastError(RESULT_ERROR); }
}
static void submit(unsigned seed) {
    tid=101;prepare_producer(&producer,seed);SetLastError(ENTRY_ERROR);
    if(audio_fixture_log_identity)call_indirect(&producer,PRODUCER);else qp_producer_hook(&producer,NULL);
    assert(GetLastError()==RESULT_ERROR);
}
static void consume(int commit,int checkpoint) {
    tid=202;prepare_consumer(&consumer);SetLastError(ENTRY_ERROR);call_indirect(&consumer,SINK_TARGET);
    assert(GetLastError()==RESULT_ERROR);
    if(commit)wr32(QP_Q+8,rd32(QP_Q+8)+1);
    if(checkpoint){consumer.x[30]=TICK_LR;os_GetSystemTick(&consumer);assert(GetLastError()==444);}
}
static void held(int value) { g_th[0].held=g_th[1].held=value;tid=303; }
static void init(void) {
    _putenv("SSBU_RB_QUEUE_PROBE=1");_putenv("SSBU_RB_SIM=120,1,60");_putenv("SSBU_RB_SIM_VERIFY=2");
    _putenv("SSBU_RB_NET=0");_putenv("SSBU_RB_SIM_SKIP=0");_putenv("SSBU_RB_SIM_LITE=0");
    _putenv("SSBU_IMPORT_WATCH=");
    memset(&producer,0x5a,sizeof producer);memset(&consumer,0x6b,sizeof consumer);memset(&foreign,0x7c,sizeof foreign);
    producer.in_import=consumer.in_import=foreign.in_import="caller";
    g_th[0].h=(HANDLE)(uintptr_t)101;g_th[1].h=(HANDLE)(uintptr_t)202;
    g_handlers[1401]=fixture_signal;g_handlers[42]=fixture_callback;g_handlers[43]=fixture_callback;
    strcpy(g_hostfn[0].name,"fixture-host");g_hostfn[0].fn=fixture_callback;
    strcpy(g_hostfn[1].name,"fixture-closure");g_hostfn[1].fnu=closure_callback;g_hostfn[1].user=input_stack;
    void *base=(void *)(uintptr_t)(QP_Q&~0xffffULL);
    assert(VirtualAlloc(base,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==base);
    wr8(QP_Q,1);wr64(QP_Q+0x130,SINK_TARGET);wr64(QP_Q+0x10,0x1234abcd);
    wr64(QP_Q+0x120,0x1111222233334444ULL);wr64(QP_Q+0x128,0x5555666677778888ULL);
}
static void start(void) {
    qp_init();assert(installs==1 && installed_hook==qp_producer_hook && g_qp_on && !g_qp_stage);
    /* Track actor identities and completed work before detailed emission begins. */
    submit(1);consume(1,1);assert(!g_qp_count && !g_qp_errors && !g_qp_consumer.pending);
    wr32(QP_Q+4,0xfffffffc);wr32(QP_Q+8,0xfffffffc);
    held(1);qp_capture(117);assert(!g_qp_stage);qp_capture(118);
    assert(g_qp_stage==1 && !g_qp_errors && events(9,1)==1 && events(10,1)==4);held(0);
}
static void finish(void) { held(1);qp_capture(119);assert(g_qp_stage==2);held(0); }

static void audio_begin(int);
static void audio_edge(unsigned,uint64_t);
static void audio_end(void);
static void complete(void) {
    qp_init();submit(1);consume(1,1);wr32(QP_Q+4,0xfffffffc);wr32(QP_Q+8,0xfffffffc);
    submit(10);submit(11);assert(!g_qp_count && !g_qp_errors);
    unsigned char base[0x240];memcpy(base,(void *)(uintptr_t)QP_Q,sizeof base);
    held(1);qp_capture(118);assert(g_qp_stage==1 && !g_qp_errors);
    assert(!memcmp(base,(void *)(uintptr_t)QP_Q,sizeof base));held(0);
    for(int pass=0;pass<2;pass++) {
        int stage=pass?3:1;
        if(audio_fixture_regions)audio_begin(0);
        submit(20);assert_payload(last_event(1),20);assert_payload(last_event(2),20);
        submit(21);assert_payload(last_event(1),21);assert_payload(last_event(2),21);
        submit(22);assert_payload(last_event(1),22);
        assert(events(1,stage)==3 && events(2,stage)==2 && events(3,stage)==1 && events(4,stage)==3);
        QpEvent *rejected=last_event(3);assert(rejected->value==4 && rejected->p==0 && rejected->c==0xfffffffc);
        for(int i=0;i<4;i++) {
            int committed=events(8,stage);consume(1,i<3);
            assert_payload(last_event(6),(unsigned)(i<2?10+i:18+i));
            assert(last_event(6)->arg==0x1234abcd && last_event(6)->target==SINK_TARGET);
            assert(events(8,stage)==committed+(i<3));
        }
        assert(g_qp_consumer.pending && rd32(QP_Q+4)==0 && rd32(QP_Q+8)==0);
        unsigned char end_bytes[0x240];memcpy(end_bytes,(void *)(uintptr_t)QP_Q,sizeof end_bytes);
        if(audio_fixture_regions){audio_edge(1,HOSTFN_BASE);audio_edge(2,HOSTFN_BASE);audio_end();}
        held(1);qp_capture(119);assert(!memcmp(end_bytes,(void *)(uintptr_t)QP_Q,sizeof end_bytes));
        assert(!g_qp_consumer.pending && events(8,stage)==4 && !g_qp_errors);
        assert(events(9,stage)==2 && events(10,stage)==8);
        if(!pass) {
            assert(g_qp_stage==2);qp_load_begin(118);assert(events(11,2)==1);
            memcpy((void *)(uintptr_t)QP_Q,base,sizeof base);qp_load_ready(118);assert(g_qp_stage==3 && !g_qp_errors);
            assert(!memcmp(base,(void *)(uintptr_t)QP_Q,sizeof base));held(0);
        }
    }
    assert(g_qp_stage==4);
    /* Every boundary includes callback/context, pair fields, and all four slots. */
    QpEvent *end=last_event(9);assert(end->value==4 && end->p==0 && end->c==0);
    assert(end->target==SINK_TARGET && end->arg==0x1234abcd && end->a==(audio_fixture_log_identity?PRODUCER:0x1111222233334444ULL) && end->lr==1);
    assert(end->b==(audio_fixture_log_identity?QP_Q:0x5555666677778888ULL));
    LONG last_original_token=0,first_replay_token=0;unsigned boundary_kind=0;
    for(int i=0;i<g_qp_count;i++) {
        QpEvent *e=&g_qp_events[i];assert(e->ready);
        if(e->kind==9)boundary_kind=e->value;
        if(e->stage==1 && e->token>last_original_token)last_original_token=e->token;
        if(e->stage==3 && e->token && !first_replay_token)first_replay_token=e->token;
        if(e->kind==10) {
            int closing=boundary_kind==2 || boundary_kind==4;
            if(e->value<2)assert_payload(e,10+e->value);
            else if(closing)assert_payload(e,18+e->value);
            else for(int j=0;j<8;j++)assert(!e->payload[j]);
        }
    }
    assert(first_replay_token>last_original_token);
    qp_drain();assert(!log_count);held(0);g_rg_kept=1;qp_drain();assert(!log_count);
    g_rg_kept=0;qp_drain();assert(log_count==g_qp_count+2 && g_qp_reported);
    int old=log_count;qp_drain();assert(log_count==old);fputs(log_text,stdout);
}
static void pending_case(const char *mode) {
    start();submit(20);int before=events(8,1);consume(0,0);
    assert(g_qp_consumer.pending && !g_qp_consumer.active && events(7,1)==1 && events(8,1)==before);
    if(!strcmp(mode,"pending-invalid")) {
        consumer.x[30]=TICK_LR;r1_queue_tick(&consumer);
        assert((g_qp_errors&QP_PENDING) && g_qp_consumer.pending && events(8,1)==before);
        InterlockedExchange(&g_qp_errors,0);wr32(QP_Q+8,rd32(QP_Q+8)+2);r1_queue_tick(&consumer);
        assert((g_qp_errors&QP_PENDING) && g_qp_consumer.pending && events(8,1)==before);return;
    }
    wr32(QP_Q+8,rd32(QP_Q+8)+1);
    if(!strcmp(mode,"pending-held")) { held(1);qp_capture(119); }
    else if(!strcmp(mode,"pending-next")) {
        submit(21);tid=202;prepare_consumer(&consumer);SetLastError(ENTRY_ERROR);call_indirect(&consumer,SINK_TARGET);
        assert(events(8,1)==before+1 && g_qp_consumer.pending);wr32(QP_Q+8,rd32(QP_Q+8)+1);
        consumer.x[30]=TICK_LR;os_GetSystemTick(&consumer);assert(events(8,1)==before+2);
    } else {
        consumer.x[30]=TICK_LR+4;r1_queue_tick(&consumer);assert(g_qp_consumer.pending);
        consumer.x[30]=TICK_LR;Ctx snapshot=consumer;os_GetSystemTick(&consumer);
        snapshot.x[0]=2361600;assert(!memcmp(&snapshot,&consumer,sizeof consumer) && GetLastError()==444);
    }
    assert(!g_qp_consumer.pending && !g_qp_errors && events(8,1)>=before+1);
}
static void stale(void) {
    start();submit(20);tid=202;prepare_consumer(&consumer);long old=r1_queue_dispatch_enter(&consumer,SINK_TARGET);assert(old);
    finish();assert(g_qp_errors&QP_BOUNDARY);held(1);qp_load_begin(118);qp_load_ready(118);
    assert(g_qp_stage==3 && (g_qp_errors&QP_BOUNDARY));
    QpOperation snapshot=g_qp_consumer;int n=g_qp_count;r1_queue_dispatch_exit(&consumer,old);
    assert((g_qp_errors&QP_STALE) && !memcmp(&snapshot,&g_qp_consumer,sizeof snapshot) && g_qp_count==n);
    /* A restored old local must not clear a newer operation's active bit. */
    InterlockedExchange(&g_qp_consumer.active,0);tid=202;prepare_consumer(&consumer);
    long fresh=r1_queue_dispatch_enter(&consumer,SINK_TARGET);assert(fresh>old);
    snapshot=g_qp_consumer;n=g_qp_count;r1_queue_dispatch_exit(&consumer,old);
    assert(!memcmp(&snapshot,&g_qp_consumer,sizeof snapshot) && g_qp_count==n && g_qp_consumer.active);
}
static void inflight_start(void) {
    qp_init();submit(20);assert(!g_qp_count);
    tid=202;prepare_consumer(&consumer);
    long token=r1_queue_dispatch_enter(&consumer,SINK_TARGET);
    assert(token && g_qp_consumer.active && !g_qp_count && !g_qp_stage);
    held(1);qp_capture(118);
    assert(g_qp_stage==1 && (g_qp_errors&QP_BOUNDARY) && g_qp_consumer.active);
    int count=g_qp_count;tid=202;r1_queue_dispatch_exit(&consumer,token);
    assert((g_qp_errors&QP_STALE) && g_qp_count==count && g_qp_consumer.active);
}
static void overlap(int allowed) {
    start();
    if(allowed) { behavior=NEST_CONSUMER;submit(20);assert(!g_qp_errors && events(2,1)==1 && events(8,1)==1);return; }
    behavior=NEST_PRODUCER;submit(20);assert(g_qp_errors&QP_OVERLAP);
    /* Persistent actor/context ownership refuses replacement between operations. */
    QpOperation saved=g_qp_producer;behavior=NORMAL;tid=404;prepare_producer(&foreign,33);
    long token=qp_enter(&g_qp_producer,&foreign);assert(!token && (g_qp_errors&QP_IDENTITY));
    assert(g_qp_producer.actor==saved.actor && g_qp_producer.ctx==saved.ctx && g_qp_producer.token==saved.token);
}
static void rejection(const char *mode) {
    start();wr32(QP_Q+4,1);wr32(QP_Q+8,0xfffffffd);
    if(!strcmp(mode,"missing-signal")) {
        wr32(QP_Q+4,rd32(QP_Q+8));behavior=OMIT_SIGNAL;submit(20);
        assert((g_qp_errors&QP_SIGNAL) && !events(2,1));
        InterlockedExchange(&g_qp_errors,0);wr32(QP_Q+4,rd32(QP_Q+8)+4);behavior=BAD_HI;submit(21);
        assert(g_qp_errors&QP_SIGNAL);return;
    }
    if(!strcmp(mode,"unqualified-inputs")) {
        prepare_producer(&producer,20);producer.x[0]=1;producer.x[1]=3;producer.x[30]++;
        int queries=query_reads;tid=101;SetLastError(ENTRY_ERROR);qp_producer_hook(&producer,NULL);
        assert(query_reads==queries && (g_qp_errors&QP_IDENTITY) && !(g_qp_errors&QP_READ));return;
    }
    unsigned char before[128];memcpy(before,(void *)(uintptr_t)(QP_Q+0x138),sizeof before);
    submit(20);assert(!g_qp_errors && events(3,1)==1 && !events(2,1) && !g_qp_producer.active);
    QpEvent *e=last_event(3);assert(e->value==4 && e->p==1 && e->c==0xfffffffd && cond(&producer,8));
    assert(!memcmp(before,(void *)(uintptr_t)(QP_Q+0x138),sizeof before));
}
static void signal_identity(void) {
    start();tid=101;prepare_producer(&producer,20);long token=qp_enter(&g_qp_producer,&producer);assert(token);
    producer.x[0]=EVENT;producer.x[8]=rd32(QP_Q+4)+1;
    r1_queue_signal(&producer,1400);assert(!g_qp_producer.accepted && !g_qp_errors);
    producer.x[0]++;r1_queue_signal(&producer,1401);assert(!g_qp_producer.accepted);producer.x[0]--;
    tid=404;r1_queue_signal(&producer,1401);assert((g_qp_errors&QP_SIGNAL) && !g_qp_producer.accepted);
    tid=101;InterlockedExchange(&g_qp_errors,0);r1_queue_signal(&producer,1401);
    assert(g_qp_producer.accepted && events(2,1)==1 && !g_qp_errors);
    r1_queue_signal(&producer,1401);assert((g_qp_errors&QP_SIGNAL) && events(2,1)==1);
}
static void dispatch_identity(void) {
    start();tid=101;prepare_producer(&producer,20);Ctx before=producer;
    assert(!r1_queue_dispatch_enter(&producer,PRODUCER+4));
    assert((g_qp_errors&QP_IDENTITY) && last_event(5)->target==PRODUCER+4 && !memcmp(&before,&producer,sizeof before));
    InterlockedExchange(&g_qp_errors,0);tid=202;prepare_consumer(&consumer);consumer.x[25]++;
    long token=r1_queue_dispatch_enter(&consumer,NRO_CALLBACK);
    assert(token && (g_qp_errors&QP_IDENTITY) && last_event(6)->target==NRO_CALLBACK);
}
static void consumer_identity(void) {
    start();tid=202;prepare_consumer(&consumer);
    long token=r1_queue_dispatch_enter(&consumer,SINK_TARGET);assert(token);
    QpOperation saved=g_qp_consumer;int count=g_qp_count;
    assert(!r1_queue_dispatch_enter(&consumer,SINK_TARGET));
    assert((g_qp_errors&QP_OVERLAP) && !memcmp(&saved,&g_qp_consumer,sizeof saved) && count==g_qp_count);
    /* A distinct callback context on the same actor also refuses ownership. */
    InterlockedExchange(&g_qp_consumer.active,0);prepare_consumer(&foreign);
    assert(!r1_queue_dispatch_enter(&foreign,SINK_TARGET) && (g_qp_errors&QP_IDENTITY));
    assert(g_qp_consumer.ctx==saved.ctx && g_qp_consumer.actor==saved.actor && g_qp_consumer.token==saved.token);
}
static void foreign_consumer(void) {
    start();submit(20);consume(1,0);assert(g_qp_consumer.pending);
    QpOperation saved=g_qp_consumer;int count=g_qp_count;LONG sequence=g_qp_seq;
    tid=404;consumer.x[30]=TICK_LR;r1_queue_tick(&consumer);
    assert((g_qp_errors&QP_IDENTITY) && !memcmp(&saved,&g_qp_consumer,sizeof saved) && count==g_qp_count);
    prepare_consumer(&foreign);assert(!r1_queue_dispatch_enter(&foreign,SINK_TARGET));
    assert(!memcmp(&saved,&g_qp_consumer,sizeof saved) && count==g_qp_count && sequence==g_qp_seq);
    tid=202;consumer.x[30]=TICK_LR;r1_queue_tick(&consumer);
    assert(!g_qp_consumer.pending && events(8,1)==1);
}
static void unheld_boundaries(void) {
    start();int count=g_qp_count;DWORD protection;
    void *page=(void *)(uintptr_t)(QP_Q&~0xfffULL);
    assert(VirtualProtect(page,4096,PAGE_NOACCESS,&protection));
    /* These calls must refuse before reading P/C, slots, or pending state. */
    qp_capture(119);qp_load_begin(118);qp_load_ready(118);qp_capture(119);
    assert(g_qp_stage==4 && (g_qp_errors&QP_BOUNDARY) && g_qp_count==count+1);
    assert(events(9,1)==1 && !events(9,3));
    assert(VirtualProtect(page,4096,protection,&protection));
}
static void bounded(void) {
    start();QpEvent *partial=qp_event(12,123,NULL);assert(partial && !partial->ready);
    for(int i=g_qp_count;i<QP_CAP;i++)qp_publish(qp_event(12,i,NULL));
    QpEvent first=g_qp_events[0],last=g_qp_events[QP_CAP-1];
    assert(!qp_event(12,999,NULL) && (g_qp_errors&QP_OVERFLOW) && g_qp_count==QP_CAP+1);
    assert(!memcmp(&first,&g_qp_events[0],sizeof first) && !memcmp(&last,&g_qp_events[QP_CAP-1],sizeof last));
    InterlockedExchange(&g_qp_stage,4);held(0);qp_drain();
    assert(g_qp_reported && log_count==QP_CAP+2 && strstr(log_text,"ready=0\n") && strstr(log_text,"errors=32"));
    fputs(log_text,stdout);
}
static void drain_active(void) {
    start();InterlockedExchange(&g_qp_consumer.active,1);g_qp_consumer.pending=123;
    InterlockedExchange(&g_qp_stage,4);held(0);qp_drain();
    assert(g_qp_reported && strstr(log_text,"consumer_active=1 pending=-1 stage=4"));
}
static void protected_read(void) {
    start();uint32_t output[8];memset(output,0x5a,sizeof output);uint32_t before[8];memcpy(before,output,sizeof before);
    unsigned char *p=VirtualAlloc(NULL,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);assert(p);
    DWORD old;assert(VirtualProtect(p+4096,4096,PAGE_NOACCESS,&old));
    assert(!qp_copy(output,(uint64_t)(uintptr_t)(p+4096),16));assert(g_qp_errors&QP_READ);
    assert(!qp_copy(output,(uint64_t)(uintptr_t)(p+4096-8),16));
    assert(!qp_copy(output,UINT64_MAX-8,16) && !memcmp(output,before,sizeof output));
    assert(VirtualFree(p,0,MEM_RELEASE));
}
static void dispatch_families(void) {
    start();uint64_t targets[]={SINK_TARGET,HOSTFN_BASE,HOSTFN_BASE+16,IMPORT_BASE+42*IMPORT_SLOT,
        NRO_CALLBACK,SDK_CALLBACK,FALLBACK_CALLBACK};
    preserve_check=1;
    for(unsigned i=0;i<sizeof targets/sizeof targets[0];i++) {
        tid=202;prepare_consumer(&consumer);Ctx before=consumer,expected=consumer;
        SetLastError(ENTRY_ERROR);fixture_callback(&expected);int called=callback_calls;
        SetLastError(ENTRY_ERROR);call_indirect(&consumer,targets[i]);
        assert(callback_calls==called+1 && GetLastError()==RESULT_ERROR && !memcmp(&expected,&consumer,sizeof consumer));
        QpEvent *enter=last_event(6);assert(enter->target==targets[i] && enter->ctx==(uint64_t)(uintptr_t)&consumer);
        assert(enter->arg==before.x[2] && enter->lr==CALLBACK_LR && g_qp_consumer.pending);
        wr32(QP_Q+8,rd32(QP_Q+8)+1);consumer.x[30]=TICK_LR;os_GetSystemTick(&consumer);
        assert(!g_qp_consumer.pending && !g_qp_errors && GetLastError()==444);
    }
}
static void preservation(void) {
    start();preserve_check=1;tid=101;prepare_producer(&producer,20);
    Ctx saved=producer,expected=producer;unsigned char queue_before[0x240];
    memcpy(queue_before,(void *)(uintptr_t)QP_Q,sizeof queue_before);
    InterlockedExchange(&g_qp_on,0);SetLastError(ENTRY_ERROR);fixture_producer(&expected);
    assert(GetLastError()==RESULT_ERROR);memcpy((void *)(uintptr_t)QP_Q,queue_before,sizeof queue_before);
    InterlockedExchange(&g_qp_on,1);producer=saved;SetLastError(ENTRY_ERROR);qp_producer_hook(&producer,NULL);
    assert(GetLastError()==RESULT_ERROR && !memcmp(&expected,&producer,sizeof producer) && !g_qp_errors);
    assert(last_event(1)->lr==SUBMIT_LR && last_event(2)->lr==SUBMIT_LR && last_event(2)->value==rd32(QP_Q+4));
    assert_payload(last_event(1),20);assert_payload(last_event(2),20);
    /* Normal imports still expose legitimate handler changes to the whole Ctx. */
    tid=202;prepare_consumer(&consumer);expected=consumer;
    SetLastError(ENTRY_ERROR);fixture_callback(&expected);SetLastError(ENTRY_ERROR);host_import(&consumer,42);
    assert(GetLastError()==RESULT_ERROR && !memcmp(&expected,&consumer,sizeof consumer));
}
static void disabled(const char *mode) {
    _putenv(!strcmp(mode,"unset")?"SSBU_RB_QUEUE_PROBE=":"SSBU_RB_QUEUE_PROBE=0");qp_init();
    assert(!g_qp_on && !installs);g_qp_original=fixture_producer;
    preserve_check=1;submit(20);consume(1,1);held(1);qp_capture(118);qp_capture(119);qp_load_begin(118);qp_load_ready(118);
    held(0);qp_drain();assert(!g_qp_stage && !g_qp_count && !g_qp_seq && !g_qp_errors && !log_count && !query_reads);
}
uint64_t ga(uint64_t address){return address;}
static uint64_t g_ra_site=0x123;
static int g_ra_off,g_ra_phase,g_ra_skip,g_ra_wd_pause,g_ra_wd_base,g_ra_skipped_kicks,h2_calls;
static long long g_ff,g_ra_wd_fired;
static void ra_workers_hold(void){assert(0);}
static int ra_fight_on(void){return 1;}
static void ra_step(Ctx *c){(void)c;}
static void ra_workers_release(void){held(0);}
static void ra_watchdog_signal(void){}
static void r1_protection_observation_drain(void){}
static void rgs_clock_drain(void){}
static int rgs_skip_now(void){return 0;}
void r1_wrote(uint64_t p,uint64_t n){(void)p;(void)n;assert(0);}
static void g_orig_kick2(Ctx *c){assert(GetLastError()==ENTRY_ERROR);h2_calls++;c->x[0]=87;SetLastError(RESULT_ERROR);}
/* H2_SOURCE */
static void h2_drain(void){
    start();InterlockedExchange(&g_qp_stage,4);held(1);
    Ctx c;memset(&c,0x53,sizeof c);c.x[30]=g_ra_site;Ctx expected=c;expected.x[0]=87;
    SetLastError(ENTRY_ERROR);ra_kick2(&c,NULL);
    assert(h2_calls==1 && g_qp_reported && log_count>0 && GetLastError()==RESULT_ERROR);
    assert(!memcmp(&c,&expected,sizeof c));
}
/* AUDIO_CASES */
int main(int argc,char **argv) {
    assert(argc==2);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);init();const char *mode=argv[1];
    if(!strncmp(mode,"audio-",6)) {audio_case(mode);printf("QUEUE_SOURCE_PASS %s\n",mode);return 0;}
    if(!strncmp(mode,"bad-",4)) {
        if(!strcmp(mode,"bad-enable"))_putenv("SSBU_RB_QUEUE_PROBE=2");
        else if(!strcmp(mode,"bad-build"))g_game_build=GAME_13_0_4;
        else if(!strcmp(mode,"bad-sim"))_putenv("SSBU_RB_SIM=120,2,60");
        else if(!strcmp(mode,"bad-verify"))_putenv("SSBU_RB_SIM_VERIFY=");
        else if(!strcmp(mode,"bad-net"))_putenv("SSBU_RB_NET=1");
        else if(!strcmp(mode,"bad-skip"))_putenv("SSBU_RB_SIM_SKIP=1");
        else if(!strcmp(mode,"bad-lite"))_putenv("SSBU_RB_SIM_LITE=1");
        else if(!strcmp(mode,"bad-symbol"))strcpy(signal_name,"different-import");
        else assert(0);
        qp_init();assert(0);
    }
    else if(!strcmp(mode,"complete"))complete();
    else if(!strncmp(mode,"pending-",8))pending_case(mode);
    else if(!strcmp(mode,"stale"))stale();
    else if(!strcmp(mode,"inflight-start"))inflight_start();
    else if(!strcmp(mode,"producer-consumer-overlap"))overlap(1);
    else if(!strcmp(mode,"producer-overlap"))overlap(0);
    else if(!strcmp(mode,"missing-signal") || !strcmp(mode,"rejected") || !strcmp(mode,"unqualified-inputs"))rejection(mode);
    else if(!strcmp(mode,"signal-identity"))signal_identity();
    else if(!strcmp(mode,"dispatch-identity"))dispatch_identity();
    else if(!strcmp(mode,"consumer-identity"))consumer_identity();
    else if(!strcmp(mode,"foreign-consumer"))foreign_consumer();
    else if(!strcmp(mode,"unheld-boundaries"))unheld_boundaries();
    else if(!strcmp(mode,"bounded"))bounded();
    else if(!strcmp(mode,"drain-active"))drain_active();
    else if(!strcmp(mode,"protected-read"))protected_read();
    else if(!strcmp(mode,"dispatch-families"))dispatch_families();
    else if(!strcmp(mode,"preservation"))preservation();
    else if(!strcmp(mode,"h2-drain"))h2_drain();
    else if(!strcmp(mode,"disabled") || !strcmp(mode,"unset"))disabled(mode);
    else assert(0);
    printf("QUEUE_SOURCE_PASS %s\n",mode);return 0;
}
