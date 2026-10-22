/* Exact fighter inventory and saved-range cleanup; OS and guarded reads scripted. */
#include <windows.h>
#include <tlhelp32.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
#define MAXR 4
#define LOG(...) fprintf(stderr,__VA_ARGS__)
static int g_collect_failed,g_cycle=1,g_phase;
static unsigned char image[3][16384];static int modules,cursor,closed,snapshot_fail,first_fail,next_fail,close_fail,disabled,read_calls,read_fail,spans,span_fail;
static int short_record,bad_path,skip_module;static DWORD last_error;static uintptr_t starts[8];static size_t lengths[8];
static HANDLE snap(DWORD f,DWORD p){(void)p;assert(f==TH32CS_SNAPMODULE);return snapshot_fail?INVALID_HANDLE_VALUE:(HANDLE)1;}
static BOOL emit(MODULEENTRY32 *m){m->modBaseAddr=image[cursor];m->modBaseSize=sizeof image[0];m->dwSize=short_record==cursor+1?0:sizeof *m;strcpy(m->szExePath,skip_module==cursor+1?"other/test.dll":"fighters_bin/test.dll");if(bad_path==cursor+1)memset(m->szExePath,65,sizeof m->szExePath);return 1;}
static BOOL first(HANDLE h,MODULEENTRY32 *m){assert(h==(HANDLE)1);cursor=0;if(first_fail){last_error=ERROR_ACCESS_DENIED;return 0;}if(!modules){last_error=ERROR_NO_MORE_FILES;return 0;}return emit(m);}
static BOOL next(HANDLE h,MODULEENTRY32 *m){assert(h==(HANDLE)1);if(++cursor==next_fail){last_error=ERROR_ACCESS_DENIED;return 0;}if(cursor>=modules){last_error=ERROR_NO_MORE_FILES;return 0;}return emit(m);}
static BOOL close_handle(HANDLE h){assert(h==(HANDLE)1);closed++;last_error=ERROR_ACCESS_DENIED;return !close_fail;}
static char *env(const char *s){assert(!strcmp(s,"SSBU_R1_NO_DLLS"));return disabled?"1":NULL;}
static int fiber_capture_read(void *ctx,const void *p,void *d,size_t n){(void)ctx;if(++read_calls==read_fail)return 0;uintptr_t a=(uintptr_t)p,b=(uintptr_t)image;assert(a>=b&&a<=b+sizeof image&&n<=b+sizeof image-a);memcpy(d,p,n);return 1;}
static void add_span(uint8_t *a,uint8_t *b){assert(spans<8);starts[spans]=(uintptr_t)a;lengths[spans++]=(size_t)(b-a);if(spans==span_fail)g_collect_failed=1;}
#define CreateToolhelp32Snapshot snap
#define Module32First first
#define Module32Next next
#define CloseHandle close_handle
#define GetLastError() last_error
#define getenv env
/* FIGHTER_SOURCE */
#undef getenv
static int releases,release_fail,crt_frees;
typedef struct {void *s,*dirty,*async;} Rng;static Rng g_r[MAXR];static int g_nr;
static BOOL vfree(void *p,size_t n,DWORD kind){assert(p&&n==0&&kind==MEM_RELEASE);return ++releases!=release_fail;}
static void cfree(void *p){if(p)crt_frees++;}
#define VirtualFree vfree
#define free cfree
/* RELEASE_SOURCE */
#undef free
static IMAGE_NT_HEADERS64 *nt(int i){return (IMAGE_NT_HEADERS64*)(image[i]+128);}
static IMAGE_SECTION_HEADER *section(int i){return IMAGE_FIRST_SECTION(nt(i));}
static void reset(void){memset(image,0,sizeof image);for(int i=0;i<3;i++){IMAGE_DOS_HEADER *d=(void*)image[i];d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=128;nt(i)->Signature=IMAGE_NT_SIGNATURE;nt(i)->FileHeader.SizeOfOptionalHeader=sizeof(IMAGE_OPTIONAL_HEADER64);nt(i)->FileHeader.NumberOfSections=1;nt(i)->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR64_MAGIC;section(i)->VirtualAddress=4096;section(i)->Misc.VirtualSize=3;section(i)->Characteristics=IMAGE_SCN_MEM_WRITE;}modules=2;cursor=closed=snapshot_fail=first_fail=close_fail=disabled=read_calls=read_fail=spans=span_fail=g_collect_failed=0;next_fail=-1;short_record=bad_path=skip_module=0;}
static void normal(void){reset();add_fighter_dlls();assert(!g_collect_failed&&closed==1&&spans==2&&lengths[0]==PG&&starts[1]==(uintptr_t)image[1]+PG);reset();disabled=1;snapshot_fail=1;add_fighter_dlls();assert(!g_collect_failed&&!closed&&!spans);reset();modules=0;add_fighter_dlls();assert(!g_collect_failed&&closed==1&&!spans);reset();section(0)->Misc.VirtualSize=0;section(1)->Characteristics=0;add_fighter_dlls();assert(!g_collect_failed&&!spans);}
static void errors(void){for(int k=0;k<4;k++){reset();if(k==0)snapshot_fail=1;if(k==1)first_fail=1;if(k==2)next_fail=1;if(k==3)span_fail=1;add_fighter_dlls();assert(g_collect_failed&&closed==(k!=0));}for(int k=0;k<7;k++){reset();if(k==0)((IMAGE_DOS_HEADER*)image[0])->e_magic=0;if(k==1)((IMAGE_DOS_HEADER*)image[0])->e_lfanew=-1;if(k==2)nt(0)->Signature=0;if(k==3)nt(0)->FileHeader.SizeOfOptionalHeader=1;if(k==4)nt(0)->OptionalHeader.Magic=0;if(k==5)nt(0)->FileHeader.NumberOfSections=UINT16_MAX;if(k==6)section(0)->VirtualAddress=sizeof image[0];assert(!fighter_sections(image[0],sizeof image[0]));}reset();assert(!fighter_sections(image[0],1));reset();assert(!fighter_sections((void*)(UINTPTR_MAX-1),8));reset();assert(fighter_sections(image[0],sizeof image[0]));int count=read_calls;for(int i=1;i<=count;i++){reset();read_fail=i;assert(!fighter_sections(image[0],sizeof image[0]));}}
static void extended(void){
 for(int at=1;at<=2;at++)for(int kind=0;kind<2;kind++){reset();if(kind)bad_path=at;else short_record=at;add_fighter_dlls();assert(g_collect_failed&&closed==1&&spans==at-1);}
 reset();skip_module=1;((IMAGE_DOS_HEADER*)image[0])->e_magic=0;add_fighter_dlls();assert(!g_collect_failed&&spans==1);
 for(int kind=0;kind<4;kind++){reset();if(kind==0)section(0)->Misc.VirtualSize=UINT32_MAX;if(kind==1){section(0)->VirtualAddress=sizeof image[0]-1;section(0)->Misc.VirtualSize=1;}if(kind==2)((IMAGE_DOS_HEADER*)image[0])->e_lfanew=sizeof image[0]-1;if(kind==3)nt(0)->FileHeader.SizeOfOptionalHeader=UINT16_MAX;assert(!fighter_sections(image[0],sizeof image[0])&&!spans);}
 reset();nt(0)->FileHeader.NumberOfSections=2;section(0)[1]=section(0)[0];section(0)[1].VirtualAddress=sizeof image[0];unsigned char before[sizeof image];memcpy(before,image,sizeof image);add_fighter_dlls();assert(g_collect_failed&&closed==1&&spans==1&&!memcmp(before,image,sizeof image));
 reset();next_fail=2;add_fighter_dlls();assert(g_collect_failed&&closed==1&&spans==2);
}
static void cleanup(void){memset(g_r,0,sizeof g_r);g_nr=3;g_r[0]=(Rng){(void*)1,(void*)2,(void*)3};g_r[2]=(Rng){(void*)4,NULL,(void*)5};release();assert(releases==2&&crt_frees==3);for(int i=0;i<g_nr;i++)assert(!g_r[i].s&&!g_r[i].dirty&&!g_r[i].async);release();assert(releases==2&&crt_frees==3);}
int main(int argc,char **argv){reset();if(argc>1){if(!strcmp(argv[1],"close")){close_fail=1;add_fighter_dlls();}else if(!strcmp(argv[1],"count")){g_nr=MAXR+1;release();}else{release_fail=atoi(argv[1]);cleanup();}puts("UNEXPECTED_SUCCESS");return 0;}normal();errors();extended();cleanup();puts("fighter_inventory_source_test: PASS");return 0;}
