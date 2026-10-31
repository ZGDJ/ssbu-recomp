/* CHECKPOINT_THUNK_SOURCE */
static void audio_late_inject(void) { ap_fail(AP_POST_SEAL); }
/* Synthetic operations call the production observer and edited wrappers above.
 * The guest buffer/stack and service bodies are fixtures, not game execution. */
static void audio_release(Ctx *c) {
    assert(GetLastError()==ENTRY_ERROR);c->x[0]=0x12345678;SetLastError(RESULT_ERROR);
}
static void audio_data(Ctx *c) {
    assert(GetLastError()==ENTRY_ERROR);c->x[0]=0x87654321;SetLastError(RESULT_ERROR);
}
static int audio_called;
static Ctx audio_seen;
static void audio_body(Ctx *c) {
    assert(GetLastError()==ENTRY_ERROR);audio_called++;audio_seen=*c;
    c->x[10]=0x1111111122222222ULL;c->v[31].d[1]=0xaabbccddeeff7788ULL;
    c->ex_val2=0x8877665544332211ULL;SetLastError(RESULT_ERROR);
}
static void audio_closure(Ctx *c,void *user) { assert(user==(void *)0x123);audio_body(c); }
static void audio_caller(void) {
    tid=101;producer.x[31]=(uintptr_t)input_stack;producer.x[29]=producer.x[31]+2336;
}
static void audio_begin(int null_return) {
    audio_caller();producer.fn=0x7500334fa0;producer.x[30]=0x7103987f94;producer.x[2]=0;
    if(null_return) {
        AudioTicket id=r1_audio_import_enter(&producer,1884);
        AudioBinding b={0};b.family=AB_IMPORT;b.status=AB_RAW;b.fn=(uintptr_t)(void *)audio_release;
        r1_audio_binding(&producer,id,&b);producer.x[0]=0;r1_audio_import_return(&producer,1884,id);
    } else {
        SetLastError(ENTRY_ERROR);f_71039c8390(&producer);assert(GetLastError()==(g_watch_sym==1884?444:RESULT_ERROR));
    }
}
static void audio_end(void) {
    audio_caller();producer.fn=0x710398bc70;producer.x[30]=0x710398b68c;producer.x[0]=0x12345678;
    SetLastError(ENTRY_ERROR);f_71039c83a0(&producer);assert(GetLastError()==RESULT_ERROR);
}
static void audio_prepare_edge(unsigned edge,uint64_t target) {
    audio_caller();uint64_t body=producer.x[31];producer.x[31]-=48;producer.x[29]=body-16;
    producer.fn=edge==1?0x7103964b70:0x7103964db0;
    producer.x[30]=edge==1?0x7103964ba0:0x7103964de0;producer.x[8]=target;producer.x[0]=0;
    wr64(producer.x[31]+32,body+2336);wr64(producer.x[31]+40,edge==1?0x710398b4b4:0x710398b61c);
}
static void audio_edge(unsigned edge,uint64_t target) {
    audio_prepare_edge(edge,target);Ctx before=producer;
    SetLastError(ENTRY_ERROR);call_indirect(&producer,target);assert(GetLastError()==RESULT_ERROR);
    assert(producer.x[10]==0x1111111122222222ULL && producer.ex_val2==0x8877665544332211ULL);
    assert(producer.x[31]==before.x[31] && producer.x[29]==before.x[29]);
}
static void audio_window(void) {
    held(1);ap_capture_held(118,0);g_qp_stage=1;held(0);
}
static void audio_gap(void) {
    held(1);ap_capture_held(119,1);g_qp_stage=2;ap_load_begin(118,2);ap_load_ready_held(118,2);
    g_qp_stage=3;held(0);
}
static void audio_seal(void) {
    held(1);ap_capture_held(119,3);g_qp_stage=4;held(0);
    uint64_t n=g_ap_count;
    for(unsigned i=0;i<n;i++)assert(g_ap_events[i].r.stage!=4);
    ap_drain();assert(n==g_ap_count);
}
static unsigned audio_count(unsigned kind) {
    unsigned n=0;for(unsigned i=0;i<g_ap_count;i++)n+=g_ap_events[i].r.kind==kind;return n;
}
static void audio_attempt(unsigned token,int accepted) {
    audio_caller();prepare_producer(&producer,20);g_qp_producer.actor=101;g_qp_producer.ctx=&producer;
    ap_producer_enter(&producer,token,g_ap_stage);
    /* Exact return notification; no guessed x0 decision. */
    producer.x[10]=token;producer.ex_val2=0xdeadbeef00000000ULL|token;
    r1_audio_producer_return(&producer,token,accepted);
}
static void audio_integrated_eleven(uint64_t target) {
    audio_fixture_log_identity=1;wr64(QP_Q+0x120,PRODUCER);wr64(QP_Q+0x128,QP_Q);
    audio_caller();qp_init();submit(1);consume(1,1);
    wr32(QP_Q+4,0);wr32(QP_Q+8,0);submit(10);submit(11);
    unsigned char base[0x240];memcpy(base,(void *)(uintptr_t)QP_Q,sizeof base);
    held(1);qp_capture(118);held(0);
    for(unsigned pass=0;pass<2;pass++) {
        audio_begin(0);
        for(unsigned i=0;i<11;i++) {
            submit(20); /* eleven identical payloads, actual kind1/2/3/4 joins */
            if(i==2 || i==5 || i==8)consume(1,1);
        }
        while(rd32(QP_Q+8)!=rd32(QP_Q+4))consume(1,1);
        audio_edge(1,target);audio_edge(2,target);audio_end();
        held(1);qp_capture(119);
        if(!pass){qp_load_begin(118);memcpy((void *)(uintptr_t)QP_Q,base,sizeof base);qp_load_ready(118);held(0);}
    }
    held(0);qp_drain();ap_drain();assert(!g_qp_errors && !g_ap_errors);
    assert(audio_count(AP_PRODUCER_RETURN)==22 && g_ap_complete==2);fputs(log_text,stdout);
}
static void audio_case(const char *mode) {
    /* The saved helper words live in real readable memory before body SP. */
    _putenv("SSBU_SKYLINE=0");
    g_qp_original=fixture_producer;g_qp_on=1;g_handlers[1884]=audio_release;g_handlers[1887]=audio_data;
    memset(&producer,0x65,sizeof producer);producer.in_import="audio-caller";memset(input_storage,0,sizeof input_storage);
    g_hostfn[0].fn=audio_body;g_hostfn[1].fnu=audio_closure;g_hostfn[1].user=(void *)0x123;
    g_handlers[42]=audio_body;
    if(!strcmp(mode,"audio-off")) {
        unsigned before=query_reads;Ctx *bad=(Ctx *)(uintptr_t)1;
        assert(!r1_audio_indirect_enter(bad,1) && !r1_audio_import_enter(bad,1884));
        r1_audio_indirect_return(bad,1);r1_audio_import_return(bad,1884,1);
        r1_audio_binding(bad,1,(AudioBinding *)(uintptr_t)1);
        r1_audio_producer_return(bad,1,1);
        assert(!g_ap_count && !g_ap_errors && before==query_reads && !g_ap_actor);return;
    }
    if(!strcmp(mode,"audio-bad-option")) { _putenv("SSBU_RB_AUDIO_CONTINUATION=2");ap_init();assert(0); }
    if(!strcmp(mode,"audio-needs-qp")) { _putenv("SSBU_RB_AUDIO_CONTINUATION=1");g_qp_on=0;ap_init();assert(0); }
    if(!strcmp(mode,"audio-watch-refusal")) { _putenv("SSBU_RB_AUDIO_CONTINUATION=1");_putenv("SSBU_IMPORT_WATCH=foo");ap_init();assert(0); }
    _putenv("SSBU_RB_AUDIO_CONTINUATION=1");ap_init();
    if(!strcmp(mode,"audio-import-interior-eleven")){audio_integrated_eleven(IMPORT_BASE+42*IMPORT_SLOT+99);return;}
    if(!strcmp(mode,"audio-integrated-eleven")){audio_integrated_eleven(HOSTFN_BASE);return;}
    if(!strcmp(mode,"audio-integrated") || !strcmp(mode,"audio-integrated-complete")) {
        audio_fixture_regions=!strcmp(mode,"audio-integrated-complete");
        audio_fixture_log_identity=1;wr64(QP_Q+0x120,PRODUCER);wr64(QP_Q+0x128,QP_Q);
        audio_caller();complete();assert(!g_ap_errors);
        size_t before=log_length;ap_drain();assert(g_ap_reported && !g_ap_errors);
        fputs(log_text+before,stdout);return;
    }
    /* Move stack within the oversized buffer so helper SP remains readable. */
    if(!strcmp(mode,"audio-prewindow")) {
        audio_begin(0);assert(g_ap_region.id && !g_ap_count);audio_window();
        assert(g_ap_region.coverage&AP_BEFORE_WINDOW);audio_gap();
        audio_prepare_edge(1,HOSTFN_BASE);SetLastError(ENTRY_ERROR);call_indirect(&producer,HOSTFN_BASE);
        assert(g_ap_region.coverage&AP_RESTORED_UNKNOWN);audio_seal();
        assert(g_ap_pending_seal==1 && g_ap_partial==2 && !g_ap_errors);fputs(log_text,stdout);return;
    }
    if(!strcmp(mode,"audio-prewindow-import")) {
        audio_caller();producer.fn=0x7500334fa0;producer.x[30]=0x7103987f94;
        AudioTicket t=r1_audio_import_enter(&producer,1884);AudioBinding b={0};
        b.family=AB_IMPORT;b.status=AB_RAW;b.fn=(uintptr_t)(void *)audio_release;
        r1_audio_binding(&producer,t,&b);assert(!g_ap_count);
        audio_window();assert(audio_count(AP_IMPORT_ENTER)==1 && audio_count(AP_IMPORT_BIND)==1);
        tid=101;producer.x[0]=0x12345678;r1_audio_import_return(&producer,1884,t);audio_end();
        assert(!g_ap_errors);return;
    }
    audio_window();
    if(!strcmp(mode,"audio-null-zero")) {
        audio_begin(1);assert(!g_ap_region.id);audio_begin(0);audio_end();
        assert(g_ap_complete==1 && !audio_count(AP_AUDIO_ENTER));
    } else if(!strcmp(mode,"audio-chain")) {
        audio_begin(0);for(unsigned t=100;t<111;t++)audio_attempt(t,t&1);
        audio_edge(1,HOSTFN_BASE);audio_edge(2,HOSTFN_BASE);audio_end();
        assert(g_ap_complete==1 && audio_count(AP_PRODUCER_RETURN)==11 && audio_count(AP_AUDIO_ENTER)==2);
        uint64_t prev=0;unsigned n=0;
        for(unsigned i=0;i<g_ap_count;i++)if(g_ap_events[i].r.kind==AP_PRODUCER_RETURN) {
            ApRecord *r=&g_ap_events[i].r;assert(r->previous_return==prev && r->qp_token==100+n);
            assert(r->full.x[10]==100+n && r->full.ex_val2==(0xdeadbeef00000000ULL|(100+n)));
            prev=r->id;n++;
        }
    } else if(!strcmp(mode,"audio-masks")) {
        for(unsigned mask=0;mask<4;mask++) {
            audio_begin(0);uint64_t id=g_ap_region.id;
            audio_attempt(100+mask*2,mask&1);audio_attempt(101+mask*2,!(mask&1));
            if(mask&1)audio_edge(1,HOSTFN_BASE);
            if(mask&2)audio_edge(2,HOSTFN_BASE);
            audio_end();assert(g_ap_region.entered==mask && g_ap_region.returned==mask && g_ap_region.id==id);
        }assert(g_ap_complete==4);
    } else if(!strcmp(mode,"audio-stale")) {
        audio_begin(0);audio_prepare_edge(1,HOSTFN_BASE);AudioTicket stale=r1_audio_indirect_enter(&producer,HOSTFN_BASE);
        AudioBinding b={0};b.family=AB_HOST;b.fn=(uintptr_t)(void *)audio_body;b.status=AB_RAW;
        r1_audio_binding(&producer,stale,&b);r1_audio_indirect_return(&producer,stale);
        audio_end();uint64_t old=g_ap_region.id;audio_begin(0);assert(g_ap_region.id!=old);
        audio_prepare_edge(1,HOSTFN_BASE);AudioTicket now=r1_audio_indirect_enter(&producer,HOSTFN_BASE);
        r1_audio_indirect_return(&producer,stale);assert(g_ap_errors&AP_STALE);
        assert(ap_ticket(now,&producer,0));return;
    } else if(!strcmp(mode,"audio-generation")) {
        audio_begin(0);audio_prepare_edge(1,HOSTFN_BASE);AudioTicket old=r1_audio_indirect_enter(&producer,HOSTFN_BASE);
        audio_gap();audio_begin(0);audio_prepare_edge(1,HOSTFN_BASE);
        AudioTicket now=r1_audio_indirect_enter(&producer,HOSTFN_BASE);assert(now>old);
        r1_audio_indirect_return(&producer,old);assert(g_ap_errors&AP_STALE);
        assert(ap_ticket(now,&producer,0));return;
    } else if(!strcmp(mode,"audio-bad-frame")) {
        audio_begin(0);audio_prepare_edge(1,HOSTFN_BASE);wr64(producer.x[31]+40,0);
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE) && (g_ap_errors&AP_FRAME));return;
    } else if(!strcmp(mode,"audio-orphan")) {
        audio_begin(0);audio_end();audio_prepare_edge(1,HOSTFN_BASE);
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE) && (g_ap_errors&AP_BOUNDARY));return;
    } else if(!strcmp(mode,"audio-bad-order")) {
        audio_begin(0);audio_edge(2,HOSTFN_BASE);audio_prepare_edge(1,HOSTFN_BASE);
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE) && (g_ap_errors&AP_OVERLAP));return;
    } else if(!strcmp(mode,"audio-import-paths")) {
        for(int watched=0;watched<2;watched++)for(int fast=0;fast<2;fast++) {
            g_watch_sym=watched?1884:-1;g_import_calls[1884]=fast?9:0;
            audio_begin(0);assert(!strcmp(producer.in_import,"audio-caller"));
            audio_end();
        }
    } else if(!strcmp(mode,"audio-bindings")) {
        uint64_t targets[]={HOSTFN_BASE+7,IMPORT_BASE+42*IMPORT_SLOT+99};
        for(unsigned i=0;i<2;i++) {audio_begin(0);audio_edge(1,targets[i]);audio_end();}
        assert(audio_called==2);
    } else if(!strcmp(mode,"audio-main-bindings")) {
        uint64_t targets[]={0x7101000100ULL,0x7600009990ULL};
        for(unsigned i=0;i<2;i++){audio_begin(0);audio_edge(1,targets[i]);audio_end();}
        assert(audio_called==2);
    } else if(!strcmp(mode,"audio-unresolved")) {
        audio_begin(0);audio_edge(1,HOSTFN_BASE+16);assert(g_ap_errors&AP_BINDING);return;
    } else if(!strcmp(mode,"audio-capacity")) {
        audio_begin(0);
        for(unsigned i=0;i<AP_INTERIOR+10;i++)ap_simple(AP_ERROR,&producer,0);
        assert((g_ap_errors&AP_CAPACITY) && g_ap_drops && g_ap_interior==AP_INTERIOR);
        audio_gap();audio_seal();assert(g_ap_reported && g_ap_boundary_count>=5);fputs(log_text,stdout);return;
    } else if(!strcmp(mode,"audio-unready")) {
        audio_begin(0);ap_event(AP_ERROR,&producer,0);audio_gap();audio_seal();
        assert((g_ap_errors&AP_UNREADY) && g_ap_reported);return;
    } else if(!strcmp(mode,"audio-wrap")) {
        audio_begin(0);g_ap_ticket_id=UINT64_MAX;audio_prepare_edge(1,HOSTFN_BASE);
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE) && (g_ap_errors&AP_WRAP));return;
    } else if(!strcmp(mode,"audio-wrong-actor")) {
        audio_begin(0);audio_prepare_edge(1,HOSTFN_BASE);tid=202;
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE) && (g_ap_errors&AP_IDENTITY));return;
    } else if(!strcmp(mode,"audio-ticket-capacity")) {
        audio_caller();for(unsigned i=0;i<AP_TICKETS;i++)assert(ap_mint(&producer,1));
        assert(!ap_mint(&producer,1) && (g_ap_errors&AP_CAPACITY));return;
    } else if(!strcmp(mode,"audio-read-failure")) {
        audio_prepare_edge(1,HOSTFN_BASE);producer.x[31]=1;
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE) && (g_ap_errors&AP_READ));return;
    } else if(!strcmp(mode,"audio-sp-overflow")) {
        audio_prepare_edge(1,HOSTFN_BASE);producer.x[31]=UINT64_MAX-16;
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE) && (g_ap_errors&AP_FRAME));return;
    } else if(!strcmp(mode,"audio-wrong-ctx")) {
        audio_begin(0);audio_prepare_edge(1,HOSTFN_BASE);Ctx other=producer;
        assert(!r1_audio_indirect_enter(&other,HOSTFN_BASE) && (g_ap_errors&AP_IDENTITY));return;
    } else if(!strcmp(mode,"audio-x8-mismatch")) {
        audio_begin(0);audio_prepare_edge(1,HOSTFN_BASE);producer.x[8]++;
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE) && (g_ap_errors&AP_FRAME));return;
    } else if(!strcmp(mode,"audio-unrelated")) {
        g_ap_owner=1;producer.x[30]=0;
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE) && !r1_audio_import_enter(&producer,1884));
        assert(!g_ap_errors);g_ap_owner=0;return;
    } else if(!strcmp(mode,"audio-overlap")) {
        audio_begin(0);g_ap_owner=1;audio_prepare_edge(1,HOSTFN_BASE);
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE) && (g_ap_errors&AP_OVERLAP));g_ap_owner=0;return;
    } else if(!strcmp(mode,"audio-gap-activity")) {
        held(1);ap_capture_held(119,1);g_qp_stage=2;held(0);
        uint64_t before=g_ap_count;audio_prepare_edge(1,HOSTFN_BASE);
        assert(!r1_audio_indirect_enter(&producer,HOSTFN_BASE));assert(g_ap_count==before && g_ap_gap_activity==1 && !g_ap_errors);return;
    } else if(!strcmp(mode,"audio-missing-load-ready")) {
        held(1);ap_capture_held(119,1);g_qp_stage=2;ap_load_ready_held(118,2);
        assert(g_ap_errors&AP_BOUNDARY);return;
    } else if(!strcmp(mode,"audio-wrong-boundary")) {
        ap_capture_held(120,1);assert(g_ap_errors&AP_BOUNDARY);return;
    } else if(!strcmp(mode,"audio-stale-import-begin") || !strcmp(mode,"audio-stale-import-end")) {
        int sym=!strcmp(mode,"audio-stale-import-begin")?1884:1887;
        if(sym==1887)audio_begin(0);
        audio_caller();producer.fn=sym==1884?0x7500334fa0:0x710398bc70;
        producer.x[30]=sym==1884?0x7103987f94:0x710398b68c;producer.x[0]=0x12345678;
        AudioTicket old=r1_audio_import_enter(&producer,sym);assert(old);audio_gap();
        audio_begin(0);uint64_t region=g_ap_region.id;
        r1_audio_import_return(&producer,sym,old);assert((g_ap_errors&AP_STALE) && g_ap_region.id==region);return;
    } else if(!strcmp(mode,"audio-stale-producer")) {
        audio_begin(0);audio_caller();prepare_producer(&producer,20);ap_producer_enter(&producer,123,1);
        audio_gap();audio_begin(0);audio_caller();prepare_producer(&producer,20);ap_producer_enter(&producer,124,3);
        r1_audio_producer_return(&producer,123,1);assert(g_ap_producer==124 && (g_ap_errors&AP_CHAIN));return;
    } else if(!strcmp(mode,"audio-drain-races")) {
        audio_begin(0);audio_end();audio_gap();audio_begin(0);audio_end();
        held(1);ap_capture_held(119,3);held(0);
        InterlockedExchange(&g_ap_owner,1);ap_drain();
        assert(!g_ap_errors && !g_ap_reported);
        InterlockedExchange(&g_ap_owner,0);log_inject=audio_late_inject;ap_drain();
        assert(g_ap_errors==AP_POST_SEAL && g_ap_reported_errors==0);
        ap_drain();assert(strstr(log_text,"AUDIO_CONTINUATION_LATE_ERROR") && g_ap_reported_errors==AP_POST_SEAL);return;
    } else if(!strcmp(mode,"audio-post-seal")) {
        audio_begin(0);audio_end();audio_gap();audio_begin(0);audio_end();
        held(1);ap_capture_held(119,3);held(0);uint64_t before=g_ap_count;
        r1_audio_indirect_return(&producer,1);assert((g_ap_errors&AP_POST_SEAL) && g_ap_count==before);return;
    } else assert(0);
    assert(!g_ap_errors);audio_gap();audio_seal();assert(!g_ap_errors && g_ap_reported);
    fputs(log_text,stdout);
}
