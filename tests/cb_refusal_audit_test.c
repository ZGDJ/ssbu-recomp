#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
typedef struct { uint8_t *data; size_t len, cap; uint8_t metadata[96]; } CbCaptureRecord;
#include "cb_refusal_audit.h"
typedef struct {
    size_t calls, fail, outstanding; int unread, reports, refused, complete;
    size_t objects, changed, unread_before, unread_after;
} Fixture;
static void *allocate(void *ctx,size_t size) {
    Fixture *f=ctx; if(++f->calls==f->fail) return NULL;
    void *p=malloc(size); if(p) ++f->outstanding; return p;
}
static void release(void *ctx,void *p) { Fixture *f=ctx; if(p) { assert(f->outstanding); --f->outstanding; free(p); } }
static int read_span(void *ctx,const void *p,void *out,size_t n,int kind) {
    Fixture *f=ctx; if(f->unread) return 0;
#ifdef _WIN32
    return refusal_audit_read_windows(NULL,p,out,n,kind);
#else
    (void)kind; memcpy(out,p,n); return 1;
#endif
}
static void report(void *ctx,const CbRefusalAudit *a,long long frame,int refused) {
    Fixture *f=ctx; assert(frame==118); ++f->reports; f->refused=refused;
    f->complete=refused&&refusal_audit_complete(&a->bytes); f->objects=a->objects;
    f->changed=a->bytes.changed[REFUSAL_METADATA];
    f->unread_before=a->bytes.unread_before; f->unread_after=a->bytes.unread_after;
}
static CbCaptureSave stage[CB_CAPTURE_MAX], saved[1];
static CbCaptureRecord live, *registry[CB_CAPTURE_MAX];
static int stage_count=1,registry_count=1,lost;
static uint8_t target[16];
static CbRefusalTransaction *prepare(Fixture *f,int force,size_t budget) {
    return cb_refusal_prepare(saved,1,target,sizeof target,stage,&stage_count,registry,&registry_count,&lost,
        118,1,force,budget,read_span,allocate,release,report,f);
}
static void capture(CbRefusalAudit *a,Fixture *f,size_t budget) {
    cb_refusal_capture(a,stage,&stage_count,registry,&registry_count,&lost,budget,read_span,allocate,release,f);
}
int main(void) {
    Fixture f={0}; live.data=allocate(&f,4); live.len=live.cap=4;
    stage[0].data=allocate(&f,4); stage[0].cap=4; stage[0].cb=&live;
    registry[0]=&live; stage[0].copy=live;
    memset(live.data,0x11,4); memset(stage[0].data,0x22,4); memset(target,0x33,sizeof target);
    saved[0].cb=&live; saved[0].copy=live;
    saved[0].copy.len=saved[0].copy.cap=saved[0].cap=sizeof target;
    saved[0].data=saved[0].copy.data=(uint8_t *)(uintptr_t)0x1000;
    f.calls=0;
    CbRefusalTransaction *tx=prepare(&f,0,64u<<20); assert(tx);
    size_t allocations=f.calls;
    cb_refusal_abort(tx);
    assert(f.reports==1 && f.complete && f.refused && f.objects==1 && !f.changed && f.outstanding==2);
    /* Every allocation failure includes audit partial capture, detached plan,
     * both replacement buffers, and the final transaction wrapper. */
    for(size_t fail=1;fail<=allocations;fail++) {
        f.calls=f.reports=0; f.fail=fail;
        tx=prepare(&f,0,64u<<20); if(tx) cb_refusal_abort(tx);
        assert(f.reports==1 && f.refused && !f.changed && f.outstanding==2);
        assert(live.len==4 && live.cap==4 && stage[0].cap==4 && stage_count==1);
        for(int i=0;i<4;i++) assert(live.data[i]==0x11 && stage[0].data[i]==0x22);
        if(fail==allocations) assert(!tx && f.complete); /* wrapper allocation after all detached allocations */
    }
    f.fail=0; f.calls=f.reports=0;
    assert(!prepare(&f,1,64u<<20) && f.reports==1 && f.complete && !f.changed && f.outstanding==2);
    f.reports=0; tx=prepare(&f,0,64); assert(tx); cb_refusal_abort(tx);
    assert(f.reports==1 && !f.complete && f.outstanding==2);
    f.reports=0; f.unread=1; tx=prepare(&f,0,64u<<20); assert(tx); cb_refusal_abort(tx);
    assert(f.reports==1 && !f.complete && f.unread_before && f.unread_after && f.outstanding==2); f.unread=0;
    /* Record pointers, scalar metadata, staging bytes, live bytes and registry
     * identity all have exact-byte comparisons. No stale pointer dereference. */
    for(int change=0;change<5;change++) {
        CbRefusalAudit audit; capture(&audit,&f,64u<<20);
        uint8_t *original=live.data;
        if(change==0) live.data=(uint8_t *)(uintptr_t)1;
        if(change==1) live.metadata[0]^=1;
        if(change==2) stage[0].data[0]^=1;
        if(change==3) original[0]^=1;
        if(change==4) registry[0]=NULL;
        cb_refusal_finish(&audit,118,1,report,&f);
        assert(f.complete && f.changed && f.outstanding==2);
        if(change==0) live.data=original;
        if(change==1) live.metadata[0]^=1;
        if(change==2) stage[0].data[0]^=1;
        if(change==3) original[0]^=1;
        if(change==4) registry[0]=&live;
    }
    /* Commit disposes observation before live writes and reports unchecked. */
    f.reports=0; tx=prepare(&f,0,64u<<20); assert(tx); cb_refusal_commit(tx);
    assert(f.reports==1 && !f.refused && !f.complete && f.outstanding==2);
    assert(!memcmp(live.data,target,sizeof target) && !memcmp(stage[0].data,target,sizeof target));
    release(&f,live.data); release(&f,stage[0].data); assert(!f.outstanding);
    puts("cb_refusal_audit_test: PASS (live/staging identity, abort, allocation failures and observation bounds)");
    return 0;
}
