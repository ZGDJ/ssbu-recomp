/* Full production correction coordinator; scripted ring/network/clock boundaries. */
#include <windows.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "rb.h"
#define LOG(...) fprintf(stderr,__VA_ARGS__)
/* CONSTANT */
typedef struct {uint64_t x[32];} Ctx;
typedef struct {long long frame;unsigned char bytes[32];} Slot;
static Slot slots[RG_MAXSLOT],saved_slots[RG_MAXSLOT];
static Ctx guest,before;
static unsigned char pages[4096],history[128];
static int g_rg_count=3,g_rg_ready=1,g_rg_nomem,g_rg_keep,g_rg_short,g_rg_keep_on;
static long long g_rg_need=-1,g_ff=100,g_rgs_next=10,g_ra_wd_fired;
static int g_ra_wh_on=1,g_ra_wd_pause,g_ra_wd_base,g_ra_phase,g_rgs_left,g_ra_after_quiet;
static int g_rgs_lastlite,g_rgs_skip,g_rgs_lite;
static volatile long long g_unwind_trace_frame;
static int expected_fatal,loads,captures,releases,hashes,drains,load_result=1,inject_at=1,queued=7,expected_pending=7;
static int allow_captures,held=1,details,checks,returned,mode;
static long long loaded=-1,confirmed=10;
static double now_ms(void){return 1000;}
static ULONG64 rgs_cyc_now(void){return 0;}
static int rbn_init_only(void){return 0;}
static Slot *rg_slot(int i){assert(i>=0&&i<g_rg_count);return slots+i;}
static long long r1_ring_oldest(void){return g_rg_count?slots[0].frame:-1;}
static int r1_ring_capture(long long i,Ctx*c);
static void fatal_sink(void);
#define abort fatal_sink
/* GLOBALS */
#define HR 32
static int g_remote=1;static long long g_hfinal_upto=4,g_peer_check_f;
static FILE *g_hlog;static long long g_hframe[HR];static uint64_t g_hash[HR],g_peer_check;
int rb_input_remote_latest(int p){assert(p==1);return confirmed;}
static void detail_frame(long long f){assert(f>g_hfinal_upto);details++;}
static void on_check(long long f,uint64_t h){(void)f;(void)h;checks++;}
static void fatal_sink(void){
 assert(expected_fatal&&!returned&&!releases&&held&&g_hfinal_upto==4&&!details&&!checks);
 assert(g_rbg_pend==expected_pending&&loads<=1&&captures==allow_captures);
 assert(!memcmp(&guest,&before,sizeof guest)&&!memcmp(slots,saved_slots,sizeof slots));
 for(int i=0;i<4096;i++)assert(pages[i]==0x35);
 for(int i=0;i<128;i++)assert(history[i]==0x72);
 puts("CORRECTION_FATAL_INTACT_NO_FINALIZE");fflush(stdout);_Exit(73);
}
static int r1_ring_capture(long long i,Ctx*c){(void)i;assert(c==&guest);captures++;if(expected_fatal&&g_rbg_keep==1)assert(g_rg_need<=expected_pending-1);return 1;}
int r1_ring_rebase(long long i,Ctx*c){return r1_ring_capture(i,c);}
static int r1_ring_load(long long f,Ctx*c){assert(c==&guest);loads++;loaded=f;assert(g_rbg_pend==expected_pending);return load_result;}
static void r1_ring_hold(void){held=1;}
static void r1_ring_let_go(void){releases++;held=0;}
int rbn_on(void){return 1;}void rbn_init(void){}void rbn_start(long long f){(void)f;}int rbn_started(void){return 1;}
int rbn_local_player(void){return 0;}int rbn_ahead(void){return 7;}int rbn_delay(void){return 0;}int rbn_rtt_ms(void){return 0;}double rbn_offset_ms(void){return 0;}
void rbn_local_pad(long long f,RbPad p){(void)f;(void)p;}RbPad rbn_pad(int p,long long f){(void)p;(void)f;RbPad v={0};return v;}
void rbn_drain(long long i){(void)i;drains++;}
int rbn_take_mismatch(void){return drains==inject_at?queued:0;}
void rbn_put_mismatch(int m){queued=m;}
long long rbn_confirmed(void){return confirmed;}int rbn_peer_gone(void){return 0;}
void rbn_pass_hash(long long f){(void)f;hashes++;}double rbn_pace_extra(long long f){(void)f;return 0;}
void rbn_report(FILE*f,long long n){(void)f;(void)n;}void rbn_resend(void){}void rbn_status(char*s,size_t n){snprintf(s,n,"fixture");}
void rbn_hello(void){}int rbn_peer_started(void){return 1;}void rbn_choose_delay(void){}
int rbn_match_cancelled(void){return 0;}void rbn_match_reset(void){}int rbn_match_number(void){return 1;}
void rbn_set_lockstep(int n){(void)n;}int rbn_loop(void){return 0;}void input_mark(const char*s){(void)s;}
static void rbg_wait_until(double t){(void)t;assert(!expected_fatal||(mode==12&&!loads));}
long nnunwind_events(void){static long calls;return mode==18?calls++:0;}
/* SOURCE */
int main(int argc,char**argv){
 assert(argc==2);mode=atoi(argv[1]);
 memset(&guest,0x23,sizeof guest);before=guest;memset(pages,0x35,sizeof pages);memset(history,0x72,sizeof history);
 slots[0].frame=2;slots[1].frame=6;slots[2].frame=9;
 g_rbg_in_match=1;g_rbg_wdfix=1;g_rbg_keep=2;g_rbg_pace=0;g_rbg_test_f=-1;
 expected_fatal=mode!=0&&mode!=9&&mode!=10&&mode!=14&&mode!=16;
 if(mode==1||mode==4)g_rg_count=0;
 if(mode==2||mode==5||mode==11)load_result=0;
 if(mode==3||mode==6||mode==7||mode==8||mode==12||mode==13||mode==15||mode==17||mode==18||mode==19||mode==23)load_result=-1;
 if(mode==7){inject_at=2;allow_captures=1;}
 if(mode==8){g_rbg_keep=1;allow_captures=1;}
 if(mode==9){queued=0;expected_pending=0;}
 if(mode==10){g_ra_phase=2;g_rgs_left=1;g_rbg_recap=1;queued=0;expected_pending=0;}
 if(mode==11){g_rbg_noring=1;}
 if(mode==12){queued=0;g_rbg_test_f=10;g_rbg_test_k=4;g_rbg_test_ms=0;allow_captures=1;expected_pending=7;}
 if(mode==13){inject_at=2;g_rbg_noring=1;}
 if(mode==14){g_rbg_pend=4;expected_pending=4;}
 if(mode==20)expected_pending=0;
 if(mode==22){slots[0].frame=8;slots[1].frame=9;slots[2].frame=10;}
 if(mode==23){g_rbg_pend=4;expected_pending=4;g_rbg_keep=1;allow_captures=1;}
 if(mode==18){queued=0;allow_captures=1;_putenv_s("SSBU_RB_NET_TEST_EH","4,0");}
 if(mode==19){queued=0;_putenv_s("SSBU_RB_NET_TEST_SCHED","10:6");}
 if(mode==17)g_rbg_keep=0;
 if(mode==15){g_rbg_pend=4;expected_pending=4;}
 memcpy(saved_slots,slots,sizeof slots);
 if(mode<=3||mode==14||mode==15||mode==20||mode==21||mode==22){int result=rbg_rollback(&guest,mode==21?(long long)INT_MAX+10:10,mode==20?0:7);assert(result==1);}
 else rbg_step_body(&guest);
 returned=1;assert(!expected_fatal);
 if(mode==0||mode==14||mode==16){assert(loads==1&&loaded==(mode==14?2:6)&&!g_rbg_pend&&g_ra_phase==2&&g_rgs_next==loaded+1&&g_rgs_left==10-loaded&&!releases&&g_hfinal_upto==4);}
 else {assert(!loads&&g_hfinal_upto==10&&releases==1&&g_ra_phase==0&&g_rgs_next==11);}
 puts("CORRECTION_PASS");return 0;
}
