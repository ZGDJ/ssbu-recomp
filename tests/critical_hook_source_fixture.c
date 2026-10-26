/* Exact production policy/callers, synthetic tables and guest/patch boundaries.
 * No game bytes, native patch execution, loader concurrency or gameplay. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
__declspec(dllimport) unsigned long __stdcall SetErrorMode(unsigned long);
#define SEM_FAILCRITICALERRORS 1
#define SEM_NOGPFAULTERRORBOX 2
typedef long long LONG64;
static void InterlockedExchange64(volatile LONG64 *p,LONG64 v) { *p=v; }
#include <crtdbg.h>
typedef struct { int unused; } Ctx;
typedef void (*ImportFn)(Ctx *);
typedef void (*HookFn)(Ctx *, void *);
typedef struct { uint64_t addr; ImportFn fn; } FnEntry;
typedef struct { const char *name; uint64_t value; int defined; } DynSym;
typedef struct { const char *name; uint64_t base; unsigned file_size; uint8_t build_id[20]; } NroInfo;
typedef struct { const NroInfo *info; FnEntry *fns; int fn_count; DynSym *syms; int sym_count; int loaded, plugin; } NroModule;
typedef struct { uint8_t *target; } HkSite;
/* LAYER_TYPE */
enum { HK_FREE, HK_PENDING, HK_ON, HK_OFF };
enum { GAME_13_0_4, GAME_13_0_5 };
#define GUEST_BASE 0x7100000000ull
#define NRO_BASE 0x7200000000ull
#define GA(a) ga(a)
#define LOG printf
/* IDENTITY */
static int g_game_build = GAME_13_0_5, g_hk_lock, g_hk_layers, g_hk_pending;
static int attach_fail_at, expected_attach, attach_fail, allocation_fail, attach_count, bad_guest, read_count, g_main_hash=1;
static char g_hk_error[200] = "scripted patch boundary";
static HkLayer layers[16];
static HkSite *site_slot;
static FnEntry main_entries[80]; static FnEntry *fn_table=main_entries; static int fn_table_count;
static DynSym main_symbols[4]; static DynSym *dyn_syms=main_symbols; static int dyn_sym_count;
static NroModule modules[3]; static NroModule *g_mods=modules; static int g_mod_count=2;
static NroInfo infos[3]; static FnEntry module_entries[3][4]; static DynSym module_symbols[3][4];
static void original(Ctx *c) { (void)c; }
static void replacement(Ctx *c, void *u) { (void)c; (void)u; }
static uint64_t ga(uint64_t ref) {
    if (g_game_build == GAME_13_0_4) return ref;
    for (size_t i=0;i<sizeof g_hk_critical_main/sizeof g_hk_critical_main[0];i++)
        if(g_hk_critical_main[i].reference==ref)return g_hk_critical_main[i].address;
    return ref;
}
static int battle_on;
static uint64_t rd64(uint64_t addr) { return addr==100?200:addr==200?300:0; }
static uint64_t hook_address(const char *name) { (void)name;return 100; }
static uint8_t rd8(uint64_t addr) { if(addr==300+0xd2)return (uint8_t)battle_on; read_count++; return (uint8_t)bad_guest; }
static void AcquireSRWLockExclusive(int *lock) { (void)lock; }
static void ReleaseSRWLockExclusive(int *lock) { (void)lock; }
static HkLayer *hk_layer(int id) { return id>0 && id<=g_hk_layers ? &layers[id-1] : NULL; }
static int hk_layer_new(void) { return allocation_fail ? 0 : ++g_hk_layers; }
static HkSite **hk_site_slot(uint64_t addr) { (void)addr; return &site_slot; }
static ImportFn function_at(uint64_t addr) {
    for(int i=0;i<fn_table_count;i++)if(fn_table[i].addr==addr)return fn_table[i].fn;
    for(int j=0;j<g_mod_count;j++)if(modules[j].loaded)
        for(int i=0;i<modules[j].fn_count;i++)if(modules[j].fns[i].addr==addr)return modules[j].fns[i].fn;
    return NULL;
}
static int hk_attach(int id,uint64_t addr) {
    attach_count++;
    if(attach_fail || (attach_fail_at && attach_count == attach_fail_at) || !function_at(addr))return 0;
    HkLayer *l=hk_layer(id);l->addr=addr;l->state=HK_ON;l->orig=original;
    if(l->orig_out)*l->orig_out=l->orig;
    return id;
}
static void ro_init_tables(void) { g_main_hash=1; }
static uint64_t hk_address_of(const char *name) {
    for(int j=0;j<g_mod_count;j++)if(modules[j].loaded)
        for(int i=0;i<modules[j].sym_count;i++)if(modules[j].syms[i].defined&&!strcmp(name,modules[j].syms[i].name))
            return modules[j].info->base+modules[j].syms[i].value;
    return 0;
}

static void fatal_oracle(void) {
    if (attach_count != expected_attach) {
        fprintf(stderr, "FATAL_ORACLE_FAILED attachments=%d expected=%d\n", attach_count, expected_attach);
        exit(91);
    }
    fprintf(stderr, "CRITICAL_HOOK_FATAL_ORACLE_PASS attachments=%d\n", attach_count);
    fflush(stderr); fflush(stdout);
    abort();
}
#define abort fatal_oracle
/* SOURCE */
#undef abort
static int g_ra,g_ra_skip,g_ra_submit_mode,g_park_ms,g_mark,g_rgs_skip,g_rgs_n,g_rgs_k,g_rgs_warm;
static double g_ra_park_ms; static uint64_t g_ra_site;
static ImportFn g_orig_submit,g_orig_kick,g_orig_kick2,g_orig_line;
static int ra_watchdog_prepare(void){return 1;} static void r1_hold_fatal(const char *s){(void)s;abort();}
#define ra_submit_hook replacement
#define ra_kick replacement
#define ra_kick2 replacement
#define ra_line replacement
static void ra_report(void){}
static void rgs_clock_init(void){}
static int mark_bind(void){return 1;} static int ls_bind(void){return 1;}
static int rgs_wanted(void){return 0;} static int rbg_on(void){return 0;}
static void rbn_init(void){} static void rgs_lite_init(void){}
/* RA_SOURCE */
/* FIGHT_ON_SOURCE */
static int g_lp_routing_ready, resource_calls, g_lps_n;
static void *g_lp, *g_lpm, *g_lpb_p, *g_lpb_s;
static uint64_t g_lps[16][2];
#define LP_RES 4096
#define LP_SN 16
typedef struct { int unused; } LpMeta;
static ImportFn g_lpo_aa,g_lpo_pm,g_lpo_ra,g_lpo_fr,g_lpo_ms;
#define lph_aa replacement
#define lph_pm replacement
#define lph_ra replacement
#define lph_fr replacement
#define lph_ms replacement
static int ls_enabled=1;
static int ls_on(void) { return ls_enabled; }
static int lp_resources_prepare(void) { resource_calls++;return 1; }
static void InterlockedExchange(int *p,int v) { *p=v; }
static void presentation_fatal(void) {
    assert(!g_lp_routing_ready);
    assert(!resource_calls); /* custom route must refuse before reserving resources */
    fatal_oracle();
}
#define abort presentation_fatal
/* PRESENTATION_SOURCE */
#undef abort
static int r1_enabled, trace_enabled, g_audio_free, g_prot, g_mcheck, g_fast, g_fcheck, g_learn;
static int g_r1_keep_fibers, g_wait_idle, g_busy_log, g_n, g_k, g_p, g_c;
static ImportFn g_orig_frame_end;
#define trace_only_frame_end replacement
#define r1_frame_end replacement
static int r1_on(void) { return r1_enabled; }
static int fight_trace_enabled(void) { return trace_enabled; }
static void fight_trace_fail(const char *s) { (void)s; }
static int r1_veh(void) { return 0; }
static void *AddVectoredExceptionHandler(int first,int (*handler)(void)) { (void)first;(void)handler;return (void*)1; }
static void r1_stats_report(void) {}
static void prot_prepare(void) {}
static int ra_wanted(void) { return 0; }
/* R1_INIT_SOURCE */
static void setup(void) {
    for(size_t i=0;i<sizeof g_hk_critical_main/sizeof g_hk_critical_main[0];i++)
        if(!g_hk_critical_main[i].site)main_entries[fn_table_count++]=(FnEntry){g_hk_critical_main[i].address,original};
    for(int i=0;i<2;i++) {
        infos[i].name=i?"other":"lua2cpp_common";infos[i].base=NRO_BASE+0x200000*i;infos[i].file_size=0x200000;
        modules[i]=(NroModule){&infos[i],module_entries[i],1,module_symbols[i],1,0,0};
        module_entries[i][0]=(FnEntry){infos[i].base+HK_CRITICAL_FIGHTER_OFFSET,original};
        module_symbols[i][0]=(DynSym){HK_CRITICAL_FIGHTER_NAME,HK_CRITICAL_FIGHTER_OFFSET,1};
    }
    _putenv("SSBU_LS_ROUTE=");
    _putenv("SSBU_RUNAHEAD_SITE=");_putenv("SSBU_RUNAHEAD_MODE=");
    _putenv("SSBU_RUNAHEAD_PARK_MS=");_putenv("SSBU_RUNAHEAD_SKIP=");
}
static int required_name(ImportFn *orig) { return hook_install_name_required("lua2cpp_common",HK_CRITICAL_FIGHTER_NAME,replacement,NULL,orig); }
int main(int argc,char **argv) {
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    _set_abort_behavior(0, _WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    assert(argc==2);setup(); const char *test=argv[1]; ImportFn orig=NULL;uint64_t addr=0x71038701e0ull;
    if(!strcmp(test,"main-valid")) { assert(hook_install_required(addr,replacement,NULL,&orig));assert(orig==original&&attach_count==1); }
    else if(!strcmp(test,"all-main-valid")) {
        for(int i=0;i<fn_table_count;i++){g_hk_layers=0;assert(hook_install_required(fn_table[i].addr,replacement,NULL,&orig));}
        hook_require_run_ahead_sites(0x710374a0d4ull);
    }
    else if(!strcmp(test,"version")) { g_game_build=GAME_13_0_4;hook_install_required(addr,replacement,NULL,&orig);goto unexpected; }
    else if(!strcmp(test,"missing")) { fn_table_count=0;hook_install_required(addr,replacement,NULL,&orig);goto unexpected; }
    else if(!strcmp(test,"null")) { main_entries[0].fn=NULL;hook_install_required(addr,replacement,NULL,&orig);goto unexpected; }
    else if(!strcmp(test,"duplicate")||!strcmp(test,"duplicate-null")) {
        main_entries[fn_table_count++]=(FnEntry){addr,!strcmp(test,"duplicate")?original:NULL};
        hook_install_required(addr,replacement,NULL,&orig);goto unexpected;
    }
    else if(!strcmp(test,"fingerprint")) { bad_guest=1;hook_install_required(addr,replacement,NULL,&orig);goto unexpected; }
    else if(!strcmp(test,"unlisted")) { hook_install_required(addr+4,replacement,NULL,&orig);goto unexpected; }
    else if(!strcmp(test,"attach")) { expected_attach=1;attach_fail=1;hook_install_required(addr,replacement,NULL,&orig);goto unexpected; }
    else if(!strcmp(test,"capacity")) { allocation_fail=1;hook_install_required(addr,replacement,NULL,&orig);goto unexpected; }
    else if(!strcmp(test,"site-override")) { hook_require_run_ahead_sites(0x710374a0d8ull);goto unexpected; }
    else if(!strcmp(test,"site-fingerprint")) { bad_guest=1;hook_require_run_ahead_sites(0x710374a0d4ull);goto unexpected; }
    else if(!strcmp(test,"ra-refusal")) { expected_attach=1;attach_fail=1;ra_init();goto unexpected; }
    else if(!strcmp(test,"ra-second-worker")) { expected_attach=2;attach_fail_at=2;ra_init();goto unexpected; }
    else if(!strcmp(test,"presentation-site-valid")) { hook_require_presentation_sites(); }
    else if(!strcmp(test,"presentation-site-fingerprint")) { bad_guest=1;hook_require_presentation_sites();goto unexpected; }
    else if(!strcmp(test,"ra-site-override")) { _putenv("SSBU_RUNAHEAD_SITE=710374a0d8");ra_init();goto unexpected; }
    else if(!strcmp(test,"ra-valid")) { ra_init();assert(attach_count==2&&g_hk_pending==1); }
    else if(!strcmp(test,"ra-submit")) { _putenv("SSBU_RUNAHEAD_MODE=submit");ra_init();assert(attach_count==3&&g_hk_pending==1); }
    else if(!strcmp(test,"no-hooks-1304")) { g_game_build=GAME_13_0_4;r1_init();assert(!attach_count&&!read_count); }
    else if(!strcmp(test,"frame-trace-off-refusal")) { r1_enabled=1;ls_enabled=0;expected_attach=1;attach_fail=1;r1_init();goto unexpected; }
    else if(!strcmp(test,"frame-trace-only-refusal")) { trace_enabled=1;expected_attach=1;attach_fail=1;r1_init();goto unexpected; }
    else if(!strcmp(test,"frame-valid")) { r1_enabled=1;ls_enabled=0;r1_init();assert(attach_count==1&&g_orig_frame_end==original); }
    else if(!strcmp(test,"fight-pending")) { required_name(&orig);battle_on=1;ra_fight_on();goto unexpected; }
    else if(!strcmp(test,"fight-menu")) { required_name(&orig);assert(!ra_fight_on()); }
    else if(!strcmp(test,"fight-ready")) { modules[0].loaded=1;required_name(&orig);battle_on=1;assert(ra_fight_on()); }
    else if(!strcmp(test,"presentation-custom")) { _putenv("SSBU_LS_ROUTE=unqualified.txt");ls_init();goto unexpected; }
    else if(!strcmp(test,"presentation-off")) { _putenv("SSBU_LS_ROUTE=0");ls_init();assert(!resource_calls&&!attach_count); }
    else if(!strcmp(test,"presentation-valid")) { ls_init();assert(resource_calls==1&&attach_count==5&&g_lp_routing_ready); }
    else if(!strcmp(test,"ready-pending")) { required_name(&orig);hook_require_critical_ready();goto unexpected; }
    else if(!strcmp(test,"ready-unregistered")) { hook_require_critical_ready();goto unexpected; }
    else if(!strcmp(test,"ready-unloaded")) { expected_attach=1; modules[0].loaded=1;required_name(&orig);modules[0].loaded=0;hook_require_critical_ready();goto unexpected; }
    else if(!strcmp(test,"ready-valid")) { modules[0].loaded=1;required_name(&orig);hook_require_critical_ready(); }
    else if(!strcmp(test,"generic")) {
        /* Existing generic deferred failure is still best-effort. */
        int id=hook_install_name(HK_CRITICAL_FIGHTER_NAME,replacement,NULL,&orig);assert(id&&g_hk_pending==1);
        modules[1].loaded=1;modules[1].sym_count=2;module_symbols[1][1]=module_symbols[1][0];attach_fail=1;
        hook_module_loaded(&modules[1]);assert(attach_count==1&&hk_layer(id)->state==HK_FREE);
    }
    else {
        int deferred=!strncmp(test,"deferred-",9), later=!strncmp(test,"later-",6);
        if(!deferred)modules[0].loaded=1;
        int id=0;
        if(later || strstr(test,"attach"))expected_attach=1;
        if(deferred||later) { id=required_name(&orig);assert(id);if(deferred)assert(!orig&&g_hk_pending==1);modules[0].loaded=1; }
        if(strstr(test,"missing"))modules[0].sym_count=0;
        if(strstr(test,"duplicate-null")) { module_entries[0][1]=module_entries[0][0];module_entries[0][1].fn=NULL;modules[0].fn_count=2; }
        else if(strstr(test,"duplicate")) { module_symbols[0][1]=module_symbols[0][0];modules[0].sym_count=2; }
        if(strstr(test,"wrong-module"))modules[1].loaded=1;
        if(strstr(test,"wrong-offset"))module_symbols[0][0].value+=4;
        if(strstr(test,"null-entry"))module_entries[0][0].fn=NULL;
        if(strstr(test,"missing-entry"))modules[0].fn_count=0;
        if(strstr(test,"fingerprint"))bad_guest=1;
        if(strstr(test,"build-id"))infos[0].build_id[0]=1;
        if(strstr(test,"version"))g_game_build=GAME_13_0_4;
        if(strstr(test,"attach"))attach_fail=1;
        if(strstr(test,"registry"))infos[1].name="lua2cpp_common";
        if(strstr(test,"main-export")) { main_symbols[0]=(DynSym){HK_CRITICAL_FIGHTER_NAME,1,1};dyn_sym_count=1; }
        if(!strcmp(test,"later-reload")) {
            modules[0].loaded=0;hook_module_loaded(&modules[1]);modules[0].loaded=1;
            hook_module_loaded(&modules[0]);assert(attach_count==1&&orig==original);goto pass;
        }
        if(deferred||later)hook_module_loaded(&modules[0]);else id=required_name(&orig);
        if(!strcmp(test,"named-valid")||!strcmp(test,"deferred-valid")) {
            assert(attach_count==1&&orig==original&&g_hk_pending==0);
            assert(!hook_remove(id)&&hk_layer(id)->state==HK_ON);
        } else goto unexpected;
    }
pass: puts("CRITICAL_HOOK_SOURCE_PASS");return 0;
unexpected: puts("UNEXPECTED_SUCCESS");return 99;
}
