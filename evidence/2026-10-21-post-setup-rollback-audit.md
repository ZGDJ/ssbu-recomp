# Post-setup rollback audit and first automated regressions

- Date: 2026-10-21. Integration: root; independent read-only native-state review: root/audit; harness: root/harness; comparator implementation: root/comparators. Integration reviewed production call sites and added the shared missing-frame rejection.
- Base: `46a8f6cc56587939c1ce93fd6a1293c8475ab1e1`, branch `feat/rollback-validation-audit`; uncommitted patch identity retained under ignored `artifacts/local/rollback-audit/`. No runtime or generated game-source edits.
- Tasks: M0.10 (diagnostic gates), partial M7.9 (production input harness), expanded M7.8 investigation; FSD-012/FSD-014. Levels: source-only tests plus an explicitly nonqualifying local navigation probe.
- Environment: configured Windows x64 checkout, isolated Python 3.12.3, clang 9.0.0 targeting x86_64-pc-windows-msvc. No new downloads or third-party dependency required.

## Decision

Retain ADR-0007 provisionally. Normal play with a save is valuable baseline availability but does not prove state restoration. Existing 13.0.5 GA mappings cover worker kicks, boundary return and frame end. No observed invariant justifies replacing the backend with GGPO or returning to WindowSmash. Keep complete-or-refuse restoration and terminal confirmation ahead of online qualification.

Review reconfirmed busy/skipped continuation restore can report success, missing correction states can be consumed, terminal teardown is speculative, input epochs/bounds are weak and hashes cover selected telemetry. Additional capture table/pool omissions in `fib_cb` expand M7.8; event/queue observation is not proof of restored service state. The address verifier was inspected but not run: its matching external decompilation `functions.csv` was not located in the configured build/local inputs. No complete Ultimate decompilation or exhaustive generated-code audit is claimed.

## Source experiments

- `deps/python/Scripts/python.exe tools/run_rollback_tests.py`: exit 0. Actual production `rb_input.c` receives deterministic injections. All 32 trials reproduce far-future frame `1 + RB_RING` replacing retained frame 1, while the contiguous/available-input horizon remains 1. This is an **unfixed defect**, explicitly labeled by the runner; it is not a rollback correctness pass.
- The same runner builds/runs inherited `rb_test`: 211 toy rollbacks, 512 resimulated frames, maximum depth 6; all passed. These do not exercise native snapshots or Ultimate gameplay.
- Missing compiler and tiny-timeout negative runs exit 1. Initial compiler temporary-file rename failed under sandbox; using isolated per-run TMP/TEMP/TMPDIR resolved it. Original failure retained.
- A disposable copy of `rb_input.c` with a future-bound rejection makes the expected-defect test fail (128 assertions), demonstrating that removal of the defect cannot silently keep the reproduction green. Production runtime was not modified.
- `deps/python/Scripts/python.exe -m unittest discover -s tests -p test_rollback_comparators.py -v`: exit 0, 10 tests with subprocess subcases. Empty logs, missing/partial/shared-gapped coverage, missing replay, skipped replay runs, real/replay differences, invalid IDs and conflicting duplicate samples reject. Positive fixtures preserve the runtime's actual trailing float text and intentional running-hash exclusion.
- `deps/python/Scripts/python.exe -m unittest discover -s tests -p test_project_docs.py -v`: exit 0, 16 tests.
- Windows project-contract workflow now runs the C harness and comparator regressions. Hosted CI was not run; local results do not certify a hosted run.

## Scope and handoff

M0.10 covers the two named rollback comparators only. `r1_cmp.py` remains reporting-only; M0.7 still owns the separate differential harness audit. Equal truncated peer logs can only establish their compared interval; callers must separately require the planned trial length. Fighter hashes remain incomplete state telemetry.

M7.9 remains open: production input-boundary injection and CI wiring exist, but OS/time/allocator/native-state fault seams remain. Next implement capture resource-failure injection, including native fiber-table/pool limits, then complete-or-refuse restore and pending-correction handling. Keep M7.4 future-input rejection as a separate runtime fix with preservation assertions and full epoch/race cases.

Before gameplay qualification, finish build identity/cache/hook prerequisites and a reproducible two-player fixture. Run forward replay and restore/replay against an uninterrupted oracle, then terminal reversals and effects; preserve depth-eight acceptance and full-roster gates. No complete match, replay, network, performance or full-roster gate closed by this work.

## Local artifact retention

Raw command/results logs are in `artifacts/local/rollback-tests/`: successful `run-su3r697y`, first-failure `run-nlzaefbj`, missing-compiler `run-p8zo_qvs`, timeout `run-ju7hxo9v`, and `mutation-check`. Navigation logs, copied saves, executable/game ELF/library/tape hashes and captured frames are under `artifacts/local/rollback-audit/`. Private data is ignored and not part of the patch.

## Bounded navigation result

Ran `scripts/run.py` with isolated `artifacts/local/rollback-audit/smoke-userdata`, distinct `ssbu_audit_probe.exe`, `--seconds 180`, `tests/seq_completo_1305.txt`, seed 12345, online off, rollback off, movie skip and fighter hash/screenshot logs. Exact resolved paths and binary/tape hashes are retained locally. This uses the installed prebuilt runtime plus locally generated game library, not a newly built modified runtime.

Process exit 0 after 185 seconds. The input sequence passed movie/title recognition and its first confirm, then stopped progressing. Inspected frame 1800: Piranha Plant DLC welcome notification. Fighter hash file: zero bytes. Verdict: navigation fixture failed to reach a battle; no comparison attempted and no game capability gate closed. The configured save source was `build/saves`; the owner's separate working save location, if different, still needs identification. Original save files and executable/library/ELF/tape hashes matched before/after. Only the disposable save copy was supplied to the test process.

Final project-document validation and `git diff --check` passed. Runtime failure seams, full identity tooling and actual battle replay remain the next work; no recurring/background test service was installed.
