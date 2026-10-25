/* Production decisions; scripted platform, configuration and ring boundaries. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef struct { uint64_t x[32]; } Ctx;
static Ctx guest, before;
static unsigned char pages[4096], history[128];
static int holds, mutations, successes, ring_calls, frame_calls, trace_calls;
static int expected_fatal, ini, net, init_only;
static const char *r1, *ra, *sim, *submit;
static const char *env(const char *n) {
 if(!strcmp(n,"SSBU_R1")) return r1;
 if(!strcmp(n,"SSBU_RUNAHEAD")) return ra;
 if(!strcmp(n,"SSBU_RB_SIM")) return sim;
 if(!strcmp(n,"SSBU_RUNAHEAD_MODE")) return submit;
 return NULL;
}
#define getenv env
static int g_gfx_runahead;
static void gfx_options(void){g_gfx_runahead=ini;}
/* GFX_SOURCE */
static int rbn_init_only(void){return init_only;}
static int rbg_on(void){return net;}
static void oracle(void){
 assert((!expected_fatal||!frame_calls)&&!mutations&&!successes&&!holds&&!memcmp(&guest,&before,sizeof guest));
 for(int i=0;i<4096;i++)assert(pages[i]==0x35);
 for(int i=0;i<128;i++)assert(history[i]==0x72);
}
static void fatal_sink(void){oracle();assert(expected_fatal);puts("LEGACY_FATAL_INTACT");fflush(stdout);exit(71);}
#define abort fatal_sink
#define LOG(...) fprintf(stderr,__VA_ARGS__)
/* RING_CONSTANT */
#define GA(x) (x)
static int g_rgs_on=-1,g_rgs_n,g_rgs_k,g_rgs_warm;
static int g_on=-1,g_n,g_k,g_p,g_c,g_cycle,g_phase,g_fast,g_mark,g_learn,g_fcheck;static void *g_ar;
static long long g_target,g_ff,g_ra_kicks;
static double g_qpf;static FILE *g_log;
static int g_ra_fe_kind;static double g_rap[3][4],g_ra_fe_end;static int g_rapn[3];
static double now_ms(void){return 1;}
static void rgs_step(Ctx*c){assert(c==&guest);ring_calls++;}
static volatile int g_rgp_seg;
static int g_ra,g_ra_phase,g_rgs_left,g_rgv_target=-1,g_rbg_pend;
static long long g_ra_nkind;static char g_ra_kind[4];
static int g_fe_busy,g_wait_idle,g_busy_log,g_postponed,g_save_failed,g_npad,g_pad_failed,g_k_run,g_ipad,g_prot;
static int g_fast_saved_valid,g_nfp;
static long long g_save_ff;
static double g_t_poll,g_t_fe_prev,g_st[2][3],g_t_mark,g_t_pass1,g_t_rerun;
static long long g_stn[2];
static void g_orig_frame_end(Ctx*c){(void)c;frame_calls++;}
static void fls_index_find(void){}
static void ra_frame_end(double t){(void)t;}
static void fight_trace_boundary(char k,int p){(void)k;(void)p;trace_calls++;}
static void r1_stats_now(void){}
static int fibers_idle(void){return 1;}
static void save(Ctx*c){(void)c;mutations++;}
static void mark_save(Ctx*c){save(c);}
static void fast_save(Ctx*c){save(c);}
static int fast_build(void){mutations++;return 1;}
static int pad_history_ready(void){return 1;}
static void fight_trace_fail(const char*s){(void)s;}
static void release(void){holds=0;}
static void pad_history_complete(void){successes++;}
static void verify(void){successes++;}
static void fast_report(void){}static void mark_report(void){}static void prot_report(void){}static void r1_stats_report(void){}
/* SOURCE */
int main(int argc,char**argv){
 assert(argc==2);int m=atoi(argv[1]);memset(&guest,0x23,sizeof guest);before=guest;memset(pages,0x35,sizeof pages);memset(history,0x72,sizeof history);
 expected_fatal=(m>=1&&m<=5)||(m>=10&&m<=19)||m==21;
 if(m==21){ra="1";submit="submit";}
 if(m==15)submit="submit";
 if(m==1||m==2||m==3){r1="10,8";g_fast=m==2;g_mark=m==3;}
 if(m==4)ra="1";
 if(m==5)ini=1;
 if(m==6){ini=1;ra="0";}
 if(m==7){sim="10,2,4";ra="1";ini=1;}
 if(m==8){net=1;ini=1;}
 if(m==22)sim="10,31,4";
 if(m==9){init_only=1;r1="10,8";ra="1";}
 if(m<10||m==21||m==22){int on=r1_on();assert(!expected_fatal);assert(on==(m==7||m==8||m==22));if(on){ra_step(&guest);assert(ring_calls==1);if(m==22)assert(g_rgs_k==RG_MAXSLOT-1);}oracle();}
 else if(m==10)restore(&guest);
 else if(m==11)fast_restore(&guest);
 else if(m==12)mark_restore(&guest);
 else if(m==13)ra_restore(&guest);
 else if(m==14||m==15)ra_step(&guest); /* ordinary and submit configurations: same removed legacy branch */
 else if(m>=16&&m<=19){g_fast=m==17;g_mark=m==18;g_phase=m==19?1:0;g_ff=100;r1_frame_end(&guest,NULL);}
 else if(m==20){g_ra=1;guest.x[30]=GA(0x7103747b7cull);before=guest;r1_frame_end(&guest,NULL);assert(frame_calls==1&&trace_calls==1);oracle();}
 assert(!expected_fatal);puts("LEGACY_PASS");return 0;
}
