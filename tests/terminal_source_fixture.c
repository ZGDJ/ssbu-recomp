/* Extends correction_source_fixture.c's scripted boundaries. */
static int g_started=1,g_peer_started=1,g_peer_mode,g_sent_newest;
static long long g_f0,g_peer_ack,g_stat_pred,g_stat_padget,g_stat_mis,g_ts_n,g_hlines,g_lacc_n,g_desync,g_check_ok,g_desync_first,g_padcheck_bad,g_padcheck_first,g_cur,g_rx_oldmatch;
static double g_ts_extra;static int g_ts_left;
static uint64_t g_hacc;static int g_acc_n[8],g_acc_var[8],g_un[8],g_unl[8];
static SRWLOCK g_hs_lock=SRWLOCK_INIT,g_rq_lock=SRWLOCK_INIT;
static int g_hs_mine_ok=1,g_hs_blk_done=1,g_hs_peer_have[8],g_rq_tail,g_rq_head=7,g_tsq_n=5,g_hs_cancelled,g_match_n=1;
static void menu_notice(const char*s){(void)s;}
void start_boundary(long long f){assert(f==0);g_started=1;g_rg_count=3;}
static int g_rg_head,g_rgp_main,g_rgp_seg,g_rgs_prof,g_rgs_polls_cur;
static long long g_rgs_multi,g_rgs_npl[2],g_rgs_npass[2],g_rgs_real_since,g_rgs_done,g_rgs_nocap,g_rg_caps;
static double g_rgs_pass_t0,g_rgs_cyc[2],g_rgs_pl[2],g_rgs_pass[2],g_rgs_plv[2][32],g_rgs_pass_v[2][32],g_ra_t_mark,g_rg_last[2];
static int g_rgs_nplv[2],g_rgs_pass_nv[2],g_rgv_target=-1,g_rgs_warm=30,g_rgs_n=30,g_rgs_ki,g_rgs_k=7;
static long long g_rgs_ksum[RG_MAXSLOT];static ULONG64 g_rgs_cyc0;
#define RG_NST 128
static void rgs_samp_start(void){}static void rgv_after(void){}
static int ra_fight_on(void){return fight;}
static void debug_writer_probe_end(long long i){(void)i;}
static void ls_fight_off(void){assert(g_rbg_in_match!=1||g_rbg_terminal_commit);learned_closes++;}
static void rbg_report(void){reports++;}
static void r1_ring_release(void);
static void rg_slot_drop(Slot*s,int pool){assert(pool==1&&g_rbg_terminal_commit);drops++;memset(s->bytes,0,sizeof s->bytes);}
static void rbg_step(Ctx*c);
static void intact(void){
 assert(held&&!releases);
 assert(!drops&&!marks&&!reports&&!learned_closes&&g_rg_count==3&&g_started==1&&g_rq_tail==0&&g_tsq_n==5);
 assert(g_hfinal_upto==4&&!details&&!checks&&!g_rbg_terminal_commit);
 assert(!memcmp(&guest,&before,sizeof guest)&&!memcmp(slots,saved_slots,sizeof slots));
 for(int i=0;i<4096;i++)assert(pages[i]==0x35);
 for(int i=0;i<128;i++)assert(history[i]==0x72);
}
static void fatal_sink(void){assert(expected_fatal);intact();assert(loads<=1&&!captures);puts("TERMINAL_FATAL_INTACT");fflush(stdout);_Exit(74);}
static void rbg_wait_until(double t){
 (void)t;intact();assert(g_rbg_in_match==1&&g_rgs_next==10&&g_ra_wd_pause==1);assert(++waits==1);
 confirmed=10;
 if(mode==3){queued=7;inject_at=drains+1;}
 if(mode==7)gone=1;
}
/* TERMINAL_SOURCE */
static void rbg_step(Ctx*c){rbg_step_body(c);}
int main(int argc,char**argv){
 assert(argc==2);mode=atoi(argv[1]);
 memset(&guest,0x23,sizeof guest);before=guest;memset(pages,0x35,sizeof pages);memset(history,0x72,sizeof history);
 slots[0].frame=2;slots[1].frame=6;slots[2].frame=9;memset(slots[0].bytes,0x51,32);memcpy(saved_slots,slots,sizeof slots);
 g_rbg_in_match=1;g_rbg_wdfix=1;g_rbg_keep=2;g_rbg_pace=0;g_rbg_test_f=-1;g_rbg=1;
 g_peer_check_f=10;g_peer_check=123;
 queued=0;expected_pending=7;
 expected_fatal=mode==4||mode==5||mode==6||mode==7||mode==8||mode==9||mode==10||mode==12;
 if(mode==0||mode==4||mode==5||mode==6||mode==9||mode==14)queued=7;
 if(mode==1||mode==3||mode==7)confirmed=6;
 if(mode==4)load_result=-1;
 if(mode==5)load_result=0;
 if(mode==6){slots[0].frame=8;slots[1].frame=9;slots[2].frame=10;memcpy(saved_slots,slots,sizeof slots);}
 if(mode==8)cancelled=1;
 if(mode==9)g_rbg_noring=1;
 if(mode==12)g_ra_off=1;
 if(mode==13){g_ra_phase=2;g_rgs_left=4;}
 if(mode==10)rbg_fight_off();else rgs_step(&guest);
 assert(!expected_fatal);
 if(mode==0||mode==3||mode==14){
  intact();assert(loads==1&&loaded==6&&g_ra_phase==2&&g_rgs_left==4&&g_rgs_next==7&&fight);
  if(mode==14){
   rgs_step(&guest);assert(g_rgs_next==8&&g_rgs_left==3);
   fight=0;queued=7;inject_at=drains+1;rgs_step(&guest);
   intact();assert(loads==2&&loaded==6&&g_rgs_next==7&&g_rgs_left==2&&g_ra_phase==2);
   rgs_step(&guest);assert(g_rgs_next==8&&g_rgs_left==1);
   fight=0;g_peer_check_f=8;rgs_step(&guest);
  }else{
  /* Corrected replay survives: no terminal cleanup; exact normal coordinator completes it. */
  for(int f=7;f<=10;f++)rgs_step(&guest);
  assert(!drops&&!marks&&!learned_closes&&g_rbg_in_match==1&&g_rgs_next==11&&g_ra_phase==0&&g_hfinal_upto==10);
  fight=0;confirmed=11;rgs_step(&guest);
  }
 }
 assert(drops==3&&marks==1&&reports==1&&g_rg_count==0&&g_rbg_in_match==0&&g_rbg_rebase==1&&!g_started&&g_rq_tail==7&&!g_tsq_n&&!g_rbg_terminal_commit);
 assert(checks==1&&g_peer_check_f==0&&g_hfinal_upto==0);
 rgs_step(&guest);assert(drops==3&&marks==1&&reports==1); /* duplicate off dispatch */
 if(mode==11){
  /* A later base is a new match, and can commit once independently. */
  fight=1;g_rbg_basefix=1;rgs_step(&guest);
  assert(g_rbg_in_match==1&&g_started&&g_rgs_next==1&&g_rg_count==3);
  g_rgs_next=20;confirmed=20;fight=0;
  rgs_step(&guest);assert(drops==6&&marks==2&&reports==2&&!g_rbg_in_match);
 }
 puts("TERMINAL_PASS");return 0;
}
