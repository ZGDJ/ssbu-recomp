static void holds(int x){g_th[0].held=g_th[1].held=x;tid=303;}
static void fixture_setup(int enable){
    InitializeCriticalSection(&g_lock);g_ar_lock_ready=1;g_freq.QuadPart=48000;
    g_qp_on=1;g_qp_original=fixture_original;g_qp_producer.actor=101;g_qp_consumer.actor=202;
    g_qp_producer.ctx=&producer;g_qp_consumer.ctx=&consumer;
    g_th[0].h=(HANDLE)(uintptr_t)101;g_th[1].h=(HANDLE)(uintptr_t)202;
    assert(VirtualAlloc((void *)(uintptr_t)(QP_Q&~0xffffULL),65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
    wr8(QP_Q,1);wr64(QP_Q+0x130,0x710373e620ULL);
    g_handlers[1884]=audio_GetReleasedAudioOutBuffer;g_handlers[1887]=audio_GetAudioOutBufferDataPointer;
    g_handlers[1401]=fixture_original;
    memset(&producer,0x65,sizeof producer);producer.in_import=NULL;
    _putenv("SSBU_RB_AUDIO_CONTINUATION=1");_putenv("SSBU_SKYLINE=0");
    _putenv(enable?"SSBU_RB_AUDIO_RELEASE_QUEUE=1":"SSBU_RB_AUDIO_RELEASE_QUEUE=0");
    SetLastError(711);ap_init();assert(GetLastError()==711);
    assert(audio_release_probe_enabled()==enable);
    for(unsigned i=0;i<130;i++){
        wr64((uintptr_t)guest_buffers[i]+8,(uintptr_t)pcm_samples);wr64((uintptr_t)guest_buffers[i]+24,sizeof pcm_samples);
    }
}
static void open_audio(void){Ctx c={0};c.x[0]=0x7106dd58a8ULL;c.x[1]=0x999;c.x[2]=(uintptr_t)guest_param;
    audio_OpenDefaultAudioOut(&c);assert(c.x[0]==0 && g_open && !g_started && g_head==0 && g_rel_head==0);}
static void append_audio(unsigned i){Ctx c={0};c.x[0]=g_audio_out;c.x[1]=(uintptr_t)guest_buffers[i%130];
    unsigned before=g_tail;audio_AppendAudioOutBuffer(&c);assert(c.x[0]==(g_open && before-g_head<64));}
static void start_audio(void){Ctx c={0};audio_StartAudioOut(&c);assert(c.x[0]==0);}
static void native_poll(void){DWORD saved=tid;tid=909;thread_iterations=1;
    if(!setjmp(thread_done))audio_thread(NULL);assert(!lock_depth);tid=saved;}
static ArRecord *last_kind(unsigned kind){for(unsigned i=(unsigned)g_ar.count;i-->0;)if(g_ar.events[i].r.kind==kind)return &g_ar.events[i].r;return NULL;}
static unsigned count_kind(unsigned kind){unsigned n=0;for(unsigned i=0;i<g_ar.count;i++)n+=g_ar.events[i].r.kind==kind;return n;}
static void boundary_begin(void){holds(1);qp_capture(118);assert(g_ap_stage==1);holds(0);}
static void boundary_gap(void){holds(1);qp_capture(119);assert(g_ap_stage==2);qp_load_begin(118);qp_load_ready(118);assert(g_ap_stage==3);holds(0);}
static void boundary_end(int dump){holds(1);qp_capture(119);assert(g_ap_stage==4);holds(0);
    Ctx h={0};h.x[30]=g_ra_site;SetLastError(711);ra_kick2(&h,NULL);assert(h.x[0]==87 && GetLastError()==413);
    assert(!lock_depth);if(dump)fputs(logs,stdout);}
static void caller(void){tid=101;producer.x[31]=(uintptr_t)stack_bytes+64;producer.x[29]=producer.x[31]+2336;producer.x[30]=0x7103987f94ULL;
    producer.x[0]=g_audio_out;producer.x[27]=0x7106dd5000ULL;}
static uint64_t get_audio(int fast){caller();g_import_calls[1884]=fast?3:0;Ctx before=producer;
    SetLastError(711);host_import(&producer,1884);uint64_t r=producer.x[0];
    before.x[0]=r;assert(!memcmp(&before,&producer,sizeof before));
    if(r){producer.x[20]=r;producer.x[30]=0x710398b68cULL;producer.x[0]=r;
        host_import(&producer,1887);producer.x[10]=512;producer.x[12]=0x7106dd5000ULL;r1_audio_postload(&producer,AUDIO_POSTLOAD_PC);}
    return r;
}
static void complete(void){fixture_setup(1);open_audio();for(unsigned i=0;i<3;i++)append_audio(i);start_audio();
    g_slots[0].hdr.dwFlags=WHDR_DONE;native_poll();assert(g_rel_tail==1);
    boundary_begin();assert(g_ar.boundaries[0].b.r.stamp_status==AR_B_OK);
    g_slots[1].hdr.dwFlags=WHDR_DONE;
    assert(get_audio(0)==(uintptr_t)guest_buffers[0]);
    assert(last_kind(AR_PRECOLLECT));assert(last_kind(AR_PRECOLLECT)->front_guest==(uintptr_t)guest_buffers[0]);
    assert(last_kind(AR_POSTCOLLECT)->n==1 && last_kind(AR_POSTCOLLECT)->rel_tail==2);
    assert(get_audio(1)==(uintptr_t)guest_buffers[1]);assert(get_audio(0)==0);
    g_slots[2].hdr.dwFlags=WHDR_DONE;assert(get_audio(1)==(uintptr_t)guest_buffers[2]);
    assert(last_kind(AR_PRECOLLECT)->rel_head==last_kind(AR_PRECOLLECT)->rel_tail);
    /* Independent publications in both explicit host gaps are mandatory. */
    holds(1);qp_capture(119);append_audio(5);g_slots[(g_tail-1)%64].hdr.dwFlags=WHDR_DONE;native_poll();
    qp_load_begin(118);append_audio(6);g_slots[(g_tail-1)%64].hdr.dwFlags=WHDR_DONE;native_poll();
    qp_load_ready(118);holds(0);native_poll();
    assert(get_audio(1)==(uintptr_t)guest_buffers[5]);assert(get_audio(0)==(uintptr_t)guest_buffers[6]);assert(get_audio(1)==0);
    append_audio(3);g_slots[(g_tail-1)%64].hdr.dwFlags=WHDR_DONE;native_poll();assert(get_audio(0)==(uintptr_t)guest_buffers[3]);
    assert(!g_ar.errors && !g_ap_errors && !g_al_errors && !g_qp_errors);
    boundary_end(1);assert(g_ar.footer.sealed && !g_ar.footer.failed && !g_ar.footer.errors);
    uint64_t count=g_ar.count,w=g_ar.footer.last_write_seq;append_audio(4);native_poll();assert(g_ar.count==count && g_ar.footer.last_write_seq==w);
    assert(count_kind(AR_PRECOLLECT)==8 && count_kind(AR_POP)==8);
}
static void raw_get(void){Ctx c;memset(&c,0x73,sizeof c);c.x[30]=0x7000000010ULL;Ctx before=c;
    audio_GetReleasedAudioOutBuffer(&c);before.x[0]=c.x[0];assert(!memcmp(&before,&c,sizeof c));}
static void predicates(void){fixture_setup(1);open_audio();for(unsigned i=0;i<5;i++)append_audio(i);boundary_begin();
    g_slots[1].hdr.dwFlags=WHDR_DONE;
    unsigned q=qpc_calls;raw_get();assert(qpc_calls==q+1 && last_kind(AR_CHECK)->decision==AR_DEC_BLOCK_DEVICE && !g_head && !g_rel_tail);
    g_slots[1].hdr.dwFlags=0;
    assert(last_kind(AR_CHECK)->valid_mask&AR_V_FLAGS_ACTUALLY_TESTED);
    g_slots[0].hdr.dwFlags=WHDR_DONE;raw_get();assert(last_kind(AR_PUBLISH)->guest==(uintptr_t)guest_buffers[0]);
    /* Every PASS retains its pre-unprepare sample, despite the fake mutating flags. */
    for(unsigned i=0;i<g_ar.count;i++)if(g_ar.events[i].r.kind==AR_CHECK && g_ar.events[i].r.decision==AR_DEC_PASS_DEVICE)
        assert(g_ar.events[i].r.flags==WHDR_DONE);
    g_slots[1].prepared=0;g_started=0;raw_get();assert(last_kind(AR_CHECK)->decision==AR_DEC_BLOCK_STOPPED &&
        !(last_kind(AR_CHECK)->valid_mask&AR_V_NOW_USED_IN_FALLBACK_COMPARE));
    g_started=1;g_slots[1].due=101;raw_get();assert(last_kind(AR_CHECK)->decision==AR_DEC_BLOCK_NOT_DUE);
    scripted_now=101;raw_get();assert(last_kind(AR_PUBLISH)->guest==(uintptr_t)guest_buffers[1]);
    g_slots[2].prepared=0;g_slots[2].due=100;raw_get();assert(last_kind(AR_PUBLISH)->guest==(uintptr_t)guest_buffers[2]);
    Ctx c={0};audio_StopAudioOut(&c);
    assert(last_kind(AR_CHECK)->decision==AR_DEC_FORCED && !(last_kind(AR_CHECK)->valid_mask&AR_V_FLAGS_ACTUALLY_TESTED));
    assert(last_kind(AR_RESET_COMMIT)->n==0 && !g_ar.errors);
}
static void reset_overlap(void){for(unsigned i=g_head;i!=g_tail;i++)g_slots[i%64].hdr.dwFlags=WHDR_DONE;native_poll();}
static void reopen_overlap(void){open_audio();}
static void lifecycle(int ambiguous){fixture_setup(1);open_audio();append_audio(0);start_audio();boundary_begin();
    reset_inject=ambiguous?reopen_overlap:reset_overlap;reset_result=7;Ctx c={0};
    audio_StopAudioOut(&c);assert(!g_started && last_kind(AR_RESET_COMMIT)->n==7);
    if(ambiguous){assert(g_ar.errors&AR_E_CONTROL_AMBIGUOUS);return;}
    assert(g_rel_tail==1 && last_kind(AR_PUBLISH)->caller_kind==AR_CALL_AUDIO_THREAD && last_kind(AR_PUBLISH)->detail);
    append_audio(1);audio_CloseAudioOut(&c);assert(!g_open && !g_wave && g_rel_tail==2);raw_get();assert(last_kind(AR_POP)->popped && last_kind(AR_POSTCOLLECT)->decision==AR_DEC_COLLECT_SKIPPED_CLOSED);
    raw_get();assert(last_kind(AR_POP)->popped);raw_get();assert(!last_kind(AR_POP)->popped);open_audio();append_audio(0);start_audio();
    boundary_gap();assert(get_audio(1)==0);boundary_end(1);assert(!g_ar.errors);
}
static ArBoundaryStamp stamp(unsigned slot){ArBoundaryStamp s={0};s.slot=slot;s.frame=slot%2?119:118;s.event=10+slot;
    s.transition=slot+1;s.stage=slot==3?3:1;s.actor=303;s.valid=1;s.hold=11;return s;}
static void busy_case(void){fixture_setup(1);Owner o={&g_lock,CreateEventA(NULL,0,0,NULL),CreateEventA(NULL,0,0,NULL)};
    HANDLE t=CreateThread(NULL,0,real_owner,&o,0,NULL);assert(t && real_wait(o.acquired,3000)==WAIT_OBJECT_0);
    assert(SuspendThread(t)!=(DWORD)-1);unsigned e=enters,q=qpc_calls,d=device_calls,tr=tries;ArBoundaryStamp s=stamp(0);
    SetLastError(811);assert(audio_release_probe_boundary(&s)==AR_B_BUSY);assert(GetLastError()==811);
    assert(tries==tr+1 && enters==e && qpc_calls==q && device_calls==d && !g_ar.live && !g_ar.count);
    ArRecord *r=&g_ar.boundaries[0].b.r;assert(!r->record_id && !r->op_id && !r->write_seq && !r->rel_tail && !(r->valid_mask&AR_V_HOST_ORDER_VALID));
    assert(ResumeThread(t)!=(DWORD)-1);SetEvent(o.release);assert(real_wait(t,3000)==WAIT_OBJECT_0);CloseHandle(t);CloseHandle(o.acquired);CloseHandle(o.release);
    s=stamp(3);assert(audio_release_probe_boundary(&s)==AR_B_INVALID && !g_ar.live);assert(!lock_depth);
}
static void refusal(const char *kind){fixture_setup(1);ArBoundaryStamp s=stamp(0);unsigned tr=tries;
    if(!strcmp(kind,"recursive")){mock_enter(&g_lock);ar_scope_enter();assert(audio_release_probe_boundary(&s)==AR_B_REENTRANT);ar_scope_leave();mock_leave(&g_lock);}
    else if(!strcmp(kind,"uninit")){g_ar_lock_ready=0;assert(audio_release_probe_boundary(&s)==AR_B_UNINITIALIZED);}
    else if(!strcmp(kind,"held")){s.valid=0;assert(audio_release_probe_boundary(&s)==AR_B_INVALID);}
    else if(!strcmp(kind,"apbusy")){g_ap_owner=1;holds(1);qp_capture(118);holds(0);assert(!g_ar.live && !g_ar.boundaries[0].ready);}
    else assert(0);assert(tries==tr);
}
static void missing_seed_intent(void){fixture_setup(1);open_audio();mock_enter(&g_lock);ar_scope_enter();ar_begin(AR_CALL_STOP_FORCE,NULL);ar_intent(g_wave);ar_end();ar_scope_leave();mock_leave(&g_lock);
    boundary_begin();assert(!g_ar.live && g_ar.boundaries[0].b.r.stamp_status==AR_B_INFLIGHT);}
static void overflow(int queue){fixture_setup(1);open_audio();boundary_begin();
    if(queue){for(unsigned round=0;round<2;round++){for(unsigned i=0;i<64;i++)append_audio(i);Ctx c={0};audio_StopAudioOut(&c);}
        assert(g_rel_tail-g_rel_head==128 && (g_ar.errors&AR_E_RELEASE_OVERRUN));raw_get();assert(g_rel_head==1);}
    else {ArRecord first=g_ar.events[0].r;for(unsigned i=0;i<900;i++)raw_get();
        assert(g_ar.count==4096 && g_ar.drops && g_ar.record==g_ar.count+g_ar.drops && (g_ar.errors&AR_E_OBSERVER_OVERFLOW));
        assert(!memcmp(&first,&g_ar.events[0].r,sizeof first));}
    boundary_gap();boundary_end(0);assert(g_ar.footer.failed && g_ar.boundaries[4].ready);
}
static void zero_pointer(void){fixture_setup(1);open_audio();append_audio(0);g_slots[0].guest=0;g_ar.play[0].guest=0;
    boundary_begin();Ctx c={0};audio_StopAudioOut(&c);raw_get();ArRecord *r=last_kind(AR_POP);assert(r->popped && !r->returned && (g_ar.errors&AR_E_OCCURRENCE));}
static void stale_stamp(void){fixture_setup(1);open_audio();boundary_begin();caller();
    AudioTicket id=r1_audio_import_enter(&producer,1884);r1_audio_selected(&producer,id,AB_IMPORT,IMPORT_BASE+1884ULL*IMPORT_SLOT,audio_GetReleasedAudioOutBuffer,NULL,NULL,1884,0,dyn_syms[1884].name);
    ArStamp a={0};assert(r1_audio_release_stamp(&producer,audio_GetReleasedAudioOutBuffer,&a)==AR_STAMP_VALID);
    holds(1);qp_capture(119);qp_load_begin(118);qp_load_ready(118);holds(0);
    mock_enter(&g_lock);ar_scope_enter();ar_begin(AR_CALL_GETTER,&a);ar_note(AR_PRECOLLECT);ar_getter_post(0,0);ar_pop(g_rel_head,0,0);ar_end();ar_scope_leave();mock_leave(&g_lock);
    assert(last_kind(AR_POP)->ap_epoch==a.epoch && last_kind(AR_POP)->ap_generation!=g_ap_generation);
    r1_audio_import_return(&producer,1884,id);assert(g_ap_errors&AP_STALE);boundary_end(1);
}
static void stamps(const char *mode){fixture_setup(1);open_audio();boundary_begin();caller();
    AudioTicket id=r1_audio_import_enter(&producer,1884);r1_audio_selected(&producer,id,AB_IMPORT,IMPORT_BASE+1884ULL*IMPORT_SLOT,audio_GetReleasedAudioOutBuffer,NULL,NULL,1884,0,dyn_syms[1884].name);
    ApTicket *t=NULL;for(unsigned i=0;i<8;i++)if(g_ap_tickets[i].id==id)t=&g_ap_tickets[i];assert(t);
    if(!strcmp(mode,"valid")){}
    else if(!strcmp(mode,"epoch"))t->epoch++;
    else if(!strcmp(mode,"generation"))t->generation++;
    else if(!strcmp(mode,"actor"))t->actor++;
    else if(!strcmp(mode,"ctx"))t->ctx=&consumer;
    else if(!strcmp(mode,"purpose"))t->purpose=2;
    else if(!strcmp(mode,"sym"))t->sym=1887;
    else if(!strcmp(mode,"bind"))t->binds=0;
    else if(!strcmp(mode,"double"))t->binds=2;
    else if(!strcmp(mode,"fn"))t->binding.fn++;
    else if(!strcmp(mode,"family"))t->binding.family=AB_HOST;
    else if(!strcmp(mode,"index"))t->binding.index++;
    else if(!strcmp(mode,"offset"))t->binding.offset++;
    else if(!strcmp(mode,"user"))t->binding.user=1;
    else if(!strcmp(mode,"hook"))t->binding.status=AB_HOOK_UNRESOLVED;
    else if(!strcmp(mode,"lr"))producer.x[30]++;
    else if(!strcmp(mode,"sp"))producer.x[31]++;
    else if(!strcmp(mode,"fp"))producer.x[29]++;
    else if(!strcmp(mode,"zero"))t->id=0;
    else if(!strcmp(mode,"two")){assert(t==&g_ap_tickets[0]);g_ap_tickets[1]=*t;g_ap_tickets[1].id++;}
    else if(!strcmp(mode,"cas"))g_ap_owner=1;
    else assert(0);
    Ctx before=producer;ArStamp a;SetLastError(817);int result=r1_audio_release_stamp(&producer,audio_GetReleasedAudioOutBuffer,&a);
    assert(GetLastError()==817 && !memcmp(&before,&producer,sizeof before));
    assert(result==(!strcmp(mode,"valid")?AR_STAMP_VALID:!strcmp(mode,"lr")?AR_STAMP_OTHER_CALL:AR_STAMP_INVALID));
}
static void disabled(int off){fixture_setup(!off);
    if(off){Ctx *bad=(Ctx *)(uintptr_t)1;ArStamp *s=(ArStamp *)(uintptr_t)1;ArView *v=(ArView *)(uintptr_t)1;
        unsigned tr=tries;assert(!r1_audio_release_stamp(bad,(ImportFn)(uintptr_t)1,s));assert(!audio_release_probe_view(v));audio_release_probe_boundary((void *)(uintptr_t)1);assert(tries==tr);}
    open_audio();for(unsigned i=0;i<4;i++)append_audio(i);start_audio();if(!off)boundary_begin();
    for(unsigned i=0;i<4;i++){g_slots[i].hdr.dwFlags=WHDR_DONE;raw_get();}
    Ctx c={0};audio_StopAudioOut(&c);audio_CloseAudioOut(&c);raw_get();
    /* Pointer addresses differ between EXEs. Hash semantic slot bytes separately
     * from addresses, then print exact calls/statistics/LastError. */
    printf("SEM %u %u %u %u %d %d %llu %llu %u %u %lu\n",g_head,g_tail,g_rel_head,g_rel_tail,g_open,g_started,
        g_total_appended,g_total_released,g_sec_polls,g_sec_empty,(unsigned long)GetLastError());
    for(unsigned i=0;i<4;i++)printf("SLOT %u %u %d %lld %lu\n",i,g_slots[i].frames,g_slots[i].prepared,g_slots[i].due,(unsigned long)g_slots[i].hdr.dwFlags);
    /* Compare every Slot byte after canonicalizing only process addresses. */
    Slot slots[64];memcpy(slots,g_slots,sizeof slots);uint64_t rel[64];memcpy(rel,g_released,sizeof rel);
    for(unsigned i=0;i<64;i++){
        if(slots[i].pcm)slots[i].pcm=(void *)(uintptr_t)1;if(slots[i].hdr.lpData)slots[i].hdr.lpData=(void *)(uintptr_t)1;
        for(unsigned j=0;j<130;j++){if(slots[i].guest==(uintptr_t)guest_buffers[j])slots[i].guest=j+1;if(rel[i]==(uintptr_t)guest_buffers[j])rel[i]=j+1;}
    }
    uint64_t hash=0xcbf29ce484222325ULL;const unsigned char *p=(const unsigned char *)slots;
    for(size_t i=0;i<sizeof slots;i++)hash=(hash^p[i])*0x100000001b3ULL;p=(const unsigned char *)rel;
    for(size_t i=0;i<sizeof rel;i++)hash=(hash^p[i])*0x100000001b3ULL;printf("BYTES %016llx\n",(unsigned long long)hash);
    for(unsigned i=0;i<trace_n;i++)printf("%u,",trace[i]);putchar('\n');
}
static void late(void){fixture_setup(1);boundary_begin();assert(!get_audio(1));boundary_gap();assert(!get_audio(0));boundary_end(0);
    ArFooter f=g_ar.footer;audio_release_probe_late(1);assert(g_ar.late && !memcmp(&f,&g_ar.footer,sizeof f));ap_drain();fputs(logs,stdout);}
static void wrap(void){fixture_setup(1);open_audio();g_head=g_tail=g_rel_head=g_rel_tail=0xfffffffeU;
    append_audio(0);append_audio(1);append_audio(2);start_audio();boundary_begin();
    Ctx c={0};audio_StopAudioOut(&c);for(unsigned i=0;i<3;i++)assert(get_audio(i&1));
    assert(g_head==1 && g_tail==1 && g_rel_head==1 && g_rel_tail==1 && !g_ar.errors);boundary_gap();assert(!get_audio(1));boundary_end(1);}
static void end_busy(int freeze_busy){fixture_setup(1);boundary_begin();assert(!get_audio(0));boundary_gap();assert(!get_audio(1));
    Owner o={&g_lock,CreateEventA(NULL,0,0,NULL),CreateEventA(NULL,0,0,NULL)};HANDLE t=CreateThread(NULL,0,real_owner,&o,0,NULL);
    assert(t && real_wait(o.acquired,3000)==WAIT_OBJECT_0 && SuspendThread(t)!=(DWORD)-1);
    unsigned tr=tries;holds(1);qp_capture(119);holds(0);assert(tries==tr+1 && g_ar.boundaries[4].b.r.stamp_status==AR_B_BUSY && !g_ar.sealed);
    if(!freeze_busy){assert(ResumeThread(t)!=(DWORD)-1);SetEvent(o.release);assert(real_wait(t,3000)==WAIT_OBJECT_0);}
    tr=tries;ap_drain();assert(tries==tr+1 && (freeze_busy?!g_ar.frozen:g_ar.footer.failed && !g_ar.footer.sealed));
    tr=tries;ap_drain();assert(tries==tr);
    if(freeze_busy){assert(ResumeThread(t)!=(DWORD)-1);SetEvent(o.release);assert(real_wait(t,3000)==WAIT_OBJECT_0);}
    CloseHandle(t);CloseHandle(o.acquired);CloseHandle(o.release);fputs(logs,stdout);
}
static void counter_wrap(void){fixture_setup(1);open_audio();boundary_begin();g_ar.write=UINT64_MAX;append_audio(0);
    assert(g_ar.write==UINT64_MAX && !g_ar.play[0].id && (g_ar.errors&AR_E_WRAP));append_audio(1);assert(g_ar.write==UINT64_MAX && !g_ar.play[1].id);}
static void init_state(void){fixture_setup(0);g_open=1;unsigned tr=tries;assert(!audio_release_probe_configure());
    assert(tries==tr+1 && (g_ar.errors&AR_E_INIT_STATE) && !g_ar.on);}
static void late_reenter(void){ap_drain();}
static void drain_reentrant(void){fixture_setup(1);boundary_begin();assert(!get_audio(1));boundary_gap();assert(!get_audio(0));
    holds(1);qp_capture(119);holds(0);log_inject=late_reenter;ap_drain();size_t len=log_len;ap_drain();assert(log_len==len);}
static void bad_mode(const char *s){fixture_setup(0);_putenv(s);ap_init();assert(0);}
static void append_failures(void){fixture_setup(1);open_audio();boundary_begin();
    prepare_result=9;append_audio(0);assert(!g_slots[0].prepared && last_kind(AR_APPEND)->due==g_clock_due);
    prepare_result=0;write_result=8;append_audio(1);assert(!g_slots[1].prepared);
    write_result=0;append_audio(2);assert(g_slots[2].prepared);
    Ctx c={0};c.x[1]=(uintptr_t)guest_buffers[3];wr64(c.x[1]+8,0);unsigned tail=g_tail;audio_AppendAudioOutBuffer(&c);
    assert(!c.x[0] && g_tail==tail && last_kind(AR_APPEND_REFUSE)->decision==AR_DEC_REFUSED);
}
static void prefix(int missing){fixture_setup(1);open_audio();caller();
    AudioTicket id=r1_audio_import_enter(&producer,1884);assert(id);
    r1_audio_selected(&producer,id,AB_IMPORT,IMPORT_BASE+1884ULL*IMPORT_SLOT,audio_GetReleasedAudioOutBuffer,NULL,NULL,1884,0,dyn_syms[1884].name);
    if(missing)audio_GetReleasedAudioOutBuffer(&producer);
    boundary_begin();tid=101;
    if(!missing)audio_GetReleasedAudioOutBuffer(&producer);
    r1_audio_import_return(&producer,1884,id);assert(!g_ap_errors);
    boundary_gap();assert(!get_audio(0));boundary_end(1);
    if(!missing)assert(g_ar.events[1].r.stamp_status==AR_STAMP_PREFIX && !g_ar.events[1].r.ap_enter_event);
}
static void postseal(void){fixture_setup(1);open_audio();boundary_begin();assert(!get_audio(0));boundary_gap();assert(!get_audio(1));boundary_end(0);
    ArFooter frozen=g_ar.footer;uint64_t count=g_ar.count;
    for(unsigned round=0;round<2;round++){for(unsigned i=0;i<64;i++)append_audio(i);Ctx c={0};audio_StopAudioOut(&c);}
    assert(g_rel_tail-g_rel_head==128 && !memcmp(&frozen,&g_ar.footer,sizeof frozen) && g_ar.count==count && !g_ar.late && !g_ar.errors);
    size_t len=log_len;ap_drain();assert(log_len==len);
}
static void recursive_getter(void){fixture_setup(1);boundary_begin();caller();
    mock_enter(&g_lock);ar_scope_enter();ar_begin(AR_CALL_APPEND,NULL);g_ar.stamp.ticket=123;
    g_ap_owner=1;audio_GetReleasedAudioOutBuffer(&producer);g_ap_owner=0;
    assert(!g_ap_errors && (g_ar.errors&AR_E_REENTRANT) && (g_ar.errors&AR_E_CONTEXT_OVERLAP));
    assert(g_ar.stamp.ticket==123 && g_ar.current_op);ar_end();ar_scope_leave();mock_leave(&g_lock);assert(!lock_depth);
}
static void activation_owner(void){assert(audio_release_probe_enabled());native_poll();assert(!t_ar_scope && !g_ar.current_op);}
static void activation(void){leave_inject=activation_owner;fixture_setup(1);assert(!t_ar_scope && !g_ar.current_op && !g_ar.errors);}
int main(int argc,char **argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);assert(argc==2);const char *m=argv[1];
    if(!strcmp(m,"complete"))complete();else if(!strcmp(m,"predicates"))predicates();else if(!strcmp(m,"lifecycle"))lifecycle(0);
    else if(!strcmp(m,"ambiguous"))lifecycle(1);else if(!strcmp(m,"busy"))busy_case();
    else if(!strcmp(m,"recursive") || !strcmp(m,"uninit") || !strcmp(m,"held") || !strcmp(m,"apbusy"))refusal(m);
    else if(!strcmp(m,"inflight"))missing_seed_intent();else if(!strcmp(m,"overflow"))overflow(0);else if(!strcmp(m,"overrun"))overflow(1);
    else if(!strcmp(m,"zero"))zero_pointer();else if(!strcmp(m,"stale"))stale_stamp();else if(!strncmp(m,"stamp-",6))stamps(m+6);
    else if(!strcmp(m,"disabled"))disabled(1);else if(!strcmp(m,"enabled-semantics"))disabled(0);
    else if(!strcmp(m,"late"))late();else if(!strcmp(m,"wrap"))wrap();else if(!strcmp(m,"end-busy"))end_busy(0);
    else if(!strcmp(m,"freeze-busy"))end_busy(1);else if(!strcmp(m,"counter-wrap"))counter_wrap();else if(!strcmp(m,"init-state"))init_state();
    else if(!strcmp(m,"drain-reentrant"))drain_reentrant();else if(!strcmp(m,"append-failures"))append_failures();
    else if(!strcmp(m,"prefix"))prefix(0);else if(!strcmp(m,"prefix-missing"))prefix(1);
    else if(!strcmp(m,"postseal"))postseal();
    else if(!strcmp(m,"recursive-getter"))recursive_getter();
    else if(!strcmp(m,"activation"))activation();
    else if(!strcmp(m,"bad-mode"))bad_mode("SSBU_RB_AUDIO_RELEASE_QUEUE=2");
    else if(!strcmp(m,"bad-ap")){_putenv("SSBU_RB_AUDIO_CONTINUATION=0");_putenv("SSBU_RB_AUDIO_RELEASE_QUEUE=1");ap_init();assert(0);}
    else assert(0);
    fprintf(stderr,"SOURCE_PASS %s\n",m);return 0;
}
