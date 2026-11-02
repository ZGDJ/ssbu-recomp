/* Private runner replaces EXACT_POSTLOAD_SEAM with the real Relifter output.
 * Service bodies and Windows loader inventory remain synthetic. */
static uint32_t postload_frames,postload_channels;
static unsigned postload_loads,postload_channel_loads,postload_pointer_loads,postload_stop;
static int postload_hold_after;
static void postload_hold_inline(Ctx *c,uint64_t pc) {
    Ctx before=*c;DWORD e=GetLastError();
    if(postload_hold_after){held(1);assert(g_al_suffix.live);held(0);tid=101;SetLastError(e);}
    game_site_inline(c,pc);assert(!memcmp(c,&before,sizeof before));
}
static __attribute__((noinline)) uint32_t postload_rd32(uint64_t a) {
    if(a==0x7106dd57b4ULL){uint32_t v=postload_frames;postload_loads++;postload_frames=v?0:512;return v;}
    assert(a==0x7106dd57bcULL);postload_channel_loads++;return postload_channels;
}
static __attribute__((noinline)) uint64_t postload_rd64(uint64_t a) {
    assert(a==0x7106dd5a18ULL);postload_pointer_loads++;return 0x12340000ULL;
}
#define rd32 postload_rd32
#define rd64 postload_rd64
#define sky_site_inline fixture_shim_inline
static void postload_seam(Ctx *c) {
/* EXACT_POSTLOAD_SEAM */
    postload_stop=3;return;
L_710398b6f4:postload_stop=2;return;
L_710398b708:postload_stop=1;return;
}
#undef sky_site_inline
#undef rd32
#undef rd64
static void postload_init(void) {
    _putenv("SSBU_SKYLINE=0");_putenv("SSBU_RB_AUDIO_CONTINUATION=1");
    g_qp_original=fixture_producer;g_qp_on=1;g_handlers[1884]=audio_release;g_handlers[1887]=audio_data;
    memset(&producer,0x65,sizeof producer);producer.in_import="audio-caller";
    host.site_inline=postload_hold_inline;ap_init();
}
static void postload_origin(void) {
    audio_begin(0);producer.x[27]=0x7106dd5000ULL;producer.x[20]=0x12345678;
    audio_end();assert(g_al_suffix.live && !g_al_errors);
}
static void postload_at_site(uint32_t value) {
    producer.x[10]=value;producer.x[12]=0x7106dd5000ULL;tid=101;
}
static void postload_execute(uint32_t value,uint32_t channels) {
    postload_frames=value;postload_channels=channels;postload_loads=postload_channel_loads=postload_pointer_loads=0;
    uint64_t before=g_al_completed;Ctx origin=g_al_suffix.origin.full;
    tid=101;SetLastError(RESULT_ERROR);postload_seam(&producer);
    assert(GetLastError()==RESULT_ERROR && postload_loads==1 && !fixture_guest_reads);
    assert(postload_frames!=(uint32_t)value && g_al_completed==before+1 && !g_al_suffix.live && !g_al_errors);
    AlRecord *r=&g_al_events[g_al_count-1].r;
    assert(r->kind==AL_POSTLOAD && r->ctx_valid && r->loaded_value==value && r->full.x[10]==value);
    assert(al_continuity(&r->full,&origin) && r->full.x[11]==origin.x[11]);
    assert(postload_channel_loads==(value!=0) && postload_pointer_loads==(value!=0));
    if(value)assert(producer.x[11]==channels && postload_stop==(channels?3:2));
    else assert(producer.x[11]==origin.x[11] && postload_stop==1);
}
static void postload_seal_trace(void) {
    audio_gap();audio_seal();assert(g_al_reported);fputs(log_text,stdout);
}
static void postload_ten(int zero,int prewindow,int cutarm) {
    audio_fixture_log_identity=1;wr64(QP_Q+0x120,PRODUCER);wr64(QP_Q+0x128,QP_Q);
    audio_caller();qp_init();submit(1);consume(1,1);
    wr32(QP_Q+4,0);wr32(QP_Q+8,0);submit(10);submit(11);
    unsigned char base[0x240];memcpy(base,(void *)(uintptr_t)QP_Q,sizeof base);
    if(prewindow)postload_origin();
    held(1);qp_capture(118);held(0);
    if(prewindow) {
        assert(g_al_suffix.live && g_al_events[0].r.pending==1);
        tid=101;postload_frames=512;postload_channels=0;postload_seam(&producer);
        assert(!g_al_suffix.live && g_al_partial==1 && g_al_canceled==1 && !g_al_completed);
    }
    for(unsigned pass=0;pass<2;pass++) {
        for(unsigned region=0;region<5;region++) {
            audio_begin(0);
            for(unsigned i=0;i<(region==4?3:2);i++){submit(20);if(rd32(QP_Q+4)-rd32(QP_Q+8)>=3)consume(1,1);}
            producer.x[27]=0x7106dd5000ULL;producer.x[20]=0x12345678;audio_end();
            if(!(cutarm==(int)pass+1 && region==4))postload_execute(zero && pass && region==4?0:512,0);
        }
        while(rd32(QP_Q+8)!=rd32(QP_Q+4))consume(1,1);
        held(1);qp_capture(119);
        if(!pass){qp_load_begin(118);memcpy((void *)(uintptr_t)QP_Q,base,sizeof base);qp_load_ready(118);held(0);}
    }
    held(0);qp_drain();ap_drain();assert(!g_qp_errors && !g_ap_errors && !g_al_errors);
    assert(g_al_expected==10+(unsigned)prewindow && g_al_eligible==10 && g_al_completed==10-(unsigned)(cutarm!=0) && g_al_zero==(uint64_t)zero);
    fputs(log_text,stdout);
}
static void postload_case(const char *mode) {
    if(!strcmp(mode,"off")) {
        _putenv("SSBU_RB_AUDIO_CONTINUATION=0");ap_init();assert(!g_ap_on && !fixture_pin_calls);
        Ctx *bad=(Ctx *)(uintptr_t)1;unsigned reads=query_reads;DWORD e=0x123;
        SetLastError(e);r1_audio_postload(bad,AUDIO_POSTLOAD_PC);assert(GetLastError()==e && !g_ap_actor && query_reads==reads);
        game_site_inline(bad,AUDIO_POSTLOAD_PC);assert(plugin_calls==1 && GetLastError()==e);return;
    }
    if(!strncmp(mode,"site-",5)) {
        const char *names[]={"absent","duplicate","kind","word","extra","foreign-table","foreign-count","foreign-caller",
            "foreign-entry-table","duplicate-entry","missing-entry","missing-data","missing-eh","unreadable","wrong-build","load-word","branch-word"};
        for(unsigned i=0;i<sizeof names/sizeof names[0];i++)if(!strcmp(mode+5,names[i]))site_mode=i+1;
        assert(site_mode);
        if(site_mode==2 || site_mode==5)fixture_site_count=2;
        if(site_mode==3)fixture_sites[0].kind=3;
        if(site_mode==4)fixture_sites[0].word=1;
        if(site_mode==10){fixture_main_table[1]=fixture_main_table[0];fixture_table_count=2;}
        if(site_mode==11)fixture_main_table[0].addr++;
        postload_init();assert(0);
    }
    postload_init();
    if(!strcmp(mode,"wrong-pc")) {
        Ctx *bad=(Ctx *)(uintptr_t)1;SetLastError(997);r1_audio_postload(bad,1);assert(GetLastError()==997 && !g_ap_actor);return;
    }
    if(!strcmp(mode,"forward")) {
        Ctx copy=producer;SetLastError(997);plugin_changes_error=1;game_site_inline(&producer,1);
        assert(GetLastError()==0xfeed && plugin_calls==1 && !memcmp(&copy,&producer,sizeof copy));return;
    }
    if(!strcmp(mode,"ten") || !strcmp(mode,"ten-zero") || !strcmp(mode,"ten-prewindow") ||
       !strcmp(mode,"ten-original-cut") || !strcmp(mode,"ten-replay-cut")){
        postload_ten(!strcmp(mode,"ten-zero"),!strcmp(mode,"ten-prewindow"),
            !strcmp(mode,"ten-original-cut")?1:!strcmp(mode,"ten-replay-cut")?2:0);return;}
    if(!strcmp(mode,"prewindow") || !strcmp(mode,"prewindow-outside")) {
        postload_origin();assert(!g_al_expected && !g_al_suffix.eligible);
        if(!strcmp(mode,"prewindow-outside")) {
            postload_at_site(512);r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);
            assert(!g_al_suffix.live && !g_al_count && !g_al_completed && g_al_outside==1);return;
        }
        audio_window();postload_at_site(512);r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);
        assert(g_al_expected==1 && !g_al_eligible && !g_al_completed && g_al_partial==1 && !g_al_suffix.live);
        assert(g_al_events[g_al_count-1].r.cut_reason==AL_BEFORE_WINDOW);postload_seal_trace();return;
    }
    audio_window();
    if(!strcmp(mode,"restored")) {
        audio_gap();postload_at_site(512);SetLastError(997);r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);
        assert(GetLastError()==997 && g_al_orphan==1 && g_al_partial==1 && !g_al_completed);
        assert(g_al_events[g_al_count-1].r.cut_reason==AL_RESTORED);audio_seal();fputs(log_text,stdout);return;
    }
    if(!strcmp(mode,"matrix")) {
        uint32_t values[]={0,1,512,UINT32_MAX},channels[]={0,2,UINT32_MAX};
        for(unsigned i=0;i<4;i++)for(unsigned j=0;j<3;j++){postload_origin();postload_execute(values[i],channels[j]);}
        assert(g_al_completed==12 && g_al_zero==3 && g_al_positive==9);return;
    }
    postload_origin();postload_at_site(512);
    if(!strcmp(mode,"positive") || !strcmp(mode,"zero") || !strcmp(mode,"hold-before") || !strcmp(mode,"hold-after")) {
        if(!strcmp(mode,"hold-before")){held(1);assert(g_al_suffix.live);held(0);tid=101;}
        postload_hold_after=!strcmp(mode,"hold-after");postload_execute(!strcmp(mode,"zero")?0:512,0);
        assert(!g_ap_errors && g_al_expected==1);postload_seal_trace();return;
    }
    if(!strcmp(mode,"full848")) {
        Ctx good=producer;
        for(unsigned i=0;i<sizeof producer;i++) {
            if((i>=80 && i<88) || (i>=96 && i<104))continue;
            producer=good;((unsigned char *)&producer)[i]^=1;Ctx before=producer;
            g_al_errors=0;SetLastError(997);r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);
            assert(GetLastError()==997 && !memcmp(&before,&producer,sizeof before) && g_al_suffix.live && !g_al_completed && g_al_errors);
        }
        producer=good;producer.x[10]=1ULL<<32;g_al_errors=0;r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);
        assert(g_al_errors && !g_al_completed);
        producer=good;producer.x[12]^=1;g_al_errors=0;Ctx before=producer;
        SetLastError(997);r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);
        assert(GetLastError()==997 && !memcmp(&before,&producer,sizeof before) && g_al_errors && !g_al_completed);
        return;
    }
    if(!strcmp(mode,"duplicate")) {
        r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);assert(g_al_completed==1);
        r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);assert(g_al_duplicate==1 && g_al_completed==1);return;
    }
    if(!strcmp(mode,"missing") || !strcmp(mode,"overlap")) {
        uint64_t ticket=g_al_suffix.origin.end_ticket;
        if(!strcmp(mode,"missing"))audio_begin(0);else audio_end();
        assert(g_al_missing==1 && g_al_errors && !g_al_completed);
        assert(g_al_events[1].r.kind==AL_CUT && g_al_events[1].r.end_ticket==ticket && g_al_events[1].r.cut_reason==AL_MISSING);
        if(g_al_suffix.live)assert(g_al_suffix.origin.end_ticket!=ticket);return;
    }
    if(!strcmp(mode,"interval-cut")) {
        audio_gap();assert(!g_al_suffix.live && g_al_partial==1 && g_al_canceled==1);
        AlRecord *cut=&g_al_events[1].r;assert(cut->kind==AL_CUT && cut->pending && !cut->ctx_valid);
        assert(!memcmp(&cut->full,&(Ctx){0},sizeof(Ctx)));return;
    }
    if(!strcmp(mode,"seal-cut")) {
        r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);audio_gap();postload_origin();
        audio_seal();assert(!g_al_suffix.live && g_al_pending_seal==1 && g_al_partial==1 && g_al_canceled==1);fputs(log_text,stdout);return;
    }
    if(!strcmp(mode,"pending-import")) {
        r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);audio_begin(0);audio_caller();producer.x[30]=0x710398b68c;producer.x[0]=0x12345678;
        assert(r1_audio_import_enter(&producer,1887));audio_gap();
        assert(!g_al_suffix.live && g_al_expected==1 && (g_ap_errors&AP_PENDING));return;
    }
    if(!strcmp(mode,"load-refusal") || !strcmp(mode,"load-ready")) {
        if(!strcmp(mode,"load-refusal"))ap_load_begin(119,1);else ap_load_ready_held(119,1);
        assert(!g_al_suffix.live && g_al_canceled==1 && (g_ap_errors&AP_BOUNDARY));return;
    }
    if(!strcmp(mode,"capacity"))g_al_interior=AL_INTERIOR;
    else if(!strcmp(mode,"wrap"))g_al_id=UINT64_MAX;
    else if(!strcmp(mode,"cas"))g_ap_owner=1;
    else if(!strcmp(mode,"generation"))g_ap_generation++;
    else if(!strcmp(mode,"actor"))tid=202;
    else if(!strcmp(mode,"qp-identity")){g_qp_producer.actor=202;g_qp_producer.ctx=&producer;}
    else if(!strcmp(mode,"pointer")) {
        Ctx other=producer;SetLastError(997);r1_audio_postload(&other,AUDIO_POSTLOAD_PC);
        assert(GetLastError()==997 && !memcmp(&other,&producer,sizeof other) && g_al_suffix.live && g_al_errors);return;
    }
    else if(!strcmp(mode,"metadata-read") || !strcmp(mode,"metadata-name") || !strcmp(mode,"origin-event") || !strcmp(mode,"origin-binding")) {
        r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);audio_begin(0);
        producer.x[27]=0x7106dd5000ULL;producer.x[20]=0x12345678;
        if(!strcmp(mode,"metadata-read"))fixture_rpm_fail=1;
        if(!strcmp(mode,"metadata-name"))fixture_bad_name=1;
        if(!strcmp(mode,"origin-event"))g_ap_interior=AP_INTERIOR;
        if(!strcmp(mode,"origin-binding"))g_handlers[1887]=NULL;
        if(!strcmp(mode,"origin-binding")) {
            producer.x[30]=0x710398b68c;producer.x[0]=0x12345678;AudioTicket id=r1_audio_import_enter(&producer,1887);
            producer.x[0]=0x87654321;r1_audio_import_return(&producer,1887,id);
        } else audio_end();
        assert(g_al_errors && g_al_suffix.live && !g_al_suffix.eligible && g_al_completed==1);return;
    }
    else if(!strcmp(mode,"unready")) {
        r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);g_al_events[1].ready=0;postload_seal_trace();
        assert(g_al_errors&AP_UNREADY);return;
    }
    else if(!strcmp(mode,"drain") || !strcmp(mode,"late")) {
        r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);audio_gap();held(1);ap_capture_held(119,3);
        ap_drain();assert(!g_al_reported);held(0);g_ap_owner=1;ap_drain();assert(!g_al_reported);
        g_ap_owner=0;g_rg_kept=1;ap_drain();assert(!g_al_reported);g_rg_kept=0;ap_drain();assert(g_al_reported);
        if(!strcmp(mode,"late")){uint64_t count=g_al_count;g_ap_owner=1;r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);
            g_ap_owner=0;ap_drain();assert(g_al_count==count && strstr(log_text,"AUDIO_POSTLOAD_LATE_ERROR"));}
        return;
    } else assert(0);
    Ctx before=producer;SetLastError(997);r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);
    assert(GetLastError()==997 && !memcmp(&before,&producer,sizeof before) && g_al_suffix.live && !g_al_completed && g_al_errors);
}
