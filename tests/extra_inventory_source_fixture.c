/* Production descriptor helper only: no game-memory enumeration or copying. */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
/* EXTRA_DECLARATIONS */
/* EXTRA_SOURCE */
static Extra entries[8192], before[8192];
static uint8_t *address(int i) { return (uint8_t *)(uintptr_t)(0x100000ull+(uint64_t)i*2*PG); }
static void fresh(void) { memset(entries,0xa5,sizeof entries); }
static void refused(int count,uint8_t *a) {
    memcpy(before,entries,sizeof entries);int original=count;
    assert(!extra_append(entries,&count,a));assert(count==original);
    assert(!memcmp(entries,before,sizeof entries));
}
static void boundaries(void) {
    fresh();int count=0;
    for(int i=0;i<8192;i++) {
        assert(extra_append(entries,&count,address(i)));assert(count==i+1);
        assert(entries[i].a==address(i)&&entries[i].n==PG&&!entries[i].b);
        if(i==8190) assert(count==8191);
    }
    refused(count,address(8192));
    /* Capacity cannot prevent extending the final contiguous descriptor. */
    entries[8191].b=(uint8_t *)(uintptr_t)0x1234;
    memcpy(before,entries,sizeof entries);
    assert(extra_append(entries,&count,address(8191)+PG));assert(count==8192);
    assert(entries[8191].a==before[8191].a&&entries[8191].n==2*PG&&entries[8191].b==before[8191].b);
    assert(!memcmp(entries,before,8191*sizeof entries[0]));
    refused(count,address(8192)+PG);
}
static void invalid(void) {
    fresh();entries[0]=(Extra){(uint8_t *)(uintptr_t)(UINTPTR_MAX-PG),2*PG,NULL};refused(1,address(0));
    fresh();refused(-1,address(0));refused(8193,address(0));
    refused(0,(uint8_t *)(uintptr_t)UINTPTR_MAX);
    refused(0,(uint8_t *)(uintptr_t)(UINTPTR_MAX-PG+1));
    int count=0;
    assert(extra_append(entries,&count,(uint8_t *)(uintptr_t)(UINTPTR_MAX-PG)));
    assert(count==1&&entries[0].n==PG);
    refused(count,(uint8_t *)(uintptr_t)UINTPTR_MAX);
}
static void merge_and_reuse(void) {
    fresh();int count=0;
    assert(extra_append(entries,&count,address(0)));entries[0].b=(uint8_t *)(uintptr_t)0x4567;
    assert(extra_append(entries,&count,address(0)+PG));assert(count==1&&entries[0].n==2*PG);
    assert(entries[0].b==(uint8_t *)(uintptr_t)0x4567);
    assert(extra_append(entries,&count,address(2)));assert(count==2&&entries[1].n==PG&&!entries[1].b);
    /* Count controls reuse; stale detached buffer ownership is cleared on append. */
    count=0;assert(extra_append(entries,&count,address(3)));
    assert(count==1&&entries[0].a==address(3)&&entries[0].n==PG&&!entries[0].b);
}
int main(void) {boundaries();invalid();merge_and_reuse();puts("extra_inventory_source_test: PASS");return 0;}
