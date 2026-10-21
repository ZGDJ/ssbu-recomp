# Hosted planning CI

- Date: 2026-10-21. Task: M0.5. Requirements: FSD-011/FSD-012. Level: source-only.
- Tested commit: `679a555882be3944f30d980e2c48b9e2b08361f4` on fork branch `docs/opensmash-hardening`.
- [Project contract run](https://github.com/ZGDJ/ssbu-recomp/actions/runs/39618337268): completed, success; GitHub-hosted Windows 2022 and Python 3.12.
- Commands: document validator and 16 targeted validator unit tests in `.github/workflows/project-contract.yml`. No private inputs or game runtime required.
- Verification: primary agent queried GitHub Actions run status after pushing. The separate PR-triggered run was still running at that observation.
- Verdict: M0.5 planning CI acceptance satisfied at the pinned commit. Subsequent changes require their own checks. This is not C/runtime regression, gameplay or full-roster proof; M7.9 still owns source runtime harness CI.
