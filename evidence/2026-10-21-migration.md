# Planning migration to OpenSmash

- Date: 2026-10-21. Author: primary agent; independent documentation author/reviewer and scope review.
- Tasks: M0.1, M0.3, M0.6. Level: source-only documentation/validator verification. No game-backed capability closed.
- Base: OpenSmash `c7c874977ea7510c291ec8c278a58883a2f4e368`. Changes are the `docs/opensmash-hardening` branch; this report is included in its commit, whose Git identity identifies the reviewed snapshot without a self-referential hash.
- Planning source: WindowSmash `cb110e7e0638acd126fdbe16da5e4011f8e966cf`. Migrated FSD-001â€“015, ADR-0001â€“0006 history, work/validation contracts, ledger IDs, validator and 16 regression tests. Preserved OpenSmash license and original README.
- Decisions: ADR-0007 adopts native page/fiber snapshots and custom rollback provisionally; GGPO remains an interface/reference option. Added M7.1â€“M7.9 for the eight audited gap classes and production-connected harness. No runtime patches were transplanted.
- Status reset: M0.4/0.5/0.7, M1.1/1.3/1.4 reopen because previous implementation/evidence is WindowSmash-specific. M1.2 remains blocked by missing private inputs/build. M0.2 is supported by the separate OpenSmash audit. M0.1/0.3/0.6 cover the migrated contract/validator/design only. Historical statuses remain in the prior pinned repository.
- Verification commands: `python tools/check_project_docs.py`; `python -m unittest discover -s tests -p test_project_docs.py -v`; `git diff --check`. Final results are recorded below after review.
- Scope limits: no game build, C compilation, gameplay, performance, hosted CI or roster qualification is claimed here. M0.5 requires a hosted CI run; M7 source passes cannot close actual-battle gates. Eight-tick FSD correctness remains despite inherited seven-frame nominal window.
- Raw retention: no game artifacts produced. Changes, test sources and sanitized report are committed; upstream audit records the earlier lobby result and failed sandbox attempt.

## Final verification

All three verification commands above exited 0 on the reviewed migration: document validation passed; all 16 validator tests passed; diff whitespace check passed. The ledger calculates 38 tasks: 4 documentation/source-investigation tasks done, 33 todo, 1 blocked; 167 relative scope units, 8 closed. These are scope counts, not capability confidence or time estimates.

Independent scope review found a restore-contract ambiguity. Resolved it: preflight refusal leaves state/history unchanged; unexpected failure after mutation irrecoverably terminates the session and never resumes or returns success. Review otherwise found the scope, dependency graph and provisional backend/GGPO direction aligned.

Next: M7.9 production-connected harness first; M1.1 identity tooling and M6.1 roster/mechanics inventory are independent ready work. M0.5 remains open for hosted CI evidence. No runtime correctness gate is closed by this report.
