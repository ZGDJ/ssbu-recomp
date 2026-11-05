/* Appended to the unchanged witness suite's exact-source translation, replacing
 * only its synthetic main and adding OS/CRT boundary observations. No game. */
static int scenario, requested_exit, lifecycle_draining, expected_writes = -1;
static int lifecycle_reports, capture_frozen;
static uint64_t frozen_projection;
static char frozen_bytes[RBW_BYTES]; static size_t frozen_used;

static void (*g_exit_report_hook)(FILE *);
static void (*g_plugin_report_hook)(void);
static FILE *g_trace;
#define REPORT_STUB(name) static void name(FILE *f) { (void)f; lifecycle_reports++; }
static void audit_exit_counts(void) { lifecycle_reports++; }
REPORT_STUB(print_import_summary)
REPORT_STUB(print_hostfn_summary)
REPORT_STUB(print_devinfo_summary)
REPORT_STUB(display_report)
REPORT_STUB(audio_report)
REPORT_STUB(hid_report)
REPORT_STUB(os_thread_report)
REPORT_STUB(module_coverage_report)
#undef REPORT_STUB
/* HOST_EXIT_SOURCE */

static DWORD WINAPI exit_thread(void *p) {
    (void)p; report_and_exit(requested_exit); REQUIRE(0,"EXIT_RETURNED"); return 0;
}
static void request_exit(int thread) {
    expected_writes=drain_writes;
    if(thread) {
        HANDLE t=CreateThread(NULL,0,exit_thread,NULL,0,NULL); REQUIRE(t,"EXIT_THREAD");
        WaitForSingleObject(t,15000); REQUIRE(0,"EXIT_THREAD_RETURNED");
    }
    report_and_exit(requested_exit); REQUIRE(0,"EXIT_RETURNED");
}
static void lifecycle_reject(void) {
    if(expected_writes>=0) {
        REQUIRE(drain_writes==expected_writes,"NO_EXIT_WRITE");
        REQUIRE(!lifecycle_reports,"GUARD_BEFORE_REPORTERS");
        REQUIRE(InterlockedCompareExchange(&g_wexit,0,0)==1,"EXIT_INCOMPLETE_PUBLICATION");
        fprintf(stderr,"LIFECYCLE_EXIT_REJECT no_shutdown_io=1 reports=0\n");
    }
}
static void lifecycle_io(const char *kind,FILE *f) {
    if(f!=g_hlog||disabled) return;
    REQUIRE(lifecycle_draining&&!g_ra_wh_on&&!g_rg_kept&&!g_th[0].held&&!g_th[1].held,"IO_ONLY_AFTER_RELEASE");
    REQUIRE(!g_wh2,"NO_H2_IO");
    REQUIRE(InterlockedCompareExchange(&g_wexit,0,0)==1,"NO_EARLY_CLOSE_PUBLICATION");
    fprintf(stderr,"LIFECYCLE_IO %s\n",kind);
    if(g_wsealed && ((scenario==14&&!strcmp(kind,"data-write")) ||
        (scenario==15&&!strcmp(kind,"END-write")) ||
        (scenario==16&&!strcmp(kind,"END-flush")) ||
        (scenario==17&&!strcmp(kind,"before-close")) ||
        (scenario==18&&!strcmp(kind,"after-close")))) request_exit(1);
}
static int lifecycle_ferror(FILE *f) {
    lifecycle_io(end_written?"END-error-check":"data-error-check",f);
    return (scenario==26&&g_wsealed) || (scenario==29&&end_written) ? 1 : ferror(f);
}
static uint64_t projection(void) {
    uint64_t h=0xcbf29ce484222325ull;
#define F(x) h=fh_fnv(h,&(x),sizeof(x))
    F(g_wtrace);F(g_wtrace_frame);F(g_wtrace_poll);F(g_wprev_trace);F(g_wseq);F(g_wevents);
    F(g_wfinals);F(g_wwindow);F(g_wtrace_phase);F(g_wtrace_left);F(g_wtrace_polls);F(g_wready);F(g_wh2);
    F(g_wlast);F(g_wpasses);F(g_wnpass);F(g_wactual);F(g_wactual_frame);F(g_wfinal_seq);
    F(g_wpred);F(g_wreads);F(g_wvar);F(g_wpad);F(g_wread_frame);F(g_warrival_cur);
    F(g_wmismatch);F(g_wspec);F(g_wload);F(g_wtarget);F(g_wmismatch_emitted);F(g_wcomplete);
    F(g_widle);F(g_wsubmits);F(g_wsealed);F(g_wend);F(g_wend_used);
#undef F
    return h;
}
static void checked_drain(void) {
    DWORD error=0x23456000u+(DWORD)g_rgs_next;
    SetLastError(error); lifecycle_draining=1; r1_loop_witness_drain(); lifecycle_draining=0;
    REQUIRE(GetLastError()==error,"DRAIN_LASTERROR");
}
static void held_drains(void) {
    int writes=drain_writes; size_t used=g_wused;
    /* Repeat every hold class with both native slots and overlapping holds. */
    for(int repeat=0;repeat<2;repeat++) {
        g_ra_wh_on=1; checked_drain(); g_ra_wh_on=0;
        g_rg_kept=1; checked_drain(); g_rg_kept=0;
        g_th[0].held=1; checked_drain();
        g_th[1].held=1; g_rg_kept=1; g_ra_wh_on=1; checked_drain();
        g_ra_wh_on=g_rg_kept=g_th[0].held=0; checked_drain(); g_th[1].held=0;
    }
    REQUIRE(writes==drain_writes&&used==g_wused,"HELD_NO_WRITES_OR_BYTES");
}
static void freeze_observed(void) {
    REQUIRE(g_wsealed&&!g_wclosed&&g_wused&&!end_written,"CUTOFF_IS_NOT_CLOSE");
    REQUIRE(g_wfinals==499&&g_wsubmits==499&&g_wseq==499+late,"CUTOFF_COUNTS");
    REQUIRE(!strstr(g_wbytes,"\"kind\":\"END\""),"NO_QUEUED_PREMATURE_END");
    REQUIRE(InterlockedCompareExchange(&g_wexit,0,0)==1,"PENDING_EXIT_IS_INCOMPLETE");
    frozen_projection=projection(); frozen_used=g_wused;
    memcpy(frozen_bytes,g_wbytes,g_wused); capture_frozen=1;
}
int main(int argc,char **argv) {
    REQUIRE(argc==5,"ARGS"); scenario=atoi(argv[1]);late=atoi(argv[2]);disabled=atoi(argv[3]);requested_exit=atoi(argv[4]);
    /* STARTUP_EXIT_CALL */
    if(scenario==31||scenario==32) request_exit(scenario==32);
    if(scenario==33) { expected_writes=drain_writes; return 0; }
    REQUIRE(rbn_on()&&g_loop&&g_bot_seed==7,"CONFIG");
    /* Net initialization and gameplay owners deliberately differ. */
    HANDLE t=CreateThread(NULL,0,init_thread,NULL,0,NULL); REQUIRE(t,"INIT_THREAD");
    REQUIRE(WaitForSingleObject(t,15000)==WAIT_OBJECT_0,"INIT_JOIN"); CloseHandle(t);
    g_fh_out=fopen("fight.txt","w"); REQUIRE(g_fh_out,"TRACE_OPEN"); g_fh_trace.target=500;
    Ctx guest={0}; guest.witness=0xcbf29ce484222325ull;
    frame_end(&guest,0,1);g_ra_wh_on=1;rbg_step_body(&guest);g_ra_wh_on=0;checked_drain();
    REQUIRE(g_rgs_next==1&&g_wbase==!disabled,"BASE");
    int physical=1;
    while(physical<600+late) {
        int f=(int)g_rgs_next,replay=g_ra_phase==2;physical++;
        REQUIRE(r1_poll(1)==replay,"POLL");
        RbPad p[2]={consume(0),consume(1)};
        guest.boundary=f; guest.witness=evolve(evolve(guest.witness,p[0]),p[1]);
        frame_end(&guest,f,physical);
        g_ra_wh_on=1;rbg_step_body(&guest);
        /* Actual input/coordinator drains can repeat without new arrivals. */
        rbn_drain(f); rbn_drain(f);
        g_rgs_polls_cur=0;g_ra_wh_on=0;
        if(f==5&&(scenario==10||scenario==11)) request_exit(scenario==11);
        if(f==5&&scenario==22) { expected_writes=drain_writes; return 0; }
        if(!disabled&&f==499) freeze_observed();
        if(!disabled&&capture_frozen) {
            REQUIRE(projection()==frozen_projection,"PROJECTION_FROZEN_ACROSS_PASSES");
            if(!g_wclosed) {
                REQUIRE(g_wused==frozen_used&&!memcmp(g_wbytes,frozen_bytes,frozen_used),"QUEUED_DATA_FROZEN");
                if(f>=499) held_drains();
            }
        }
        if(f==499&&scenario==12) request_exit(0);
        if(f==550&&scenario==13) request_exit(1);
        if(f==550&&scenario==21) { expected_writes=drain_writes; return 0; }
        int release=scenario==1?500:(scenario==2||scenario>=13)?550:scenario==4?600:499;
        if(f>=499&&f<release) continue;
        if(f==release) {
            write_fail=scenario==24?1:scenario==27?2:0;
            flush_fail=scenario==25?1:scenario==28?2:0;
            close_fail=scenario==30;
        }
        checked_drain(); checked_drain();
    }
    REQUIRE(g_fh_trace.state==1&&loads==late&&cap11==late&&recap11==late,"TRACE_AND_LOAD_COUNTS");
    REQUIRE(g_hfinal_upto==599&&submissions==599&&!g_mismatch&&!g_rbg_pend&&!g_ra_phase,"CORE_CONTINUED_PAST_512");
    if(scenario==4) checked_drain();
    if(!disabled) {
        REQUIRE(capture_frozen&&projection()==frozen_projection,"PERMANENT_CUTOFF");
        REQUIRE(g_wclosed&&g_wsealed&&!g_wused&&g_wnpass==64+late&&g_wfinals==499,"SEALED");
        REQUIRE(g_stat_padget==2*(599+late),"GAMEPLAY_STATS_CONTINUE");
        REQUIRE(InterlockedCompareExchange(&g_wexit,0,0)==2,"CHECKED_CLOSED_PUBLICATION");
        if(late) {
            REQUIRE(g_rgv_runs==1&&g_rgv_loop.comparisons==1,"ACTUAL_RAW_COMPARISON");
            for(int i=0;i<3;i++) REQUIRE(g_rgv_loop.diff[i]==1,"RAW_DIFF_PRESERVED");
        }
        /* Observer-only calls after cutoff cannot reopen or add records. */
        rbn_witness_reserve(-1,-1,-1);rbn_witness_complete(0,0,0,0,0,0,0,NULL,0,0,0,0);
        rbn_witness_base(-1,-1,0,0,0,0,0,0,0);
        int writes=drain_writes; rbn_witness_exit_init(); rbw_shutdown(); checked_drain(); REQUIRE(writes==drain_writes,"NO_SHUTDOWN_FLUSH");
    }
    if(scenario==19||scenario==20) request_exit(scenario==20);
    if(disabled&&g_hlog) { fflush(g_hlog);fclose(g_hlog);g_hlog=NULL; }
    puts("LIFECYCLE_PASS diagnostic=1 authoritative=0"); return 0;
}
