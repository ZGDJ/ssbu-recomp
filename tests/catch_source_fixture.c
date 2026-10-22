/* Exact production catch helpers; only current-stack identity is substituted. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#include <windows.h>
typedef struct { uint64_t cfa; jmp_buf *jb; } CatchSlot;
#define CATCH_SLOTS 8192
static CatchSlot g_catch[CATCH_SLOTS], before[CATCH_SLOTS], staged[CATCH_SLOTS], stage_before[CATCH_SLOTS];
typedef struct { uint64_t cfa, jb; } IntegerSlot;
static IntegerSlot integer_stage[CATCH_SLOTS];
static unsigned char unaligned_stage[sizeof g_catch + 1];
static SRWLOCK g_catch_lock = SRWLOCK_INIT;
static int g_cfix=1,g_cprobes;
static volatile LONG g_c_crowded,g_c_full,g_c_maxprobe;
static union { uint64_t align; unsigned char bytes[0x1480]; } fake_teb;
#undef NtCurrentTeb
#define NtCurrentTeb() ((NT_TIB *)fake_teb.bytes)
/* CATCH_SOURCE */
static void reset(void) {
    memset(g_catch,0,sizeof g_catch); g_cfix=1; g_cprobes=0;
    g_c_crowded=g_c_full=g_c_maxprobe=0;
    ((NT_TIB *)fake_teb.bytes)->StackBase=(void *)(uintptr_t)0x2000;
    *(uint64_t *)(fake_teb.bytes+0x1478)=0x1000;
}
static void fill(void) {
    for(unsigned i=0;i<CATCH_SLOTS;i++) { g_catch[i].cfa=0x10000000+i*16; g_catch[i].jb=(jmp_buf *)(uintptr_t)(0x4000+i*16); }
}
static void unchanged(void) { assert(!memcmp(before,g_catch,sizeof g_catch)); }
static void detached_tests(void) {
    uint64_t cfa=0x987650, jb=0x1100;
    /* Ring's integer jb representation and unaligned byte storage need no
     * compatible CatchSlot effective type. Optimize with strict aliasing on. */
    reset(); unsigned expected=catch_hash(cfa);
    memset(integer_stage,0,sizeof integer_stage);
    assert(nnunwind_catch_stage_insert(integer_stage,sizeof integer_stage,cfa,jb));
    assert(integer_stage[expected].cfa==cfa&&integer_stage[expected].jb==jb);
    assert(nnunwind_catch_stage_free(integer_stage,sizeof integer_stage,expected));
    assert(integer_stage[expected].cfa==0&&integer_stage[expected].jb==0);
    memset(unaligned_stage,0,sizeof unaligned_stage);
    assert(nnunwind_catch_stage_insert(unaligned_stage+1,sizeof g_catch,cfa,jb));
    IntegerSlot value; memcpy(&value,unaligned_stage+1+expected*sizeof value,sizeof value);
    assert(value.cfa==cfa&&value.jb==jb);
    assert(nnunwind_catch_stage_free(unaligned_stage+1,sizeof g_catch,expected));
    memcpy(&value,unaligned_stage+1+expected*sizeof value,sizeof value);
    assert(value.cfa==0&&value.jb==0);
    /* Successful staged selection is byte-identical to legacy insertion, while
     * neither live bytes nor diagnostic counters change during staging. */
    for(int mode=0;mode<4;mode++) {
        reset(); g_cfix=mode!=1; g_cprobes=mode==2?2:mode==3?0x7fffffff:0;
        for(unsigned n=0;n<64;n++) {
            uint64_t key=cfa+n*0x10000, pointer=jb+n*16;
            memcpy(staged,g_catch,sizeof staged); memcpy(before,g_catch,sizeof before);
            LONG crowded=g_c_crowded,full=g_c_full,maxprobe=g_c_maxprobe;
            assert(nnunwind_catch_stage_insert(staged,sizeof staged,key,pointer)); unchanged();
            assert(crowded==g_c_crowded&&full==g_c_full&&maxprobe==g_c_maxprobe);
            nnunwind_catch_reinsert(key,pointer); assert(!memcmp(staged,g_catch,sizeof staged));
        }
        /* Duplicate and same-CFA/different-stack policy remains identical. */
        for(unsigned n=0;n<2;n++) {
            memcpy(staged,g_catch,sizeof staged); memcpy(before,g_catch,sizeof before);
            assert(nnunwind_catch_stage_insert(staged,sizeof staged,cfa,jb+n*0x10000)); unchanged();
            nnunwind_catch_reinsert(cfa,jb+n*0x10000); assert(!memcmp(staged,g_catch,sizeof staged));
        }
    }
    for(int legacy=0;legacy<2;legacy++) {
        reset(); g_cfix=!legacy;
        /* Tombstone collapse wraps backwards across index zero. Legacy keeps tombstones. */
        g_catch[CATCH_SLOTS-1].cfa=1; g_catch[CATCH_SLOTS-2].cfa=1;
        g_catch[0].cfa=cfa; g_catch[0].jb=(jmp_buf *)(uintptr_t)jb;
        memcpy(staged,g_catch,sizeof staged); memcpy(before,g_catch,sizeof before);
        assert(nnunwind_catch_stage_free(staged,sizeof staged,0)); unchanged();
        catch_free_slot(0); assert(!memcmp(staged,g_catch,sizeof staged));
        assert(staged[0].cfa==(legacy?1:0));
        assert(staged[CATCH_SLOTS-1].cfa==(legacy?1:0));
        /* A live successor retains the tombstone. */
        g_catch[1].cfa=cfa; memcpy(staged,g_catch,sizeof staged);
        assert(nnunwind_catch_stage_free(staged,sizeof staged,0)); catch_free_slot(0);
        assert(!memcmp(staged,g_catch,sizeof staged)&&staged[0].cfa==1);
    }
    reset(); fill(); memcpy(staged,g_catch,sizeof staged); memcpy(stage_before,staged,sizeof staged);
    memcpy(before,g_catch,sizeof before);
    assert(!nnunwind_catch_stage_insert(staged,sizeof staged,cfa,jb)); unchanged();
    assert(!memcmp(staged,stage_before,sizeof staged));
    assert(!g_c_crowded&&!g_c_full&&!g_c_maxprobe);
    /* Every invalid argument is refused before any detached or live write. */
    assert(!nnunwind_catch_stage_insert(NULL,sizeof staged,cfa,jb));
    assert(!nnunwind_catch_stage_insert(staged,sizeof staged-1,cfa,jb));
    assert(!nnunwind_catch_stage_insert(staged,sizeof staged+1,cfa,jb));
    assert(!nnunwind_catch_stage_free(NULL,sizeof staged,0));
    assert(!nnunwind_catch_stage_free(staged,sizeof staged-1,0));
    assert(!nnunwind_catch_stage_free(staged,sizeof staged+1,0));
    assert(!nnunwind_catch_stage_free(staged,sizeof staged,CATCH_SLOTS));
    assert(!memcmp(staged,stage_before,sizeof staged)); unchanged();
    assert(!g_c_crowded&&!g_c_full&&!g_c_maxprobe);
    g_cprobes=0x7fffffff; assert(catch_window()==CATCH_SLOTS);
    assert(!nnunwind_catch_stage_insert(staged,sizeof staged,cfa,jb));
    assert(!memcmp(staged,stage_before,sizeof staged)); unchanged();
    /* Exact match wins even after a reusable tombstone in its collision chain. */
    reset(); unsigned h=catch_hash(cfa); g_catch[h].cfa=1;
    g_catch[(h+1)&(CATCH_SLOTS-1)].cfa=cfa;
    g_catch[(h+1)&(CATCH_SLOTS-1)].jb=(jmp_buf *)(uintptr_t)jb;
    memcpy(staged,g_catch,sizeof staged); memcpy(before,g_catch,sizeof before);
    assert(nnunwind_catch_stage_insert(staged,sizeof staged,cfa,jb)); unchanged();
    assert(!memcmp(staged,before,sizeof staged));
}
int main(void) {
    detached_tests();
    reset();
    assert(nnunwind_catch_try_lock()); assert(!nnunwind_catch_try_lock()); nnunwind_catch_unlock();
    assert(nnunwind_catch_try_lock()); nnunwind_catch_unlock();
    uint64_t cfa=0x987650, jb=0x1100; unsigned h=catch_hash(cfa);
    assert(nnunwind_catch_reinsert_checked(cfa,jb));
    assert(g_catch[h].cfa==cfa&&(uintptr_t)g_catch[h].jb==jb);
    memcpy(before,g_catch,sizeof g_catch); assert(nnunwind_catch_reinsert_checked(cfa,jb)); unchanged();
    /* Same CFA on a different host stack is a separate continuation. */
    assert(nnunwind_catch_reinsert_checked(cfa,0x3100));
    assert((uintptr_t)g_catch[(h+1)&(CATCH_SLOTS-1)].jb==0x3100);
    catch_insert(cfa,(jmp_buf *)(uintptr_t)0x1200,1);
    assert((uintptr_t)g_catch[h].jb==0x1200);
    assert((uintptr_t)g_catch[(h+1)&(CATCH_SLOTS-1)].jb==0x3100);
    /* A tombstone is reusable, but an exact match beyond it wins. */
    g_catch[h].cfa=1; g_catch[h].jb=NULL;
    memcpy(before,g_catch,sizeof g_catch); assert(nnunwind_catch_reinsert_checked(cfa,0x3100)); unchanged();
    assert(nnunwind_catch_reinsert_checked(cfa,jb)); assert((uintptr_t)g_catch[h].jb==jb);
    /* Full table failure changes no byte, including diagnostics. */
    reset(); fill(); memcpy(before,g_catch,sizeof g_catch);
    assert(!nnunwind_catch_reinsert_checked(cfa,jb)); unchanged();
    assert(!g_c_crowded&&!g_c_full&&!g_c_maxprobe);
    /* Even a full table may accept an exact existing entry. */
    unsigned slot=127; uint64_t existing=g_catch[slot].cfa, pointer=(uintptr_t)g_catch[slot].jb;
    assert(nnunwind_catch_reinsert_checked(existing,pointer)); unchanged();
    g_catch[slot].cfa=1; g_catch[slot].jb=NULL;
    assert(nnunwind_catch_reinsert_checked(cfa,jb)); assert(g_catch[slot].cfa==cfa);
    /* Hash collisions retain both entries, including wrap around. */
    reset(); while(catch_hash(cfa)!=CATCH_SLOTS-1) cfa+=16;
    uint64_t other=cfa+16;
    while(catch_hash(other)!=catch_hash(cfa)) other+=16;
    assert(nnunwind_catch_reinsert_checked(cfa,jb)); assert(nnunwind_catch_reinsert_checked(other,0x3200));
    assert(g_catch[(catch_hash(cfa)+1)&(CATCH_SLOTS-1)].cfa==other);
    /* Restricted and old probe windows refuse instead of evicting. Legacy keeps its policy. */
    for(int legacy=0;legacy<2;legacy++) {
        reset(); g_cfix=!legacy; g_cprobes=legacy?0:2; fill();
        memcpy(before,g_catch,sizeof g_catch); assert(!nnunwind_catch_reinsert_checked(cfa,jb)); unchanged();
        nnunwind_catch_reinsert(cfa,jb); assert(g_catch[catch_hash(cfa)].cfa==cfa&&g_c_crowded==1);
    }
    reset(); fill(); catch_insert(cfa,(jmp_buf *)(uintptr_t)jb,1);
    assert(g_catch[catch_hash(cfa)].cfa==cfa&&g_c_crowded==1&&g_c_full==1);
    puts("catch_source_test: PASS"); return 0;
}
