/* Fake ONLY loader/inventory boundaries; the admission and host wrapper bodies
 * below are verbatim production sources. No DLL/game is built or loaded. */
static struct { uint64_t addr;uint32_t kind,word; } fixture_sites[2]={{AUDIO_POSTLOAD_PC,2,0}};
static int fixture_site_count=1,fixture_table_count=1,fixture_pin_calls,fixture_site_reads;
static void fixture_caller(Ctx *c) { (void)c; }
static FnEntry fixture_main_table[2]={{0x7103987e40ULL,fixture_caller}};
static const FnEntry (*game_fn_table_p)[]=(const FnEntry (*)[])fixture_main_table;
static const int *game_fn_table_count_p=&fixture_table_count;
static int fixture_rpm_fail,fixture_bad_name;
static SIZE_T fixture_guest_reads;
static BOOL fixture_read_process(HANDLE process,LPCVOID p,LPVOID out,SIZE_T n,SIZE_T *got) {
    if((uintptr_t)p==0x7106dd57b4ULL)fixture_guest_reads++;
    if(fixture_rpm_fail || (site_mode==14 && p==fixture_sites)){*got=0;SetLastError(0xabc);return 0;}
    if(fixture_bad_name && n==96){memset(out,'x',n);*got=n;return 1;}
    BOOL result=ReadProcessMemory(process,p,out,n,got);SetLastError(0xabc);return result;
}
#define ReadProcessMemory fixture_read_process
static BOOL fixture_module(DWORD flags,LPCSTR p,HMODULE *out) {
    HMODULE main=GetModuleHandleA(NULL);*out=main;
    if(flags & GET_MODULE_HANDLE_EX_FLAG_PIN)fixture_pin_calls++;
    if(!p)return 0;
    if((site_mode==6 && (const void *)p==fixture_sites) ||
       (site_mode==7 && (const void *)p==&fixture_site_count) ||
       (site_mode==8 && (const void *)p==(void *)fixture_caller) ||
       (site_mode==9 && !(flags & GET_MODULE_HANDLE_EX_FLAG_PIN) && (const void *)p==fixture_main_table)) *out=(HMODULE)(uintptr_t)0xdeadbeef;
    SetLastError(0xddd);return 1;
}
static FARPROC fixture_export(HMODULE m,LPCSTR name) {
    assert(m==GetModuleHandleA(NULL));
    if(!strcmp(name,"sky_site_table"))return site_mode==1?NULL:(FARPROC)(void *)fixture_sites;
    if(!strcmp(name,"sky_site_count"))return (FARPROC)(void *)&fixture_site_count;
    if(!strcmp(name,"game_bind"))return (FARPROC)fixture_caller;
    if(!strcmp(name,"game_data_bind"))return site_mode==12?NULL:(FARPROC)fixture_caller;
    if(!strcmp(name,"game_eh_bind"))return site_mode==13?NULL:(FARPROC)fixture_caller;
    return NULL;
}
#define GetModuleHandleExA fixture_module
#define GetProcAddress fixture_export
/* SITE_ADMISSION_SOURCE */
#undef GetModuleHandleExA
#undef GetProcAddress
static unsigned plugin_calls;
static int plugin_changes_error;
static void sky_site_inline(Ctx *c,uint64_t pc) {
    (void)c;(void)pc;plugin_calls++;if(plugin_changes_error)SetLastError(0xfeed);
}
/* HOST_INLINE_SOURCE */
static struct { void (*site_inline)(Ctx *,uint64_t); } host={game_site_inline};
/* SHIM_INLINE_SOURCE */
/* Hook identity is covered through the actual existing hook validator in the
 * private runner, in addition to these AP-init gate controls. */
void hook_require_audio_sites(void) {
    if(site_mode==15 || site_mode==16 || site_mode==17)r1_hold_fatal("audio instruction/build identity");
}
