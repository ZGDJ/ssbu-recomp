/* Exact host-thread walk with scripted OS and guarded-read boundaries. */
#include <windows.h>
#include <tlhelp32.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define LOG(...) fprintf(stderr,__VA_ARGS__)
typedef struct {LONG st;void *teb;void *pid,*tid;ULONG_PTR mask;LONG pri,bpri;} HsTbi;
static volatile LONG g_hs_thread_failed;
static int missing_module,short_record,missing_api,snapshot_failure,first_failure,next_failure,open_failure,query_failure,read_failure,bad_teb,bad_span;
static int nthreads=3,cursor,reads,opens,queries,closes,close_failure,excluded;
static int closed[5];static DWORD last_error;
static uint8_t tebs[3][0x1500];static uint64_t excluded_lo[3],excluded_hi[3];
static HANDLE snapshot(DWORD flags,DWORD pid){assert(flags==TH32CS_SNAPTHREAD&&pid==0);return snapshot_failure?INVALID_HANDLE_VALUE:(HANDLE)99;}
static BOOL emit(THREADENTRY32 *te){te->dwSize=short_record==cursor+1?0:sizeof *te;te->th32ThreadID=cursor+1;te->th32OwnerProcessID=cursor==1?88:77;return TRUE;}
static BOOL first(HANDLE h,THREADENTRY32 *te){assert(h==(HANDLE)99);cursor=0;if(first_failure){last_error=ERROR_ACCESS_DENIED;return FALSE;}if(!nthreads){last_error=ERROR_NO_MORE_FILES;return FALSE;}return emit(te);}
static BOOL next(HANDLE h,THREADENTRY32 *te){assert(h==(HANDLE)99);cursor++;if(cursor==next_failure){last_error=ERROR_BAD_LENGTH;return FALSE;}if(cursor>=nthreads){last_error=ERROR_NO_MORE_FILES;return FALSE;}return emit(te);}
static HANDLE open_thread(DWORD access,BOOL inherit,DWORD id){assert(access==THREAD_QUERY_LIMITED_INFORMATION&&!inherit&&id!=2);opens++;return (int)id==open_failure?NULL:(HANDLE)(uintptr_t)id;}
static LONG WINAPI query(HANDLE h,int kind,void *out,ULONG size,ULONG *ret){
    (void)ret;assert(!kind&&size==sizeof(HsTbi));int id=(int)(uintptr_t)h;queries++;
    if(id==query_failure)return -1;HsTbi *tb=out;
    tb->teb=bad_teb==id?NULL:bad_teb==id+10?(void *)(UINTPTR_MAX-4):tebs[id-1];return 0;
}
static HMODULE fake_module(LPCSTR name){assert(!strcmp(name,"ntdll.dll"));return missing_module?NULL:(HMODULE)1;}
static FARPROC proc(HMODULE m,LPCSTR name){assert(m==(HMODULE)1&&!strcmp(name,"NtQueryInformationThread"));return missing_api?NULL:(FARPROC)query;}
static BOOL close_handle(HANDLE h){int id=h==(HANDLE)99?4:(int)(uintptr_t)h;assert(id>=1&&id<=4&&!closed[id]);closed[id]=1;closes++;last_error=ERROR_ACCESS_DENIED;return closes!=close_failure;}
static int fiber_capture_read(void *ctx,const void *p,void *out,size_t n){(void)ctx;assert(n==8);reads++;if(reads==read_failure)return 0;memcpy(out,p,n);return 1;}
static void hs_exclude(uint64_t lo,uint64_t hi,const char *why){assert(why&&excluded<3);excluded_lo[excluded]=lo;excluded_hi[excluded++]=hi;}
#define CreateToolhelp32Snapshot snapshot
#define Thread32First first
#define Thread32Next next
#define GetCurrentProcessId() 77u
#define OpenThread open_thread
#define GetModuleHandleA fake_module
#define GetProcAddress proc
#define CloseHandle close_handle
#define GetLastError() last_error
/* THREAD_SOURCE */
static void reset(void){
    missing_module=short_record=missing_api=snapshot_failure=first_failure=open_failure=query_failure=read_failure=bad_teb=bad_span=0;next_failure=-1;
    nthreads=3;reads=opens=queries=closes=close_failure=excluded=0;g_hs_thread_failed=0;memset(closed,0,sizeof closed);
    for(int i=0;i<3;i++){uint64_t lo=0x10000+(uint64_t)i*0x10000,hi=lo+0x8000;memcpy(tebs[i]+0x1478,&lo,8);memcpy(tebs[i]+8,&hi,8);}
}
static void failed(void){int nth=0;assert(!hs_threads_exclude(&nth)&&g_hs_thread_failed);assert(nth==excluded);assert(opens>=queries);assert(closes==queries+(!missing_module&&!missing_api&&!snapshot_failure));assert(closed[4]||missing_module||missing_api||snapshot_failure);for(int id=1;id<=3;id+=2)if(closed[id])assert(id!=open_failure);}
int main(int argc,char **argv){
    reset();if(argc>1){close_failure=atoi(argv[1]);int n=0;(void)hs_threads_exclude(&n);puts("UNEXPECTED_SUCCESS");return 0;}
    int nth=0;assert(hs_threads_exclude(&nth)&&nth==2&&excluded==2&&!g_hs_thread_failed&&opens==2&&queries==2&&closes==3);
    assert(excluded_lo[0]==0x10000&&excluded_hi[0]==0x18000&&excluded_lo[1]==0x30000&&excluded_hi[1]==0x38000);
    reset();nthreads=0;nth=0;assert(hs_threads_exclude(&nth)&&!nth&&!excluded&&closes==1);
    reset();missing_module=1;failed();assert(!opens&&!closes);
    reset();missing_api=1;failed();assert(!opens&&!closes);
    reset();snapshot_failure=1;failed();assert(!opens&&!closes);
    reset();first_failure=1;failed();assert(closes==1&&!opens);
    for(int at=1;at<=3;at++){reset();next_failure=at;failed();assert(excluded==(at==3?2:1));}
    for(int at=1;at<=3;at++){reset();short_record=at;failed();assert(excluded==(at>1));}
    for(int id=1;id<=3;id+=2){
        reset();open_failure=id;failed();assert(closes==(id==1?1:2));
        reset();query_failure=id;failed();assert(closes==(id==1?2:3));
        reset();bad_teb=id;failed();assert(closes==(id==1?2:3));
        reset();bad_teb=id+10;failed();assert(closes==(id==1?2:3));
    }
    for(int at=1;at<=4;at++){reset();read_failure=at;failed();assert(excluded==(at>2));}
    for(int kind=0;kind<4;kind++){
        reset();uint64_t lo=kind==0?0:0x10000,hi=kind==1?lo:kind==2?lo-1:lo+(1ull<<32)+1;
        memcpy(tebs[0]+0x1478,&lo,8);memcpy(tebs[0]+8,&hi,8);failed();assert(!excluded);
    }
    reset();uint64_t hi=0x10000+(1ull<<32);memcpy(tebs[0]+8,&hi,8);nth=0;assert(hs_threads_exclude(&nth)&&nth==2);
    reset();query_failure=3;failed();query_failure=0;memset(closed,0,sizeof closed);excluded=0;nth=0;
    (void)hs_threads_exclude(&nth);assert(g_hs_thread_failed);
    puts("host_thread_inventory_source_test: PASS");return 0;
}
