/* Cold AP admission only. Resolve the actual bound main table, never a filename
 * or the Skyline/NRO registry. PIN is process-lifetime authority, not a claim
 * about arbitrary in-process writes. Kept separate for exact-source tests. */
static AudioPostloadIdentity g_game_audio_postload_identity;
const AudioPostloadIdentity *game_audio_postload_identity(void) {
    return g_game_audio_postload_identity.module?&g_game_audio_postload_identity:NULL;
}
#ifdef _WIN32
#include <windows.h>
typedef struct { uint64_t addr; uint32_t kind,word; } AudioPostloadSite;
static HMODULE audio_site_owner(const void *p) {
    HMODULE m=NULL;
    if(!p || !GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
        GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,(LPCSTR)p,&m))return NULL;
    return m;
}
static int audio_site_read(HMODULE m,const void *p,void *out,size_t n) {
    uintptr_t a=(uintptr_t)p;SIZE_T got=0;
    if(!n || a>UINTPTR_MAX-(n-1) || audio_site_owner(p)!=m ||
       audio_site_owner((const void *)(a+n-1))!=m)return 0;
    return ReadProcessMemory(GetCurrentProcess(),p,out,n,&got) && got==n;
}
static int audio_postload_site_check(HMODULE *out,const void **site,const void **caller) {
    HMODULE main=NULL;
    /* No UNCHANGED_REFCOUNT: this diagnostic pins the selected main module. */
    if(!game_fn_table_p || !GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
        GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(const void *)game_fn_table_p,&main) || !main)return 0;
    const void *tab=(const void *)GetProcAddress(main,"sky_site_table");
    const void *num=(const void *)GetProcAddress(main,"sky_site_count");
    int count=0;AudioPostloadSite row={0};
    if(!audio_site_read(main,num,&count,sizeof count) || count!=1 ||
       !audio_site_read(main,tab,&row,sizeof row) || row.addr!=AUDIO_POSTLOAD_PC ||
       row.kind!=2 || row.word!=0)return 0;
    const char *exports[]={"game_bind","game_data_bind","game_eh_bind"};
    for(unsigned i=0;i<sizeof exports/sizeof exports[0];i++)
        if(audio_site_owner((const void *)GetProcAddress(main,exports[i]))!=main)return 0;
    if(!audio_site_read(main,game_fn_table_count_p,&count,sizeof count) || count<1 || count>1000000)return 0;
    unsigned found=0;const void *fn=NULL;
    for(int i=0;i<count;) {
        FnEntry rows[64];int n=count-i<64?count-i:64;
        if(!audio_site_read(main,&(*game_fn_table_p)[i],rows,(size_t)n*sizeof rows[0]))return 0;
        for(int j=0;j<n;j++)if(rows[j].addr==0x7103987e40ULL) {found++;fn=(const void *)rows[j].fn;}
        i+=n;
    }
    if(found!=1 || audio_site_owner(fn)!=main)return 0;
    *out=main;*site=tab;*caller=fn;return 1;
}
void game_require_audio_postload_site(void) {
    DWORD error=GetLastError();HMODULE main=NULL;const void *site=NULL,*caller=NULL;
    if(!audio_postload_site_check(&main,&site,&caller)) {
        fprintf(stderr,"audio postload requires one exact inline site in the bound main DLL; rebuild the diagnostic game DLL\n");
        exit(9);
    }
    /* Cache only; the safe AP drain emits SITE into the same r1.log as the
     * companion seal. No stdout/file dependency at an observation site. */
    g_game_audio_postload_identity=(AudioPostloadIdentity){(uintptr_t)main,(uintptr_t)site,(uintptr_t)caller,
        (uintptr_t)audio_site_owner(site),(uintptr_t)audio_site_owner(caller)};
    SetLastError(error);
}
#else
void game_require_audio_postload_site(void) {
    fprintf(stderr,"audio postload diagnostic requires the admitted Windows fixture\n");exit(9);
}
#endif
