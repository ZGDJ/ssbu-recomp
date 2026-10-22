# Proof-first execution audit

Date: 2026-10-22. Planning audit of the current ledger, workflow, handoff, SDK memory evidence and synchronous RNG checkpoint evidence. HEAD remains `969a238d553ff600679c15ce7ddef5f977d21113`; substantial pre-existing runtime/test work is uncommitted. This update changes planning only and preserves active ownership. Independent read-only review agreed with the three findings below. No game trials or runtime fixes are claimed.

## Findings and changes

1. **Resource hardening had absorbed determinism research.** M7.8's current next action is RNG writer attribution, although its acceptance is snapshot resource safety. The research has real value: SDK controls fail the forward reference before the first snapshot. It should not silently expand resource acceptance. Added bounded M3.5 for causal attribution and diagnostic repeatability, and made full M3.2 qualification depend on it. Current ownership is not transferred automatically; coordinate at handoff. M3.5 does not claim full deterministic replay merely because an observer emits records.
2. **Formal battle prerequisites were being starved.** M1.1 build/input identity, M1.4 cache correctness, M1.3 hook validation, M1.2 complete identified matches and early M6.1 fixtures remain necessary for M2-M4. The execution queue now prioritizes these alongside the safety chain, reusing existing manifests/tools. M1.2 no longer asks to rediscover private inputs already supplied. No dependency or acceptance gate is removed.
3. **Adjacent hardening lacked a clear stopping rule.** The workflow now requires a defect or next proof, decisive observation, stopping condition and risk-based checks for every packet. Optional diagnostics, unsupported modes, public-lobby enhancements and generic frameworks do not outrank the next gameplay proof. Known reachable safety failures cannot be deferred merely because they are inconvenient.

## Finite resource closeout to reconcile at next owner handoff

Use existing M7.8 evidence to reconcile these known outstanding items against its unchanged acceptance; do not reopen already validated helpers without new risk:

- Attribute and remedy the retained protection=177 capture refusal/coverage issue, separately from the 176-to-177 initial-base hold-ordering issue owned by M7.1. A refused run is not evidence of safe full coverage or a diagnosis of earlier failures.
- Complete SDK candidate validation after the forward-reference failure is understood/addressed: reuse control failed and both restore-refusal controls were unrun. Newer observer-only passing controls do not qualify those omitted cases automatically.
- Resolve successful reservation-release lifetime against retained snapshot ownership. Keep OS mutation/notification quiescence in M2/M4 where appropriate; cross-reference rather than assuming a resource helper proves it.
- Classify optional SSBU_MEM_KEEP reachability in the supported candidate. If required/reachable, its enumeration/readonly-zeroing/marking defects need bounded remediation. If safely excluded, record the restriction and evidence; this audit does not establish that exclusion.

Any additional discovery must specify its supported-path invariant or exact proof blocker, affected acceptance and a bounded disposition. This list is an audit of known open work, not certification that no other resource issue exists. Completion still requires the original acceptance and independent review; no arbitrary task-count cutoff excuses unsafe restoration.

## Observable outcomes that govern priority

The proof sequence is reproducible identified battle setup; controlled stepping and authoritative state inventory; 10,000-tick forward replay/reference behavior; complete restore/correction at required depths 1/2/4/8 and terminal reversals; two-PC confirmed-state agreement and bounded failure; measured catch-up/network envelope. Existing ledger dependencies own the exact ordering. Early bounded research informs these gates without claiming them complete.

Each handoff reports the earliest unresolved divergence/refusal, what observation changed the hypothesis, which gameplay outcome was enabled and the next decisive experiment. Helper test counts and relative effort remain bounded evidence, never percent rollback correctness.

## Retained value and deferred work

Keep production-connected failure tests, strict reference/fatal/trace comparators, build provenance and preserved failures. These prevent misleading success and protect real engine fixes. Core resource/restore changes retain their required full controls. Isolated opt-in diagnostics can use justified disabled/enabled and affected regression tests; unrun required controls remain unrun. Do not repeat unchanged checks without new risk or use smaller validation to mask a failed reference.

The four-member persistent lobby, two active fighters and mandatory delayed spectators remain the family-ready product. Their implementation follows baseline 1v1 correctness/connectivity; planning their boundaries now does not authorize premature UI/platform expansion. No separate paid server, general networking framework, Local Wireless integration or simultaneous multiplayer is added.

## Validation

After integration, python tools/check_project_docs.py and git diff --check passed. No capability was marked done, no original failure was removed and no active runtime claim was seized. M3.5 adds explicit accounting for already discovered research rather than attributing more progress to M7.8.
