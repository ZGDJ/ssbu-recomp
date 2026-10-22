# Agent entry point

Target Ultimate 13.0.5, Windows x64, full-roster competitive 1v1 rollback.
Advance the next falsifiable battle proof: a verified fix, a causal finding, a narrowed divergence, or an enabled gameplay experiment.
OpenSmash rollback exists but is unqualified; distinguish source acceptance, exploratory observations and formal gameplay evidence.
Read ADR-0007 and docs/ROLLBACK_AUDIT.md before changing the inherited backend.

## Context and ownership

- Read `milestones/README.md` first; it alone owns task status and dependencies.
- Select work from the ledger proof-first queue and current dependencies; build on completed prerequisites and existing tools.
- Read the current handoff summary, then selected FSD requirements, relevant ADRs and affected source. Historical checkpoints are evidence, not active instructions.
- `docs/AGENT_WORKFLOW.md` defines packets; `docs/VALIDATION.md` defines evidence.
- Inspect `git status` and nested instructions; preserve unrelated edits.
- Claim one ready task with owner and UTC timestamp; assign exclusive edit scopes for complementary work.

## Execute and verify

- Work autonomously within acceptance criteria; ordinary local edits/tests need no reconfirmation.
- Establish battle boundaries and state ownership from source and experiments before defining interfaces.
- Give each packet a concrete defect or gameplay outcome, decisive observation and stopping criterion. Use the result to select the next action.
- Prefer original recompiled behavior; justify semantic changes with ADRs and evidence.
- Compare semantic changes to pinned upstream behavior; self-consistent replay alone is insufficient.
- Critical hooks must uniquely validate against 13.0.5 and fail closed on mismatch.
- Follow `docs/ROLLBACK_DESIGN.md`; prove confirmation-safe match end and preserve input history.
- Apply the validation contract to changed risk; run affected checks, fix introduced regressions, and record commands/results.
- Run authorized synthetic tests autonomously using disposable fixtures.
- Run `python tools/check_project_docs.py` after project-documentation changes.
- Use root BUILDING.md; WindowSmash tools/evidence are historical, not this runtime's baseline.
- Done requires acceptance evidence and done dependencies; the validator checks structure, not truth.
- Missing private inputs block game tests; mocks cannot close game-backed gates.
- Deliver the change or finding, decisive evidence, remaining uncertainty and next action; update the ledger and short current handoff.
- Capture useful workflow friction and improve the method through the bounded process in `docs/AGENT_WORKFLOW.md`, preserving acceptance coverage.

## Authorized collaboration

- Owner authorizes implementation, tests, commits, pushes to the fork and draft PRs.
- Use feature branches and draft PRs against the fork, not upstream; verify remotes first.
- Merges, releases, paid resources and destructive history changes need explicit authorization.
- Delegate disjoint investigations or high-risk state/scheduling review when useful.
- Parallelize disjoint investigations and source tests; integration coordinates the frozen candidate, serialized game trials and final verdict.
- Keep private inputs/generated code/dumps out of Git; use ignored `artifacts/local/`.
- Commit sanitized evidence; preserve notices and do not invent a project-wide license.
- Do not schedule recurring execution merely because this workflow supports autonomy.
