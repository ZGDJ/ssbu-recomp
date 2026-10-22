#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include "../runtime/restore_plan.h"
typedef struct { int calls, fail, live, changes, undo_fail; } Fixture;
static void *allocate(void *ctx, size_t bytes) { Fixture *f=ctx; if (++f->calls==f->fail) return NULL; void *p=malloc(bytes); if(p) f->live++; return p; }
static void release(void *ctx, void *p) { if(p) { ((Fixture *)ctx)->live--; free(p); } }
static int prepare(void *ctx, RestorePage *p) { Fixture *f=ctx; p->committed=1; f->changes++; return ++f->calls != f->fail; }
static int undo(void *ctx, RestorePage *p) { Fixture *f=ctx; if(p->committed) { if(f->undo_fail) return 0; p->committed=0; f->changes--; } return 1; }
int main(void) {
    Fixture f={0}; RestorePlan p={0}; uint32_t live[4]={7,8,9,10}, original[4]; memcpy(original,live,sizeof live);
    f.fail=2; assert(!restore_plan_init(&p,4,4,allocate,release,&f)); assert(!f.live && !p.pages);
    f=(Fixture){0}; assert(restore_plan_init(&p,4,4,allocate,release,&f));
    for(uint32_t i=0;i<4;i++) assert(restore_plan_put(&p,i,live[i],0));
    assert(restore_plan_put(&p,2,5,1)); assert(restore_plan_put(&p,2,3,1));
    assert(restore_plan_put(&p,2,99,0)); assert(p.count==4 && p.pages[2].value==3);
    assert(!restore_plan_put(&p,4,0,1)); assert(!memcmp(live,original,sizeof live));
    f.calls=0; f.fail=3; assert(restore_plan_prepare(&p,prepare,undo,&f)==0); assert(!f.changes);
    f.calls=0; f.fail=0; assert(restore_plan_prepare(&p,prepare,undo,&f)==1); assert(f.changes==4);
    assert(restore_plan_unprepare(&p,undo,&f)); assert(!f.changes);
    f.calls=0; f.fail=2; f.undo_fail=1; assert(restore_plan_prepare(&p,prepare,undo,&f)==-1);
    f.undo_fail=0; assert(restore_plan_unprepare(&p,undo,&f));
    int calls=f.calls; for(size_t i=0;i<p.count;i++) live[p.pages[i].id]=p.pages[i].value;
    assert(live[2]==3 && f.calls==calls); restore_plan_dispose(&p,release,&f); assert(!f.live);
    assert(!restore_plan_init(&p,SIZE_MAX,4,allocate,release,&f));
    puts("restore_plan_test: PASS (immutable overlay, late refusal cleanup, cleanup failure, allocation-free apply)"); return 0;
}
