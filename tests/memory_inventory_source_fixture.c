/* Exact memory walks with bounded scripted VirtualQuery records. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define PG 4096u
#define LOG(...) fprintf(stderr,__VA_ARGS__)
static int g_collect_failed,g_heap_inventory_failed,g_nheap;static uint8_t *g_heap_base[8];
typedef struct {uintptr_t a,end,allocation;DWORD state,protect;} Region;
static Region regions[32];static int nr,queries,fail_query,short_query,bad_geometry,added;static uintptr_t first,limit,range_lo[32];static size_t range_n[32];
static void fake_system(SYSTEM_INFO *s){memset(s,0,sizeof *s);s->lpMinimumApplicationAddress=(void*)first;s->lpMaximumApplicationAddress=(void*)(limit-1);}
static SIZE_T fake_query(LPCVOID ptr,PMEMORY_BASIC_INFORMATION m,SIZE_T bytes){
 assert(bytes==sizeof *m);assert(++queries<100);if(queries==fail_query)return 0;
 uintptr_t p=(uintptr_t)ptr;int i;for(i=0;i<nr;i++)if(p>=regions[i].a&&p<regions[i].end)break;assert(i<nr);
 Region *r=&regions[i];memset(m,0,sizeof *m);m->BaseAddress=(void*)r->a;m->AllocationBase=(void*)r->allocation;m->RegionSize=r->end-r->a;m->State=r->state;m->Protect=r->protect;
 if(bad_geometry==1)m->RegionSize=0;if(bad_geometry==2)m->BaseAddress=(void*)(p+1);if(bad_geometry==3){m->BaseAddress=(void*)(UINTPTR_MAX-1);m->RegionSize=4;}if(bad_geometry==4){m->BaseAddress=(void*)(p-2);m->RegionSize=1;}
 return queries==short_query?sizeof *m-1:sizeof *m;
}
static void add_range(uint8_t *p,size_t n){assert(added<32);range_lo[added]=(uintptr_t)p;range_n[added++]=n;}
#define GetSystemInfo fake_system
#define VirtualQuery fake_query
/* SOURCE */
static void reset(void){nr=queries=fail_query=short_query=bad_geometry=added=g_collect_failed=g_heap_inventory_failed=g_nheap=0;first=0x10000;limit=first+4*PG;memset(g_heap_base,0,sizeof g_heap_base);}
static void region(uintptr_t a,uintptr_t end,uintptr_t allocation,DWORD state,DWORD protect){assert(nr<32);regions[nr++]=(Region){a,end,allocation,state,protect};}
static void ordinary(void){reset();region(first,first+2*PG,first,MEM_COMMIT,PAGE_READWRITE);region(first+2*PG,limit,0,MEM_FREE,PAGE_NOACCESS);uintptr_t a,e;assert(inventory_alloc_span((void*)(first+7),&a,&e)&&a==first&&e==first+2*PG);add_alloc(NULL);assert(!added&&!g_collect_failed);add_alloc((void*)(first+7));assert(added==1&&range_lo[0]==first&&range_n[0]==2*PG);reset();region(first,limit,first,MEM_COMMIT,PAGE_READWRITE);assert(inventory_alloc_span((void*)first,&a,&e)&&e==limit);add_span((uint8_t*)(first+5),(uint8_t*)(limit-7));assert(added==1&&range_lo[0]==first+5&&range_n[0]==limit-first-12);}
static void failures(void){for(int k=0;k<6;k++){reset();region(first,limit,first,MEM_COMMIT,PAGE_READWRITE);if(k==0)fail_query=1;else if(k==1)short_query=1;else bad_geometry=k-1;add_span((void*)first,(void*)limit);assert(g_collect_failed&&!added);}reset();region(first,first+PG,first,MEM_COMMIT,PAGE_READWRITE);region(first+PG,limit,first,MEM_COMMIT,PAGE_READWRITE);fail_query=2;add_span((void*)first,(void*)limit);assert(g_collect_failed&&added==1);reset();region(first,limit,0,MEM_FREE,PAGE_NOACCESS);add_alloc((void*)first);assert(g_collect_failed&&!added);reset();add_span((void*)first,(void*)first);assert(!queries&&!g_collect_failed);add_span((void*)(first+1),(void*)first);assert(g_collect_failed&&!queries);}
static void heaps(void){for(int n=8;n<=9;n++){reset();uintptr_t step=16ull<<30;limit=first+n*step;for(int i=0;i<n;i++)region(first+i*step,first+(i+1)*step,first+i*step,MEM_RESERVE,PAGE_NOACCESS);find_heaps();assert(g_nheap==8&&g_heap_inventory_failed==(n==9));}for(int f=1;f<=2;f++){reset();uintptr_t step=16ull<<30;limit=first+2*step;region(first,first+step,first,MEM_RESERVE,PAGE_NOACCESS);region(first+step,limit,first,MEM_RESERVE,PAGE_NOACCESS);fail_query=f;find_heaps();assert(g_heap_inventory_failed&&!g_nheap);}}
static void more(void){
 DWORD protections[]={PAGE_READWRITE,PAGE_EXECUTE_READWRITE,PAGE_WRITECOPY,PAGE_EXECUTE_WRITECOPY,PAGE_READONLY,PAGE_READWRITE|PAGE_GUARD};
 for(int i=0;i<6;i++){reset();region(first,limit,first,MEM_COMMIT,protections[i]);add_span((void*)first,(void*)limit);assert(!g_collect_failed&&added==(i<2));}
 reset();region(first,limit,first,MEM_RESERVE,PAGE_READWRITE);add_span((void*)first,(void*)limit);assert(!added&&!g_collect_failed);
 uintptr_t a,e;for(int i=0;i<2;i++){reset();limit=i?first-1:0;assert(!inventory_bounds(&a,&e));find_heaps();assert(g_heap_inventory_failed&&!queries);limit=first+PG;region(first,limit,first,MEM_RESERVE,PAGE_NOACCESS);find_heaps();assert(g_heap_inventory_failed&&!queries);}
 for(int f=1;f<=3;f++){reset();region(first,first+PG,first,MEM_COMMIT,PAGE_READWRITE);region(first+PG,limit,first,MEM_COMMIT,PAGE_READWRITE);fail_query=f;add_alloc((void*)first);assert(g_collect_failed&&!added);}
 reset();region(first,limit+PG,first,MEM_RESERVE,PAGE_NOACCESS);assert(!inventory_alloc_span((void*)first,&a,&e));queries=0;find_heaps();assert(g_heap_inventory_failed&&!g_nheap);
 reset();region(first,limit,first+PG,MEM_RESERVE,PAGE_NOACCESS);assert(!inventory_alloc_span((void*)first,&a,&e));queries=0;find_heaps();assert(g_heap_inventory_failed);
 reset();region(first,limit,first,MEM_COMMIT,PAGE_READWRITE);add_alloc((void*)(first-1));assert(g_collect_failed&&!queries);add_alloc((void*)first);assert(g_collect_failed&&added==1);
}
int main(void){ordinary();failures();heaps();more();puts("memory_inventory_source_test: PASS");return 0;}
