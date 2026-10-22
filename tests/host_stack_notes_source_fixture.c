/* Exact note/validity helpers. Exclusion is an observed boundary, not a real
 * page-map implementation. Caller integration is checked structurally only. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define LOG(...) ((void)0)
static uint64_t g_hs_note[16][2];
static int g_hs_nnote,g_hs_on=-1;
static volatile LONG g_hs_note_failed,g_bf_failed;
static uint8_t *g_ns2;
static int exclusions;
static uint64_t last_lo,last_hi;
static void hs_exclude(uint64_t lo,uint64_t hi,const char *why){
    (void)why;exclusions++;last_lo=lo;last_hi=hi;
}
/* NOTE_SOURCE */
static void reset(void){
    memset(g_hs_note,0,sizeof g_hs_note);g_hs_nnote=0;
    g_hs_note_failed=g_bf_failed=0;g_ns2=NULL;g_hs_on=-1;exclusions=0;
}
static void fill(void){for(int i=0;i<16;i++)r1_host_stack_note(0x1000+(uint64_t)i*0x1000,0x1800+(uint64_t)i*0x1000);}
int main(void){
    reset();assert(host_inventory_valid());fill();
    assert(g_hs_nnote==16&&host_inventory_valid()&&!exclusions);
    /* Duplicates must update even when full, without consuming an entry. */
    r1_host_stack_note(0x1000,0x1c00);
    assert(g_hs_nnote==16&&g_hs_note[0][1]==0x1c00&&host_inventory_valid());
    uint64_t before[16][2];memcpy(before,g_hs_note,sizeof before);
    g_ns2=(uint8_t *)1;g_hs_on=1;r1_host_stack_note(0x20000,0x21000);
    assert(g_hs_nnote==16&&!memcmp(before,g_hs_note,sizeof before));
    assert(g_hs_note_failed&&!host_inventory_valid()&&exclusions==1&&last_lo==0x20000&&last_hi==0x21000);
    r1_host_stack_note(0x1000,0x1e00);
    assert(g_hs_note[0][1]==0x1e00&&!host_inventory_valid()&&exclusions==2);
    /* Recreating exclusion maps cannot recover a dropped historical note. */
    g_ns2=NULL;assert(!host_inventory_valid());g_ns2=(uint8_t *)1;assert(!host_inventory_valid());
    for(int fault=0;fault<3;fault++){
        reset();g_ns2=(uint8_t *)1;g_hs_on=1;
        uint64_t lo=0x1000,hi=fault==0?lo:fault==1?lo-1:lo+(1ull<<32)+1;
        r1_host_stack_note(lo,hi);
        assert(g_hs_note_failed&&!host_inventory_valid()&&g_hs_nnote==0);
        assert(exclusions==1&&last_lo==lo&&last_hi==hi);
        r1_host_stack_note(0x2000,0x3000);assert(!host_inventory_valid());
    }
    reset();g_ns2=(uint8_t *)1;g_hs_on=0;r1_host_stack_note(0x1000,0x2000);
    assert(!exclusions&&g_hs_nnote==1&&host_inventory_valid());
    g_hs_on=-1;r1_host_stack_note(0x2000,0x3000);assert(exclusions==1);
    reset();r1_host_stack_note(0x1000,0x1000+(1ull<<32));
    assert(host_inventory_valid()&&g_hs_nnote==1&&g_hs_note[0][1]==0x1000+(1ull<<32));
    for(int bad=0;bad<2;bad++){
        reset();g_hs_nnote=bad?17:-1;g_ns2=(uint8_t *)1;g_hs_on=1;
        r1_host_stack_note(0x1000,0x2000);
        assert(g_hs_note_failed&&!host_inventory_valid()&&g_hs_nnote==(bad?17:-1));
        assert(exclusions==1&&!g_hs_note[0][0]);
    }
    reset();g_bf_failed=1;assert(!host_inventory_valid()&&!g_hs_note_failed);
    reset();g_hs_note_failed=1;assert(!host_inventory_valid()&&!g_bf_failed);
    puts("host_stack_notes_source_test: PASS");return 0;
}
