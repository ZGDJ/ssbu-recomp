# Source checkpoint and continuation

The owner requested committing all current work and a continuation prompt. This checkpoint includes rollback hardening, diagnostics, production-connected tests, family installer/save/support work, evidence and workflow documentation. Private game inputs, generated binaries, save data and ignored local artifacts are excluded. The fork feature branch is `feat/rollback-validation-audit`; no release, merge or family update-channel change is requested.

[Rollback handoff](../docs/ROLLBACK_HANDOFF.md) gives the next bounded task, source/evidence entry points, local fixture/build commands, protected identities and remaining qualifications. The next packet is copy-worker startup/dispatch/completion failure handling, not a new rollback backend. The milestone ledger remains the sole task-status source.

## Pre-commit verification

The full configured local validation selection passed: project-document validator, its regression suite, common production rollback/resource harness, and all 16 remaining Python suite groups (134 tests across those groups, including 47 family and 13 download tests). Exact-source C tests compile/run at O1/O3 through their Python fixtures. The common input harness retains its explicitly expected M7.4 defect; a passing harness does not fix it.

Commands follow `.github/workflows/project-contract.yml`. Local results/logs are under ignored `artifacts/local/precommit-20261022/`: `results.json` records the initial attempt and `unsandboxed/results.json` records the remaining 16 groups. The initial family run failed with sandbox WinError5 replacement/junction restrictions; the unchanged suite passed outside that sandbox. This is an execution-environment retry, not a relaxed assertion or source fix. Two new-file trailing blank lines were removed during staged whitespace review.

The latest frozen runtime game matrix remains the six passing controls in [capture pool preparation](2026-10-21-capture-pool-preparation.md). This checkpoint does not claim full rollback correctness, full roster, competitive performance or multiplayer qualification. Normal build/save identities remain as documented there; no private game trial output is committed.
