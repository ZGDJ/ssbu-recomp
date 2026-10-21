# OpenSmash baseline audit

- Date: 2026-10-21. Authors: primary agent with independent coordinator/network and native-state reviewers.
- Task: M0.2. Requirement: FSD-012; informs FSD-002/004/005/008/015.
- Level: source-only. Revision: `c7c874977ea7510c291ec8c278a58883a2f4e368`, clean checkout during audit.
- Environment: Windows x64, Python 3.12. No private game inputs/build; suitable C compiler not found on PATH or standard LLVM location.
- Commands: `git rev-parse HEAD`, `git status --short` succeeded. `python tools/net/test_ssbu_lobby.py` first failed with no WELCOME packet in the restricted sandbox; outside it exited 0 with all lobby self-tests passing. This records the rerun result, not a proven root cause for the initial failure.
- Findings/artifacts: [source audit](../docs/ROLLBACK_AUDIT.md); source references and sanitized observations only. No raw game traces exist. Primary agent reviewed critical paths alongside independent network and native-state reviews.
- Exclusions: C toy rollback test not run; no gameplay, oracle, performance, cross-machine or roster qualification. Upstream measured-match claims not reproduced.
- Verdict: source baseline documented; capability gates remain open. Begin production-connected regressions and failure-path hardening.
