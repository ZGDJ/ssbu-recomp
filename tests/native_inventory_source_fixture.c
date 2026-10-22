/* Exact raw inventory and fiber visitors. Objects are synthetic; callbacks
 * compare complete tuples/order against the exact direct traversal. */
#include <windows.h>
#include <stdint.h>
#include <limits.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
typedef struct {uint64_t x[32];} Ctx;
/* OBJ_DECLARATION */
/* CACHE_DECLARATIONS */
static Obj *g_table[BUCKETS];
static struct {Obj *o;Ctx *c;} g_threads[256];static volatile LONG g_threads_n;
static Obj objects[610];static Ctx contexts[610];
typedef struct {uint64_t key;Ctx *c;uint64_t stack,size;void *fiber;} Seen;
static Seen expected[610],seen[610];static int expected_count,seen_count;
static int realloc_calls,fail_realloc,change_generation,changed;
static void *failed_pointer;static int failed_capacity,allocated_capacity;
static void *fixture_realloc(void *p,size_t n){
    assert(!seen_count); /* No partial cached callbacks before fallible growth. */
    if(++realloc_calls==fail_realloc){failed_pointer=p;failed_capacity=allocated_capacity;return NULL;}
    void *next=realloc(p,n);assert(next);allocated_capacity=(int)(n/sizeof(Obj *));
    if(change_generation&&!changed){changed=1;InterlockedIncrement(&g_fib_gen);}
    return next;
}
#define realloc fixture_realloc
/* INVENTORY_SOURCE */
#undef realloc
static void expected_cb(uint64_t key,Ctx *c,uint64_t stack,uint64_t size,void *fiber){
    assert(expected_count<610);expected[expected_count++]=(Seen){key,c,stack,size,fiber};
}
static void seen_cb(uint64_t key,Ctx *c,uint64_t stack,uint64_t size,void *fiber){
    assert(seen_count<610);seen[seen_count++]=(Seen){key,c,stack,size,fiber};
}
static void compare(void){
    assert(seen_count==expected_count);
    for(int i=0;i<seen_count;i++){Seen *a=&seen[i],*b=&expected[i];
        assert(a->key==b->key&&a->c==b->c&&a->stack==b->stack&&a->size==b->size&&a->fiber==b->fiber);}
}
static void table(int count){
    memset(g_table,0,sizeof g_table);memset(objects,0,sizeof objects);
    for(int i=0;i<count+3;i++){
        Obj *o=&objects[i];o->key=1000+i;o->fctx=&contexts[i];o->stack=0x100000ull+(uint64_t)i*4096;o->stack_size=4096+i;
        o->fiber=i<count?(void *)(uintptr_t)(0x200000+i*16):NULL;
        int bucket=(i*131)%17;o->next=g_table[bucket];g_table[bucket]=o;
    }
    expected_count=0;os_r1_fibers_direct(expected_cb);assert(expected_count==count);
}
static void reset(void){
    free(g_fib_c);g_fib_c=NULL;g_fib_cn=g_fib_ccap=g_fib_cvalid=0;g_fib_cgen=0;g_fib_gen=1;
    realloc_calls=fail_realloc=change_generation=changed=seen_count=0;failed_pointer=NULL;failed_capacity=-1;allocated_capacity=0;
}
static void visit(void){seen_count=0;os_r1_fibers(seen_cb);compare();}
static void raw_threads(void){
    memset(g_threads,0,sizeof g_threads);g_threads_n=0;assert(os_r1_thread_inventory_count()==0&&os_r1_thread_inventory_valid());
    for(int i=0;i<256;i++){objects[i].thread=(HANDLE)(uintptr_t)(i+1);objects[i].name=(uint64_t)(uintptr_t)"fixture";
        objects[i].finished=0;g_threads[i].o=&objects[i];g_threads[i].c=&contexts[i];}
    g_threads_n=256;assert(os_r1_thread_inventory_count()==256&&os_r1_thread_inventory_valid());
    Ctx *c;const char *name;HANDLE h;
    for(int i=0;i<256;i++){assert(guest_thread_info(i,&c,&name,&h));assert(c==&contexts[i]&&h==(HANDLE)(uintptr_t)(i+1));}
    assert(!guest_thread_info(256,&c,&name,&h)&&!guest_thread_info(-1,&c,&name,&h));
    g_threads_n=257;assert(os_r1_thread_inventory_count()==257&&!os_r1_thread_inventory_valid());g_threads_n=-1;assert(os_r1_thread_inventory_count()==-1&&!os_r1_thread_inventory_valid());g_threads_n=256;
    g_threads[128].o=NULL;assert(os_r1_thread_inventory_count()==256&&!os_r1_thread_inventory_valid());assert(!guest_thread_info(128,&c,&name,&h));g_threads[128].o=&objects[128];
    g_threads[255].c=NULL;assert(!os_r1_thread_inventory_valid());g_threads[255].c=&contexts[255];
    objects[17].finished=1;assert(os_r1_thread_inventory_valid());assert(guest_thread_info(17,&c,&name,&h)&&!h);
}
static void growth_failures(void){
    for(int failure=1;failure<=3;failure++){
        reset();table(600);fail_realloc=failure;visit();
        assert(realloc_calls==failure&&g_fib_c==failed_pointer&&g_fib_ccap==failed_capacity&&!g_fib_cvalid&&g_fib_cgen!=g_fib_gen);
        fail_realloc=0;realloc_calls=0;visit();assert(realloc_calls>0&&g_fib_cgen==g_fib_gen&&g_fib_cn==600);
        realloc_calls=0;visit();assert(!realloc_calls);
    }
    for(int failure=1;failure<=2;failure++){
        reset();table(200);visit();assert(g_fib_cn==200&&g_fib_ccap==256);
        table(600);InterlockedIncrement(&g_fib_gen);realloc_calls=0;fail_realloc=failure;visit();
        assert(realloc_calls==failure&&g_fib_c==failed_pointer&&g_fib_ccap==failed_capacity&&!g_fib_cvalid&&g_fib_cgen!=g_fib_gen);
        fail_realloc=0;realloc_calls=0;visit();assert(g_fib_cn==600&&g_fib_cgen==g_fib_gen);realloc_calls=0;visit();assert(!realloc_calls);
    }
}
static void controls(void){
    reset();table(200);visit();assert(g_fib_cvalid);LONG previous=g_fib_cgen;
    table(600);InterlockedIncrement(&g_fib_gen);realloc_calls=0;fail_realloc=1;visit();
    assert(!g_fib_cvalid&&g_fib_cgen==previous);
    /* Even an aliased generation cannot make the partial cache eligible. */
    g_fib_gen=previous;fail_realloc=0;realloc_calls=0;visit();
    assert(realloc_calls>0&&g_fib_cvalid&&g_fib_cn==600&&g_fib_cgen==g_fib_gen);
    reset();table(0);visit();assert(!realloc_calls&&g_fib_cn==0&&g_fib_cgen==g_fib_gen);
    reset();table(600);change_generation=1;visit();assert(changed&&g_fib_cgen!=g_fib_gen);
    change_generation=0;realloc_calls=0;visit();assert(g_fib_cgen==g_fib_gen&&g_fib_cn==600);assert(!realloc_calls);
    table(10);InterlockedIncrement(&g_fib_gen);visit();assert(g_fib_cn==10&&!realloc_calls);
    /* An object that lost its fiber must not be emitted from a cache hit. */
    objects[3].fiber=NULL;expected_count=0;os_r1_fibers_direct(expected_cb);visit();assert(expected_count==9);
    reset();
}
int main(void){raw_threads();growth_failures();controls();puts("native_inventory_source_test: PASS");return 0;}
