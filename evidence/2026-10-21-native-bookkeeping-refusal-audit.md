# Native bookkeeping refusal observations

2026-10-21. Follow-up to [native hold failure hardening](2026-10-21-native-hold-failures.md). M7.8 remains in progress. Root owns ring integration/parser/build, a separate agent owns the OS visitor and its fixture, and an independent reviewer checked the frozen candidate.

## Scope and lifecycle

The first eligible `SSBU_RB_REFUSAL_AUDIT=1` attempt now records a separate native bookkeeping baseline after holds and before page-plan/preparation work. It compares after page and command-buffer abort cleanup, before unpark. Successful commits discard the baseline and report `commit_not_checked` before mutation. Ordinary audit-disabled execution does not call the visitor.

The visitor copies exact spans for the raw thread inventory count, object/context identities and each thread object's key/handle/finished fields; all object-table bucket heads and fiber generation; and each live fiber object's key, host-fiber/context pointers, entry, argument, stack bounds, FLS pointers, running thread ID and thread-block pointer. The ring also copies the guest `Ctx` of each thread it currently holds. No struct padding, mutable FLS accessor or enumeration cache is used. Main/native CPU contexts and native stack payloads are outside this extension.

Published objects are never removed and their chain links are immutable in the current implementation. The visitor takes no object lock, which could be owned by a suspended thread. It bounds threads at 256, fibers at 1,024 and all traversed objects at 65,536, including non-fiber objects. Missing inventory entries, bounds, callback/read failures or budget exhaustion make the observation incomplete. The separate 32 MiB budget limits storage, not execution time. Lock-free field reads and the guarded copies do not form an atomic snapshot or prove writer quiescence; logs retain `holds=unproven authoritative=0`.

`NATIVE_REFUSAL_AUDIT` reports threads, fibers, held contexts, spans, changed/unread counts and completeness. `tools/analyze_restore_refusal.py --require-cb --require-native` requires complete native, CB and ring observations at the same refused frame. Present native observations are validated even without the flag. Schema v1 requires exactly `3 + 5*threads + 11*fibers + contexts` spans, so missing structural coverage cannot pass. A matching snapshot is only bounded observation evidence, not full restoration proof.

## Validation

The exact production OS visitor is extracted and compiled against controlled inventory/OS boundaries with the real `RefusalAudit` implementation. O1 and O3 passed at `artifacts/local/native-audit-source/run-q9dj8adw`: field and membership mutation detection, every observer allocation failure, before/after read failures, budget exhaustion, invalid/holey thread inventories, cyclic/excessive traversal and fiber limits. Tests also verify unrelated object fields are excluded. These tests execute the visitor, not the whole live ring transaction. CI runs the fixture separately.

All fifteen refusal-parser tests passed, including missing/mismatched/duplicate/unchecked native records, changed/unread spans and impossible coverage. Independent review found no remaining blocker after tightening the exact span formula.

The isolated runtime built successfully from 55 sources. Manifest: `artifacts/local/runtime-native-audit/package/manifest.json`; tree `58371ffff03bb21c818e29d9348ad1f782368c48c51b9257aff447f7a5829c5e`; package SHA-256 `2ff7a3d4b313ea41b5521f11073902ab3787311ae8ede7709f6293ef27e71a3f`. No package is published.

The local matrix `artifacts/local/save-import-20261021/native-audit-trials-a.json` uses fresh disposable userdata and `ssbu_native_audit_probe.exe` (SHA-256 `ef779cfacfab674ac5d21f02f021957e69d40905076ea55200ee777698d62e98`). `native-audit-default-a` passed 500 real frames and two one-frame replay cycles in 64.032 seconds. `native-audit-late-a` passed 500 real frames and two replay cycles totaling three replay frames in 54.437 seconds; after its injected refusal at frame 118, the first successful rollback covered two frames and the second covered one.

The late-refusal combined audit passed: 31 threads, 21 fibers, 22 held guest contexts and 411 native spans; 66 ring metadata spans; 5,358 readable planned destinations plus 304 verified reservations; 5,694 OS observations; and 703 CB objects/718 spans. All observations were complete with zero changed/unread spans. Reservations are reported separately from compared bytes.

`native-audit-cb-a` passed 500 real frames and two one-frame replays in 54.687 seconds. Its forced CB-preparation refusal at frame 118 also passed all three observers: 31 threads, 21 fibers, 22 held contexts/411 native spans; 66 ring metadata spans; 5,260 readable destinations with no reservations; 5,292 OS observations; and 705 CB objects/720 spans, all complete and unchanged/readable. Every required launcher, sealed telemetry comparator and combined audit exited zero. The earlier unexplained page-plan refusal did not recur and is not reclassified.

Final normalized source hashes matched the manifest, the normal playable executable and game DLL retained their prior hashes, and all 24 installed save files matched the extracted fixture. Documentation validation and whitespace checks passed. The tests ran in disposable userdata; no shared executable, installed save or online protocol was replaced.

## Remaining scope

Native registers, suspended stack/FLS payloads, complete scheduler ownership, catch-table restoration, fresh-fiber recovery and replay-state divergence remain open. The earlier unexplained page-plan refusal and incomplete observations remain preserved. This packet adds observation coverage; it does not qualify online play or complete M7.1/M7.8.
