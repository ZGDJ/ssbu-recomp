# Production resource-policy regression harness

- Date / author / reviewer: 2026-10-21 / root with fault_seams / independent resource_review (no actionable findings).
- Task / requirements: M7.9; FSD-012, FSD-014. Source-only acceptance; game smoke is supplementary.
- Revision: dirty work based on `46a8f6cc56587939c1ce93fd6a1293c8475ab1e1`; isolated runtime build tree digest `b46764cbf021b6c11828de5d969907188208b986304bb5dd424307787776d62a`.
- Environment: configured Windows x64 checkout, bundled Clang 9, existing MSVC/Windows SDK dependencies. No new library required.

`runtime/rb_resource_policy.h` extracts the actual normal snapshot-pool allocation and coordinator pacing policies. Production calls the same helpers tested with injected commit, clock and wait operations. Allocation refusal preserves metadata; tests cover retry, free-list reuse, 256-page batch boundaries and the production capacity. Pacing tests cover exact thresholds, no timer, repeated clock readings and oversleep. Windows adapters preserve original API arguments and ignored timer errors. There is still no total stalled-clock deadline.

`deps/python/Scripts/python.exe tools/run_rollback_tests.py` exited 0. Evidence is retained in ignored `artifacts/local/rollback-tests/run-_jfnls6l/results.json`: resource policy, restore comparison, native protected reads and bounded trace tests passed; existing rollback test reported 211 rollbacks / 512 replayed frames / depth 6. Actual production input tests reproduced the M7.4 retained-input overwrite in all 32 trials, explicitly **NOT FIXED**. The Windows CI job invokes this runner; a hosted CI run was not performed here.

An isolated full build using `scripts/make_release.py --build artifacts/local/runtime-resource-policy --out artifacts/local/runtime-resource-policy-dist --allow-dirty` exited 0 (55 runtime sources). Local package SHA-256: `77a023b0ffc137d74bd21a9a24e5ed48a3b5b48c272906d2595050f3c2ac19c7`. This package was not published. Build log and manifest remain local.

The game-free harness acceptance is met: actual production policies, injectable OS/time/allocation boundaries, deterministic audited-defect reproduction, inherited tests and CI wiring. This does not close M7.1/M7.5/M7.8: whole-capture refusal, native continuation exhaustion, corrupted allocator metadata and stopped-clock recovery remain untested or unfixed. Matching diagnostic fighter traces cannot qualify complete rollback state.

Supplementary smoke: `resource-policy-smoke-a` used the existing isolated Mario/Mario 13.0.5 fixture and fresh imported-save copy described in the restore-localization evidence. It exited 0 in 62.594 seconds. Executable SHA-256 `e9a1c4bd870e21f1dfeae795a9a9fe6179af3ffa2eb46ee9830d7f93963ce698`; command, identity, result and raw traces remain in `artifacts/local/save-import-20261021/resource-policy-smoke-a/`. Restore diagnostics were disabled; bounded fighter target was 500. `tests/bounded_trace_cmp.py` against `bounded-forward-500-a/fight.txt --require-replay` exited 0: 500 real passes and two one-frame replay passes matched. Raw memory verification still differs (including 595 window-1, 7 window-2 and 2 extra pages in the reported 237→238 cycle); this is not a complete-state pass. The normal playable executable retained its prior hash. Project-document validation and all 16 project-document regression tests passed.

Handoff: M7.9 is done; prioritize dependency-ready hardening and the phase-attributed writer experiment in `2026-10-21-replay-writer-map.md`. Do not exclude clock/queue pages based only on static mapping.
