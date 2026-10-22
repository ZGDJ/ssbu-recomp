/* Exact module helpers; scripted Toolhelp/export boundaries and actual target
 * variables. This proves neither loader quiescence nor module pinning. */
#include <windows.h>
#include <tlhelp32.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define LOG(...) fprintf(stderr,__VA_ARGS__)
#define WN2 (8ull<<30)
static uint8_t *g_win1=(uint8_t *)(uintptr_t)0x100000;
static size_t g_wn1=0x400000;
typedef struct {uint8_t *m1,*m2;uint64_t lo1,n1,n2;} Target;
static Target targets[1026],original[1026];
static int masks[1026],module_count,cursor,snapshot_failure,first_failure,next_failure,close_failure,close_calls,export_calls;
static DWORD last_error;
static HANDLE fake_snapshot(DWORD flags,DWORD pid){(void)pid;assert(flags==TH32CS_SNAPMODULE);return snapshot_failure?INVALID_HANDLE_VALUE:(HANDLE)1;}
static BOOL emit_module(MODULEENTRY32 *m){m->hModule=(HMODULE)(uintptr_t)(cursor+1);snprintf(m->szModule,sizeof m->szModule,"module%d",cursor);return TRUE;}
static BOOL fake_first(HANDLE h,MODULEENTRY32 *m){assert(h==(HANDLE)1);cursor=0;if(first_failure){last_error=ERROR_ACCESS_DENIED;return FALSE;}if(!module_count){last_error=ERROR_NO_MORE_FILES;return FALSE;}return emit_module(m);}
static BOOL fake_next(HANDLE h,MODULEENTRY32 *m){assert(h==(HANDLE)1);cursor++;if(cursor==next_failure){last_error=ERROR_BAD_LENGTH;return FALSE;}if(cursor>=module_count){last_error=ERROR_NO_MORE_FILES;return FALSE;}return emit_module(m);}
static FARPROC fake_export(HMODULE h,LPCSTR name){
    int i=(int)(uintptr_t)h-1,k=-1;assert(i>=0&&i<module_count);export_calls++;
    if(!strcmp(name,"r1_m1"))k=0;else if(!strcmp(name,"r1_m2"))k=1;else if(!strcmp(name,"r1_lo1"))k=2;else if(!strcmp(name,"r1_n1"))k=3;else if(!strcmp(name,"r1_n2"))k=4;
    assert(k>=0);if(!(masks[i]&(1<<k)))return NULL;
    void *p=k==0?(void *)&targets[i].m1:k==1?(void *)&targets[i].m2:k==2?(void *)&targets[i].lo1:k==3?(void *)&targets[i].n1:(void *)&targets[i].n2;
    return (FARPROC)p;
}
static BOOL fake_close(HANDLE h){assert(h==(HANDLE)1);close_calls++;last_error=ERROR_ACCESS_DENIED;return !close_failure;}
#define CreateToolhelp32Snapshot fake_snapshot
#define Module32First fake_first
#define Module32Next fake_next
#define GetProcAddress fake_export
#define CloseHandle fake_close
#define GetLastError() last_error
typedef struct {uint8_t **m1,**m2;uint64_t *lo1,*n1,*n2;char name[MAX_MODULE_NAME32+1];} MarkModule;
static MarkModule g_mark_modules[1024];
static int g_mark_module_count,g_mark_modules_prepared;
/* MODULE_SOURCE */
static void reset(int n){
    module_count=n;cursor=0;snapshot_failure=first_failure=close_failure=close_calls=export_calls=0;next_failure=-1;
    memset(targets,0x5a,sizeof targets);memcpy(original,targets,sizeof targets);for(int i=0;i<1026;i++)masks[i]=31;
}
static void unchanged(void){assert(!memcmp(targets,original,sizeof targets));}
static void refused(void){assert(!mark_modules_prepare());unchanged();assert(!g_mark_module_count&&!g_mark_modules_prepared);assert(close_calls==!snapshot_failure);}
int main(int argc,char **argv){
    if(argc>1){reset(1);if(!strcmp(argv[1],"close")){close_failure=1;(void)mark_modules_prepare();}else mark_modules_publish(NULL,NULL,0);puts("UNEXPECTED_SUCCESS");return 0;}
    reset(0);assert(mark_modules_prepare()&&close_calls==1&&!g_mark_module_count);unchanged();
    reset(2);snapshot_failure=1;refused();reset(2);first_failure=1;refused();
    for(int i=1;i<=3;i++){reset(3);next_failure=i;refused();}
    for(int mask=1;mask<31;mask++){reset(3);masks[1]=mask;refused();}
    reset(1025);refused();
    reset(1024);assert(mark_modules_prepare()&&g_mark_module_count==1024);unchanged();
    reset(3);masks[1]=0;assert(mark_modules_prepare()&&g_mark_module_count==2);unchanged();
    uint8_t *m1=(uint8_t *)0x1111,*m2=(uint8_t *)0x2222;
    int calls=export_calls;assert(mark_modules_publish(m1,m2,0)==2);assert(calls==export_calls&&!g_mark_modules_prepared);
    for(int i=0;i<3;i++)if(i!=1)assert(targets[i].m1==m1&&targets[i].m2==m2&&targets[i].lo1==(uintptr_t)g_win1&&targets[i].n1==g_wn1&&targets[i].n2==WN2);
    assert(!memcmp(&targets[1],&original[1],sizeof(Target)));
    for(int field=0;field<5;field++){
        if(field==0)targets[0].m1=NULL;if(field==1)targets[0].m2=NULL;if(field==2)targets[0].lo1=0;if(field==3)targets[0].n1=0;if(field==4)targets[0].n2=0;
        assert(mark_modules_prepare());assert(mark_modules_publish(m1,m2,1)==1);assert(!g_mark_modules_prepared);
        assert(targets[0].m1==m1&&targets[0].m2==m2&&targets[0].lo1==(uintptr_t)g_win1&&targets[0].n1==g_wn1&&targets[0].n2==WN2);
    }
    assert(mark_modules_prepare());assert(mark_modules_publish(m1,m2,1)==0);
    /* A later failed preparation must invalidate the previous target list. */
    reset(1);assert(mark_modules_prepare());first_failure=1;close_calls=0;refused();
    puts("mark_modules_source_test: PASS");return 0;
}
