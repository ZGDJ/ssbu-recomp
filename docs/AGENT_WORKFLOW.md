# Autonomous work and Astra sizing

Start with [AGENTS.md](../AGENTS.md) and [ledger](../milestones/README.md); load only relevant requirements, ADRs and source. These conventions serve GPT-6 Astra and other agents; they do not configure an API/model.

Read the short [rollback handoff](ROLLBACK_HANDOFF.md) for current continuation context, then the selected ledger entry and only its relevant validation/evidence sections. Recheck the worktree and ownership. Archived checkpoints and upstream guides are historical context, not current task instructions; do not load their full history by default. Update the current summary in place at handoff, putting detailed results in evidence rather than appending another chronological continuation.

## Adopted upstream and gates

Work from OpenSmash upstream `c7c874977ea7510c291ec8c278a58883a2f4e368` and [ADR-0007](../adr/0007-opensmash-adoption-and-hardening.md). Inspect the existing `r1_*` / `rb_*` implementation before proposing replacements. M7.1–M7.8 are bounded source-hardening tasks; completing them does not close private-data, gameplay or full-roster M1–M6 gates. Use root [BUILDING.md](../BUILDING.md), not the former WindowSmash build commands or evidence.

## Outcome-first work selection

Advance the next falsifiable battle proof. Useful progress is a verified fix, a causal finding, a narrowed divergence, or an enabled gameplay experiment. Every implementation/investigation packet names (a) a reproduced failure or concrete source invariant violation, or (b) the next gameplay gate it enables, plus the smallest observation that would change the decision and a stopping condition. Start with existing tools; when a new probe is needed, explain the missing observation and implement the smallest tool that supplies it.

Prioritize the ledger's proof-first queue. M7 safety fixes remain mandatory; dependency-ready battle prerequisites and early M6.1 fixture work must not be starved behind expanding resource cleanup. Reuse completed M1 identity/cache/hook/baseline acceptance rather than reopening it without new evidence. Bounded research may run before a downstream capability gate is dependency-ready under an explicit investigation task; it cannot close that gate. Keep forward-determinism research separate from snapshot-resource acceptance.

After each cohesive runtime change, perform its required validation, then attempt the named next proof or record the exact prerequisite preventing it. Choose each probe to distinguish specific hypotheses; use its result to select the next experiment. Conclude the packet when its question is answered. If it supplies no discriminating evidence, revise the hypothesis/observation or report the remaining uncertainty. Select subsequent work against the proof-first queue. Preserve failed attempts and establish their causes separately; successful retries never diagnose prior failures.

Defer optional diagnostic polish, unused configuration modes, public lobby improvements, generic transport abstractions and broader framework work unless they meet the same defect/proof test. A known optional unsafe mode may be deferred only with an explicit restriction and evidence that supported/default paths do not use it; otherwise its safety issue remains blocking. Deferral never means silently ignoring a reachable corruption bug or weakening acceptance.

Validation is risk-based: keep mandatory fatal/trace/reference gates and frozen identity. For core capture/restore/resource changes, retain the full required control matrix. For an isolated diagnostic, use reviewed disabled/enabled controls plus affected source regressions unless shared-path changes justify broader coverage. State selected/omitted controls and why; do not rerun an unchanged matrix without new risk. These rules do not retroactively qualify failed or unrun SDK controls.

Deliver the change or finding, decisive evidence, earliest remaining divergence/refusal, evidence limits, and next action. Explain which gameplay outcome the result advances. A negative experiment is useful when it eliminates a hypothesis or identifies a prerequisite; capability completion still requires its acceptance evidence. Helper-test counts and effort totals describe scope, not rollback correctness.

## Let the engineering decision select the experiment

Start from the inherited implementation and an explicit requirement. Trace the relevant state owner, callers and lifecycle; identify a concrete violated invariant or the bounded uncertainty preventing a correction. Source inspection can establish a path-specific defect. Execution establishes whether the integrated correction preserves intended behavior and whether restore/replay matches an uninterrupted battle.

For each proposed observation, name the decision and the actions supported by its likely outcomes. Give priority to observations that select a correction boundary, distinguish an incorrect fix, or enable the next gameplay verdict. When outcomes lead to the same supported correction and validation plan, proceed with that plan using existing evidence. A prepared observer remains an available instrument; its existence alone does not set task priority. Bound consumer searches to what can change ownership or semantic conclusions, and stop when the correction and its falsification test are supported.

A reproduced invariant violation can justify a bounded correction before every historical failure is attributed. Establish the intended ownership and semantics, validate the correction against the specific violation, and retain unexplained failures separately. Keep acceptance dependencies and original reference obligations intact; incomplete attribution is not permission to force agreement.

After required validation, exercise the relevant capture, restore, correction or initialization behavior, or identify the exact safety prerequisite preventing that experiment. Conclude with evidence supporting the implementation, a bounded remediation, or architecture reconsideration. An inconclusive result names the remaining uncertainty and the observation that can resolve it. An investigation verdict does not close an unmet capability gate.

Choose complementary delegated roles for the task: disjoint implementations, ownership investigation, or independent challenge/review as appropriate. Integration owns shared edits, frozen candidates and serialized game trials. Task-specific experiment plans belong in the owning ledger entry and linked evidence; see the current handoff for active initialization work.

## Work loop

1. Inspect the worktree; select unclaimed dependency-ready work. Independent source tasks can proceed around private-data blockers.
2. Claim with owner/session and UTC timestamp; set `in_progress` and next action. Claims coordinate, not lock. Coordinate before taking active/stale claims.
3. Define a falsifiable investigation or cohesive implementation. Investigate unknown ownership before coding assumptions.
4. Implement, run affected checks, inspect the diff, record evidence. Fix introduced regressions; keep baseline failures visible.
5. Independently review high-risk continuation/state/scheduling work.
6. Done requires acceptance evidence and completed dependencies. Negative research can finish an investigation, not a capability gate: create remediation and rewire dependencies.
7. Record the brief retrospective described below, then continue with the next evidence-supported action within authorized scope, or hand off the exact blocker and an experiment or prerequisite that can resolve it. Recurring execution requires separate user instruction.

## Improving the method

At packet close, briefly record observed friction, supporting evidence and one proposed improvement, or `none`. Use existing timestamps/logs for observed build, trial and review waits when useful; distinguish elapsed wall time from summed parallel work. Label estimates as estimates and leave unavailable measurements unknown. A retrospective is a small learning note, not a requirement to find another task.

Agents may implement bounded tooling and workflow improvements within existing authorization. State the repeated cost or concrete friction, the next proof it helps, expected benefit, and a check of both the improvement and preserved evidence quality. Reuse existing tools first; add timing automation only when a recurring decision needs data the current logs cannot supply. Use the existing task structure for substantial work; routine improvements need no separate process lane or mandatory ADR.

Preserve correctness and evidence obligations: required state restoration and gameplay semantics, fatal/reference/trace-completeness gates, frozen candidate identity, retained failures, and acceptance dependencies. Execution mechanisms such as batching, control organization, low-risk review scope and document layout may evolve when their replacement preserves the required coverage, isolation and failure detection. Map each affected old obligation to its replacement and record remaining limitations; saved time alone is not acceptance. Current required controls remain in force until the replacement is validated and documented. Changes affecting high-risk state/scheduling evidence receive independent review; integration owns adoption and the final verdict. Architecture or substantial acceptance-method changes receive a durable decision record, with an ADR for architectural reconsideration.

Early bounded profiling may inform an architecture decision before formal performance qualification. Name the decision, candidate, measured components and omitted work, using safe existing experiment paths. Fast incomplete replay does not prove feasibility; slow instrumented replay does not by itself disprove it. Retain M4.3 representative-scene and tail-latency acceptance.

Keep validation principles and applicable gates easy to find. Move historical test detail to linked evidence when it obstructs navigation, preserving required procedures, coverage and evidence links. Organize documents when useful rather than pruning at every handoff.

## Packet template

```text
Task/outcome: Mx.y / one sentence
Proof/defect: named gameplay gate or concrete violated invariant
Decision: correction/validation choice; likely observation outcomes and resulting actions
Context: requirement, ADR, source symbols, relevant prior evidence
Ownership: exact files/subsystem; other active writers
Scope: included work and explicit deferred work
Approach: bounded experiment/implementation
Acceptance: observable result + command/manual procedure
Artifacts: code/tests + evidence + ledger update
Split/stop: falsifiable stop condition; missing prerequisite, architecture decision, excessive scope
Validation scope: required controls and justified omissions; reusable existing tools
Handoff: change/finding, decisive evidence, uncertainty, next action
Retro: observed friction, supporting evidence, proposed improvement or none
```

## Shared-work integration checkpoint

For stateful runtime changes, assign exclusive file ownership and agree on function signatures before parallel edits. The integration owner alone launches the game and owns shared caller wiring. A reviewer stays read-only until assigned a separate edit scope. Freeze the candidate tree before building or testing it. Independent investigation and disjoint source tests may continue outside that candidate; one integration owner does not require one worker for all tasks. Separate worktrees do not inherit uncommitted changes, and shared-machine game trials remain serialized.

Before building, each writer reports its frozen file list, interface contract, tests performed and remaining limitations. The reviewer acknowledges that exact candidate. Later source edits invalidate the corresponding runtime manifest: rebuild before claiming game evidence applies. Verify normalized source hashes against the manifest after the final trial. A helper test proves its policy, not the integrated runtime lifecycle.

Use a sequential, fail-fast trial batch with fresh userdata and distinct executable identity. Run the default control first, then boundary refusals and recovery. Stop if the default cannot produce mandatory replay; preserve that failed control and investigate instead of weakening the comparator. Record process exit, sealed trace comparison, injected refusal reason, history observations and binary identity separately. A process exit alone is never a pass.

Run `python tools/check_runtime_trial.py TRIAL` after each stopped rollback trial and before its trace/observer comparisons. A native fatal can race normal shutdown and leave exit zero; any fatal-log diagnostic still fails the control. Preserve the original result and gate report. Do not treat a later successful retry as a diagnosis of the failed run.

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
