# Protection coverage and refusal audit

2026-10-22, test sub-agent; integration owner retains review and runtime ownership. M7.8 / FSD-005, FSD-012. Source-only bounded finding, not a capability closure. No production changes, game launches, full builds, commits, ledger edits or reservation-lifetime work.

## Result

Existing tests correctly reject reported protection failures, but do not prove complete protection coverage. `test_protection_resources_source.py` exercises the optional `prot_*` diagnostic backend, not the normal learned protection walk. Learned tracking tests set failure counters (including a diagnostic assertion for protection=3) and exercise opening failures, but replace `ls_protect_all` with a stub. Learned startup likewise stubs protection. Learned lifecycle executes setup successfully but does not couple its failed setup coverage to `ls_validate_tracking`.

The new fixture executes exact `ls_protect_all`, `ls_protect_run`, admission helpers, address/exclusion helpers and `ls_validate_tracking` with a controlled VirtualProtect double. Five subprocess cases pass at each of O1/O3:

- Complete: two bulk calls protect all 184 eligible pages; validator accepts.
- Recovered bulk failure: both bulk calls fail, all 184 per-page calls succeed; 186 calls, zero protection failures, complete coverage, validator accepts. Bulk-call failure alone is not a refused capture.
- Refusal177: both bulk calls fail; exactly 177 page calls fail, seven succeed. Validator returns false and reports `metadata count=0 ... protection=177`. A subsequent successful protection setup still refuses with the lifetime-sticky count. This generates the counter through production code rather than assigning 177 to it. It does not identify the historical game failure's cause or addresses. The count is failed page attempts, not necessarily distinct pages over the process lifetime.
- Cross-window boundary: exact production `add_range` merges a hypothetical full-window span with an adjacent one-page span. The learned setup skips the resulting range, protects zero pages, leaves protection failures zero, and the validator accepts. This is a missing-guard reproduction with conditional collector reachability, not an observed supported game layout.
- Partial-page boundary: a directly manufactured PG+1-byte range protects only its first page and validates. This establishes missing geometry validation at the helper boundary, not supported default-path reachability.

The boundary cases deliberately assert current incomplete behavior and use `MISSING_GUARD` markers. Green tests mean the findings reproduce; they do not certify those inputs safe. A remediation must replace these assertions with complete-coverage or explicit-refusal oracles.

## Production reachability assessment

`add_span` clips committed writable OS regions to the supplied interval. `add_alloc` supplies the full allocation span; `mark_setup` independently chooses the largest eligible heap allocation as window 1. `add_range` merges consecutive adjacent spans without checking AllocationBase or window membership. The later collect overlap merge also retains unions without splitting at window boundaries. Thus, **if** a collected committed span ends at window 1's end and the next collected span starts exactly there, the real merge helper produces the reproduced crossing range. Adjacent reservations are not ruled out by these helpers. This audit did not run the complete collector with real allocations, establish heap enumeration order/layout in the supported game, or prove that the hypothetical adjacent allocation is collected. It therefore does not establish an actual default-game coverage defect.

Normal Windows allocation region boundaries and the fixed window-2 interval are page aligned. Fighter writable section lengths are rounded to PG; ordinary PE section placement is page aligned. Presentation metadata size is rounded to PG. Stack cuts use `ex_cb`'s rounded-down/up page endpoints; merge/split operations preserve alignment when their inputs have it. These paths do not manufacture the PG+1 case from aligned input. Optional `SSBU_R1_TEST_CATCH_KB` can request non-page-sized diagnostic spans, and malformed/external metadata would need separate validation, but neither establishes the tested partial tail inside a learned window in the supported default candidate. No default-path partial-tail reachability is claimed.

The whole-range skip and integer-page truncation also exist in pinned upstream `c7c874977ea7510c291ec8c278a58883a2f4e368`. No memory-management policy or exclusion is changed here. Skipping ranges wholly outside learned windows is intentional; the concern is a range partly inside a window. The validator checks metadata/list/failure observations, not an independently enumerated eligible-page inventory.

## Reproduction and identities

Branch `feat/rollback-validation-audit`, HEAD `9ea0c0b82be5aa046857501beb9c3e1c01426d2c`, with pre-existing uncommitted M1.3/runtime work preserved. Windows x64; repository clang 9.0.0, target x86_64-pc-windows-msvc. No private inputs required.

Command: `python -B -m unittest discover -s tests -p test_protection_coverage_audit.py -v` exited 0. Final artifacts: `artifacts/local/protection-coverage-audit/run-iiv0abg2/`: generated exact-source translation, raw source/test/fixture/compiler hashes, compiler version, O1/O3 commands/build logs, ten case logs and results JSON. Both builds and all ten subprocesses exited zero with explicit case oracles. Raw learned source SHA-256: `6496fa6dda0286528a21dbcfc30140c4cc5f9a4d5926fda181600b876d63d94a`. Both production source inputs are byte-checked unchanged after testing. The initial preliminary run `run-f98mm4uk` is retained; it lacked the collector merge helper and used stronger defect labels, superseded by the final classification above. No failed compiled test runs occurred.

## Handoff and stopping point

`python -B tools/check_project_docs.py` exited 0 (document validation passed). Scoped whitespace check passed. The production input diff against HEAD is retained as `artifacts/local/protection-coverage-audit/runtime-inputs.patch`; raw source hashes in the final run manifest are the authoritative tested-input identity.

Frozen files: `tests/test_protection_coverage_audit.py`, `tests/protection_coverage_audit_fixture.c`, this evidence file; raw outputs only under `artifacts/local/protection-coverage-audit/`. Integration review remains pending. Existing suites were inspected, not rerun, because their runners write outside the assigned artifact scope.

Next action: retain the production source unchanged pending supported reachability evidence. In the next integration-owned identified control, record saved-range/window intersections and the first failed per-page protection attempt with OS error and checked region state; distinguish missing intersection coverage from explicit failure. Compare eligible, excluded, successfully protected and refused pages before base publication. Preserve the historical protection=177 refusal and separately owned 176-to-177 membership race. If a partial-window range is confirmed reachable, prepare a bounded split-at-window or explicit-refusal correction with complete-or-refuse tests; do not silently exclude required pages. This audit proves neither actual OS protection semantics nor whole capture/refusal transaction behavior, writer quiescence, gameplay replay, or the historical refusal's origin.
