#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include "restore_resources.h"
static int fail, calls;
static void *resize(void *p, size_t n) { ++calls; return fail ? NULL : realloc(p,n); }
int main(void) {
    size_t cap=0; void *p=NULL;
    assert(restore_reserve(&p,&cap,4,16,resize));
    void *old=p; fail=1;
    assert(!restore_reserve(&p,&cap,8,16,resize) && p==old && cap==4);
    assert(restore_reserve(&p,&cap,4,16,resize) && calls==2);
    assert(!restore_reserve(&p,&cap,SIZE_MAX,16,resize) && calls==2);
    fail=0; assert(restore_reserve(&p,&cap,8,16,resize)); free(p);
    assert(fiber_restore_action(1,0,0,1,1,0,0,0)==FIB_RESTORE_NEVER);
    assert(!fiber_restore_action(1,0,0,1,0,0,0,0)); /* needs fresh fiber */
    assert(!fiber_restore_action(1,0,0,0,1,0,0,0));
    assert(!fiber_restore_action(0,1,1,1,1,0,0,0));
    assert(fiber_restore_action(1,1,1,0,0,0,0,0)==FIB_RESTORE_SUSPENDED);
    assert(!fiber_restore_action(1,1,1,1,1,1,0,0));
    assert(!fiber_restore_action(1,1,1,1,1,0,1,0));
    assert(fiber_restore_action(1,1,0,1,1,1,0,1)==FIB_RESTORE_REGS);
    assert(!fiber_restore_action(1,1,0,1,1,1,0,0));
    puts("restore_resources_test: PASS (reserve identity and conservative continuation actions)");
    return 0;
}
