/* Included by r1_ring.c. Detached incremental capture comparisons and ownership
 * assignment precede eviction. Host-writer quiescence remains unproven. */
typedef struct { uint32_t id, old, value; } RgCaptureOp;
static RgCaptureOp *g_rg_ops;
static size_t g_rg_ops_cap, g_rg_ops_count, g_rg_copy_count;
static uint8_t *g_rg_capture_seen; static size_t g_rg_capture_seen_cap;
static CapturePoolPlan g_rg_pool_plan;
static size_t g_rg_pool_free_cap, g_rg_pool_assigned_cap, g_rg_pool_owned_cap;
static int g_rg_op_failed;
static int rg_capture_candidate(uint32_t id) {
    size_t total = g_rg_n1 + g_rg_n2 + g_rg_nx;
    if ((size_t)id >= total) return 0;
    uint32_t source = g_rg_idx[id];
    if (source >= 2 && source - 2 >= g_rg_bump) return 0;
    uint8_t bit = (uint8_t)(1u << (id & 7));
    if (g_rg_capture_seen[id >> 3] & bit) return 0;
    g_rg_capture_seen[id >> 3] |= bit; return 1;
}
static void rg_capture_collect(uint32_t id, int w, size_t j) {
    uint32_t old = g_rg_idx[id];
    if (!w && g_dc[j] && old == RG_DECOM) return;
    if (g_rg_ops_count >= g_rg_capture_entries) { g_rg_op_failed = 1; return; }
    RgCaptureOp *op = &g_rg_ops[g_rg_ops_count++];
    op->id = id; op->old = old;
    op->value = !w && g_dc[j] ? RG_DECOM : 0;
    if (!op->value) g_rg_copy_count++;
}
static int rg_capture_page_plan(void) {
    g_rg_ops_count = g_rg_copy_count = 0; g_rg_op_failed = 0;
    size_t total = g_rg_n1 + g_rg_n2 + g_rg_nx, seen_bytes = (total + 7) / 8;
    g_rg_capture_refusal = "pool source bounds";
    if (!g_rg_capture_prepared || !g_cp_reserved || g_ncj || !g_rg_idx ||
        g_rg_bump > g_rg_pcom || g_rg_pcom > RG_POOL_MAX || g_rg_pcom % 256) return 0;
    void *storage = g_rg_ops;
    g_rg_capture_refusal = "detached operation storage";
    if (!restore_reserve(&storage, &g_rg_ops_cap, g_rg_capture_entries, sizeof *g_rg_ops, realloc)) return 0;
    g_rg_ops = storage; storage = g_rg_capture_seen;
    if (!restore_reserve(&storage, &g_rg_capture_seen_cap, seen_bytes, 1, realloc)) return 0;
    g_rg_capture_seen = storage;
    if (seen_bytes) memset(g_rg_capture_seen, 0, seen_bytes);
    g_rg_capture_refusal = "pool planning storage";
    storage = g_rg_pool_plan.free_ids;
    if (!restore_reserve(&storage, &g_rg_pool_free_cap, RG_POOL_MAX, sizeof(uint32_t), realloc)) return 0;
    g_rg_pool_plan.free_ids = storage; storage = g_rg_pool_plan.owned;
    if (!restore_reserve(&storage, &g_rg_pool_owned_cap, RG_POOL_MAX, 1, realloc)) return 0;
    g_rg_pool_plan.owned = storage;
    size_t assignments = g_rg_capture_entries < RG_POOL_MAX ? g_rg_capture_entries : RG_POOL_MAX;
    storage = g_rg_pool_plan.assigned;
    if (!restore_reserve(&storage, &g_rg_pool_assigned_cap, assignments, sizeof(uint32_t), realloc)) return 0;
    g_rg_pool_plan.assigned = storage;
    g_rg_capture_refusal = "extras comparison source";
    for (size_t e = 0; e < g_rg_nx; e++) {
        uint32_t id = (uint32_t)(g_rg_n1 + g_rg_n2 + e);
        if (!rg_capture_candidate(id)) { g_ncj = 0; return 0; }
        uint8_t *src = rg_src(id);
        if (!src || src == (uint8_t *)1) { g_ncj = 0; return 0; }
        cp_add(g_rg_xa[e], src);
    }
    g_cp_cmp = g_rg_xdiff; cp_run(); g_cp_cmp = NULL;
    g_rg_capture_refusal = "capture candidate inventory";
    if (g_ls_active) {
        if (!ls_capture_plan(rg_capture_collect, rg_capture_candidate)) return 0;
    } else {
        for (size_t k = 0; k < g_rg_mark_count; k++) {
            uint32_t id = g_rg_mark_ids[k]; int w = id >= g_rg_n1;
            size_t j = w ? id - g_rg_n1 : id;
            if (!rg_capture_candidate(id)) return 0;
            if ((g_audio_free && is_async(rg_addr(id))) || (w ? g_ns2[j] : g_ns1[j])) continue;
            rg_capture_collect(id, w, j);
        }
    }
    for (size_t e = 0; e < g_rg_nx; e++) if (g_rg_xdiff[e]) {
        uint32_t id = (uint32_t)(g_rg_n1 + g_rg_n2 + e);
        rg_capture_collect(id, 2, e); /* Extras have no decommit-map entry. */
    }
    if (g_rg_op_failed || g_rg_copy_count > RG_POOL_MAX) return 0;
    CapturePoolSlot slots[RG_MAXSLOT];
    g_rg_capture_refusal = "pool ring bounds";
    if (g_rg_count <= 0 || g_rg_count > g_rg_cap || g_rg_cap > RG_MAXSLOT || g_rg_cap <= 0) return 0;
    for (int k = 0; k < g_rg_count; k++) {
        RgSlot *s = rg_slot(k);
        if (s->nent > RG_ENT_RES / 8 || s->nent > s->entcom / 8 || s->entcom > RG_ENT_RES) return 0;
        slots[k] = (CapturePoolSlot){s->ent, s->nent, s->frame};
    }
    CapturePoolInput input = {g_rg_bump, g_rg_pcom, RG_POOL_MAX, g_rg_free, g_rg_nfree,
        g_rg_idx, total, slots, (size_t)g_rg_count, (size_t)g_rg_cap, g_rg_need,
        g_rg_poolfix, g_rg_tp_active, g_rg_tp_mode, (uint64_t)g_rg_tp_gets};
    int ok = capture_pool_prepare(&input, g_rg_copy_count, &g_rg_pool_plan, rg_pool_commit, NULL);
    /* Only physical commitment and diagnostic attempts survive refusal. */
    g_rg_pcom = g_rg_pool_plan.committed;
    g_rg_tp_gets = (int)g_rg_pool_plan.test_gets;
    g_rg_tp_refused += (long long)g_rg_pool_plan.test_refused;
    if (!ok) { g_rg_capture_refusal = g_rg_pool_plan.reason; return 0; }
    size_t copy = 0;
    for (size_t k = 0; k < g_rg_ops_count; k++) if (!g_rg_ops[k].value)
        g_rg_ops[k].value = g_rg_pool_plan.assigned[copy++];
    if (g_rg_pool_fail_after > 0) g_rg_pool_fail_after--;
    else if (g_rg_pool_fail_count > 0) {
        g_rg_pool_fail_count--; g_rg_capture_refusal = "test failure after pool commitment"; return 0;
    }
    g_rg_capture_refusal = NULL; return 1;
}
static void rg_capture_execute(RgSlot *s, long long frame) {
    /* No pool put/take here: publish the already validated ownership result. */
    for (size_t k = 0; k < g_rg_pool_plan.drop_count; k++) {
        rg_slot_drop(rg_slot(0), 0); g_rg_head = (g_rg_head + 1) % g_rg_cap; g_rg_count--;
    }
    if (g_rg_pool_plan.free_count) memcpy(g_rg_free, g_rg_pool_plan.free_ids, g_rg_pool_plan.free_count * sizeof *g_rg_free);
    g_rg_nfree = (uint32_t)g_rg_pool_plan.free_count; g_rg_bump = g_rg_pool_plan.bump;
    g_rg_freed_slots += (long long)g_rg_pool_plan.extra_drops;
    s->frame = frame; s->nent = s->pages = s->xpages = 0; g_rg_cur = s; g_rg_fail_now = 0;
    for (size_t k = 0; k < g_rg_ops_count; k++) {
        const RgCaptureOp *op = &g_rg_ops[k];
        if (g_rg_idx[op->id] != op->old || !rg_push(s, op->id, op->old)) {
            LOG("r1: fatal: prepared capture operation changed after mutation\n"); abort();
        }
        g_rg_idx[op->id] = op->value;
        if ((size_t)op->id < g_rg_n1 + g_rg_n2) {
            s->pages++;
            if (op->value >= 2 && g_rgpg_on > 0) rgpg_note(rg_addr(op->id));
        } else s->xpages++;
        if (op->value >= 2) cp_add(rg_pool_ptr(op->value), rg_addr(op->id));
    }
    if (g_ls_active) ls_capture_plan_commit(s->pages);
    else for (size_t k = 0; k < g_rg_mark_count; k++) {
        uint32_t id = g_rg_mark_ids[k];
        if (id < g_rg_n1) (*pm1)[id] = 0; else (*pm2)[id - g_rg_n1] = 0;
    }
}
