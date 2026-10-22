# Autonomous work and Astra sizing

Start with [AGENTS.md](../AGENTS.md) and [ledger](../milestones/README.md); load only relevant requirements, ADRs and source. These conventions serve GPT-6 Astra and other agents; they do not configure an API/model.

For the current rollback continuation checkpoint, see [rollback handoff](ROLLBACK_HANDOFF.md). Recheck the ledger and worktree because the handoff records a dated checkpoint.

## Adopted upstream and gates

Work from OpenSmash upstream `c7c874977ea7510c291ec8c278a58883a2f4e368` and [ADR-0007](../adr/0007-opensmash-adoption-and-hardening.md). Inspect the existing `r1_*` / `rb_*` implementation before proposing replacements. M7.1–M7.8 are bounded source-hardening tasks; completing them does not close private-data, gameplay or full-roster M1–M6 gates. Use root [BUILDING.md](../BUILDING.md), not the former WindowSmash build commands or evidence.

## Work loop

1. Inspect the worktree; select unclaimed dependency-ready work. Independent source tasks can proceed around private-data blockers.
2. Claim with owner/session and UTC timestamp; set `in_progress` and next action. Claims coordinate, not lock. Coordinate before taking active/stale claims.
3. Define a falsifiable investigation or cohesive implementation. Investigate unknown ownership before coding assumptions.
4. Implement, run affected checks, inspect the diff, record evidence. Fix introduced regressions; keep baseline failures visible.
5. Independently review high-risk continuation/state/scheduling work.
6. Done requires acceptance evidence and completed dependencies. Negative research can finish an investigation, not a capability gate: create remediation and rewire dependencies.
7. Continue authorized work or hand off exact blockers. Do not spin or invent recurring schedules.

## Packet template

```text
Task/outcome: Mx.y / one sentence
Context: requirement, ADR, source symbols, relevant prior evidence
Ownership: exact files/subsystem; other active writers
Non-goals: deferred scope
Approach: bounded experiment/implementation
Acceptance: observable result + command/manual procedure
Artifacts: code/tests + evidence + ledger update
Split/stop: missing prerequisite, architecture decision, excessive scope
Handoff: results, uncertainty, next action
```

## Shared-work integration checkpoint

For stateful runtime changes, assign exclusive file ownership and agree on function signatures before parallel edits. The integration owner alone launches the game and owns shared caller wiring. A reviewer stays read-only until assigned a separate edit scope. Avoid concurrent builds while source writers are still changing files.

Before building, each writer reports its frozen file list, interface contract, tests performed and remaining limitations. The reviewer acknowledges that exact candidate. Later source edits invalidate the corresponding runtime manifest: rebuild before claiming game evidence applies. Verify normalized source hashes against the manifest after the final trial. A helper test proves its policy, not the integrated runtime lifecycle.

Use a sequential, fail-fast trial batch with fresh userdata and distinct executable identity. Run the default control first, then boundary refusals and recovery. Stop if the default cannot produce mandatory replay; preserve that failed control and investigate instead of weakening the comparator. Record process exit, sealed trace comparison, injected refusal reason, history observations and binary identity separately. A process exit alone is never a pass.

Before memory-heavy snapshot trials, record available system commit and check for a separate normal game process as well as prior test processes. Idle-host headroom is not the snapshot-time headroom: game startup consumes additional commit. A normal game may run outside this checkout, so verify process identity/path rather than assuming the test executable is the only instance. Preserve an initial-snapshot refusal as a failed mandatory-replay control; resume after resolving the resource condition, without weakening the guard or comparator. Close a user game only with authorization, preferring its normal window-close path.

Distinguish a launcher time limit from the required trace length. Repeated failure paths can run much slower than a normal control. Preserve timed-out runs; when extending a duration, retain the same binary, trace requirement and comparison checks, and keep the wrapper timeout longer than the launcher plus cleanup. Save a machine-readable matrix of launcher and comparator outcomes so a successful process exit cannot hide an incomplete trace.

For restore transactions, review preparation, commit and abort together. List every allocation, lock, thread hold, page commitment/protection change and ownership transfer. Verify late failure after earlier success, cleanup failure escalation, and a commit with allocation disabled. Keep prior guest bytes/history unchanged on refusal; explicitly distinguish harmless retained host capacity and diagnostic counters. Preserve known semantic limitations rather than expanding a narrow resource test into a complete-state claim.

For static runtime functions that cannot be linked independently, a source harness may compile their exact current bodies against narrow OS boundaries. Keep the generated translation unit and compiler/run output as local evidence, fail if extraction cannot find the function, and exercise caller cleanup as well as the return-code helper. State which surrounding caller paths remain source-reviewed or game-tested; an extracted hold function does not itself test the entire ring transaction.

## Keep changes readable and removable

- Use the [source map](UPSTREAM.md#source-seams) to find existing owners before adding a file or abstraction. Keep one owner for each fact, state buffer and clock.
- Keep new battle hooks thin. Put checkpoint policy and session coordination behind the proven battle boundary; do not spread networking decisions through HLE services or generated game code.
- Prefer a concrete function or module over a plugin system, generic scheduler or configuration layer. Extract shared code only when actual callers need the same contract.
- For a new subsystem, document its inputs, outputs, state owner, cleanup and failure behavior next to the interface. Explain invariants and reasons; avoid comments that narrate the code.
- Keep experiments in a removable module or tool with explicit entry/exit points. A local revert must restore the previous path without a data migration; test the disabled path when introducing runtime integration. Do not add a second rollback coordinator or replace the existing snapshot representation without a documented failing invariant and decision.
- Avoid bulk renames, formatting and source moves in behavioral fixes. Preserve upstream comparability and keep tests with the behavior they protect.

## Calculate scope without false precision

Use 1/2/3/5/8 relative effort units: 1 bounded source check/change; 2–3 focused subsystem; 5 substantial research/integration; 8 high uncertainty requiring decomposition before implementation. These are not hours, tokens or model calls. Discovery may expand scope.

When splitting a coarse task, replace its entry with new uniquely numbered child tasks and rewire every downstream dependency to the required children. Retire the parent ID in the evidence/handoff with its old scope and replacement IDs; do not reuse it. Do not count parent effort alongside children. Preserve completed task history and never renumber unrelated work.

`python tools/check_project_docs.py` computes counts, effort and ready work. Weighted closed scope is `done effort / total effort`, not probability of success or a schedule. Critical research gates matter more than percentages. Explain re-estimation in evidence.

Use Astra for difficult state ownership, determinism and architecture; keep routine packets compact. Use the configured model unless explicitly changed. Parallelize disjoint investigations, avoid duplicate writers and whole-repo rereads. Repeat passing suites only for new risk.

Record actual model/effort, elapsed time and token usage only when tools expose them; unknown stays unknown. Forecast from measured comparable packets. If applicable, API token cost is `(uncached input * input rate + cached input * cache rate + output * output rate) / 1,000,000`, plus applicable tool/cache-write costs. Verify current rates/surface first; effort units do not predict spend. No paid API budget is authorized.

This approach follows [official Astra guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra), consulted 2026-10-18: concise reusable context, useful boundaries, and avoiding redundant work. Task sizes are project conventions, not vendor guarantees.

## Authorization

Owner permits implementation, tests, commits, pushes to the fork and draft PRs. Merges/releases/paid resources/destructive history stay explicit. Verify PR base/remotes; do not target upstream accidentally. Put durable findings in evidence/ledger, not duplicate transcripts. This workflow does not schedule continuous execution.
