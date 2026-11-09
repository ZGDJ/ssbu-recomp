# ADR-0009: Unordered fighter projection for bounded loop research

- Status: proposed; independent root review/adoption required before native use
- Date: 2026-11-09
- Scope: M1.14 preparation only; no backend, FSD or capability-gate change

## Context

The two-lane witness observes HID lane consumption and correction execution. Fighter slots are assigned by first-seen BOMA; an entry value of -1 cannot associate a fighter with a lane/profile or establish that fighter's identity in another process. The existing attributed final-arm policy therefore requires an independent association before either arm. The final oracle cannot discover and retroactively declare its own mapping.

This association is unnecessary for the smaller question: after the exact mismatch/load/replay, does the **unordered pair of whole captured fighter records** equal the independently declared all-correct pair on each finalized frame 1..64? The fixture has two human Mario records. This is a useful limited selected-state observation, without player ownership or persistent cross-arm fighter identity.

## Proposed decision

Keep v1 and its association obligation intact. Add explicit analyzer v2 `comparison=unordered-selected-fighters-v1`, admitted only with an independently pinned `comparison-policy-review`. Compare a multiset of entire records per frame, including every captured raw field except ordinal/slot/entry and including the joined full 64-bit RNG value. Preserve original ordered divergences separately. Do not sort individual columns, infer a trajectory or associate the differing lane with a fighter. Compare the multiset of declared gameplay fields at wrong R11 against oracle11 for meaningful contrast; pads or hashes alone cannot establish it. Corrected S11 remains final11.

Separately admit a one-arm `loop-calibration` packet restricted to loop,0, 900 seconds and the owning fixture. Require its own policy review, safety/review prerequisites and authenticated own-package controls. Reuse the owned process, fresh admission, full identities and consumed journal. Existing BASE/PASS/END and raw/detail witnesses are the smallest necessary observer: derive actual B/P and read counts, then validate every required cadence/read/input/tail/seal join. No new runtime hook or association getter is introduced. This phase cannot launch either final arm.

A successful calibration produces a retained result bound to its subject, gates, admission, observation and completed journal. Independently accept it, then freeze the final declaration **before both** final arms. Final admission checks the calibration's mapping, subject and diagnostic identities; neither final arm fits its offsets or counts to its own output. Different observed mapping refuses rather than shifting the experiment.

Preserve full original-reference 500R/0S and 500R/exactly-two-depth-one comparisons in the owning disabled/SIM controls. For bot arms, additionally compare the original pre-loop prefix through B (at least the first three physical samples), as unordered whole telemetry rows without entry labels. Check the unchanged original menu/RNG identity and early raw folds separately. The bot oracle supplements these original controls; it never replaces the original reference. This interpretation is part of the proposed policy review, not unilateral acceptance of a weaker original-control gate.

## Obligation mapping and limits

- Lane-specific attribution and cross-arm fighter identity: excluded from the v2 research claim; retained for v1 and formal gameplay qualification.
- Physical/logical mapping and read counts: separately observed calibration, independently accepted and frozen before either final arm; rechecked exactly in both arms.
- Two-lane input/correction evidence: unchanged complete schedule, actual tape, wrong R11, load10, replay11, raw completion and final S11.
- Selected-state comparison: all 64 finalized samples, per-frame whole-record multisets; ordered divergences retained. A swap of fighters may be invisible under this claim. This does not certify individual trajectories, complete state or gameplay correctness.
- Meaningful gameplay contrast: declared gameplay-field multiset at wrong R11 versus oracle11; report input-path-only if absent. Expected equality/effect is not a launch gate.
- Original reference, safety, identity, admission, exclusion and failure-stop: preserved; bot-prefix interpretation and calibration purpose require independent review. Unknown lifetime or receipt error retains exclusion and cannot advance the journal.

## Alternatives

Implement a supported guest lane/profile-to-BOMA observer and keep attributed comparison. This remains necessary for that stronger claim; the current e=-1 path cannot supply it. Comparing discovery indices across processes without such proof would manufacture identity. Sorting each field independently could accept a pair of fighter states that never existed. Using the final oracle as calibration violates predeclaration.

## Consequences and reconsideration

The candidate removes an unnecessary association prerequisite only from a precisely narrower, reviewed research claim. No native result exists yet. Root must review this method and integrated implementation, build/control a matching package, execute calibration and accept its evidence, then freeze/control/run the final packet. A failed comparison is retained evidence. Reject this proposal or add association if the next decision requires identifying which fighter a lane/profile controls, persistent trajectories, or a formal M4 gameplay claim. Reconsider if initial-prefix/menu comparability or the source-supported cadence fails natively. M1.13, formal M4.1/M4.2 and integrated controls remain open.

Implementation and validation: [source integration evidence](../evidence/2026-11-09-loop-calibration-driver.md).
