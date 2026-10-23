# Menu-boundary gameplay contrast

M3.5 / FSD-004,FSD-013, 2026-10-23 UTC. Branch `feat/rollback-validation-audit`, HEAD `11287ff8598c37db8561ff291cb7e85e446942ed`; incoming uncommitted initialization tooling preserved. Runtime/source unchanged. This completes the previously prepared menu-disabled, enabled and single +60 protocol with a discriminating observation. It does not qualify rollback or supply a production seed correction.

## Result and decision

Both baseline controls pass the original reference. The +60 arm passes fatal and sealed exactly 500R/0S but **fails the unchanged original reference at real frame 2**, with 499 differing frames. At frame 2 only captured `rng` differs in both slots: baseline/reference `9d723f07`, wait `eeaa81e9`.

The new observation is **equal global RNG at menu wait-begin, different global RNG at confirmation**. Baseline and wait begin at `270810be,d5359241,34690e0d,fc2d6112`. Baseline confirmation is `c453539a,b42451fb,66af19c2,ec155499`; wait confirmation is `fec6ba1d,669c9f22,2aeec16b,9acb5375`. Selector/owner seeds become `b77b0413` and `fa10bec7`, respectively. The original owner/reset association faithfully preserves those results; the evidence does not support a broken owner copy or reset.

Stop this contrast here. The first differing sampled endpoint is confirmation, narrowing the next question to consumption during the observed neutral interval. Non-atomic sampling, different absolute sequence origins and possible concurrent work prevent a claim that +60 alone caused all downstream differences or that a particular caller executed. No arbitrary reseed, vector repair, reset suppression, new reference or additional delay sweep follows.

## Preparation, admission and preserved refusal

Reuse [preparation evidence](2026-10-23-offline-initialization-execution.md). All three initial caches were independently rehashed before their selected launch: 74871 files each, equal to the retained preparation manifest. Current package and deployed aliases, all 11 offline helper hashes and four paired-v2 hashes matched reviewed values. Current normalized source remains `770a5d8c9979c83718a9e4be810089e8e184e3e1ec52213f4377156e8f267826`; executable remains `8b91dbf80026d0a71f952fab92623e3d86d79d7081e2a278a86ddbade01d00f8`. No rebuild was needed; dirty pre-commit provenance remains intact.

Fresh preflight at 02:26:20/36 passed single-game reserves at 12.16/12.20 GiB. The first disabled attempt completed real-input identity capture but native admission refused **649.796875 MiB absolute commit drift** over 15.779 seconds. Committed memory decreased, but the unchanged absolute guard correctly rejected it. `disabled/native-admission.json` states no native launch attempted; game log is empty. Wrapper fatal/completeness failures are consequences of admission refusal, not failed gameplay. Preserve this entire directory and the earlier low-capacity refusals.

Both Astra reviewers accepted one bounded retry with fresh saves, unchanged semantic inputs and separate `disabled-attempt2` outputs. Three copied outer wrappers each change exactly one output-directory expression; original scripts and native admission remain byte-identical. The independent reviewer verified exact deltas/hashes in `retry-wrapper-deltas.json`. Literal `disabled` remains the arm label, preserving disabled-build and menu-silence semantics, 900-second native/1020-second wrapper bounds, cleanup and all gates. Failed outputs were not moved, overwritten or relabeled.

All three actual launches passed fresh two-sample native admission after heavy identity hashing, with no existing game/build process, reserve/drift/freshness checks unchanged. Root serialized all games and sampled host pressure in `host-monitor.jsonl`. No user process was closed, threshold lowered or pagefile changed. The single-game runs did not admit a pair; observed available commit remained below the separate 20 GiB pair requirement. No paired launch/preparation occurred.

## Controls and identity

Completed runs live under `artifacts/local/offline-initialization-next-20261022/`:

- `disabled-attempt2`: native/process exit 0; 103.656-second wrapper duration; fatal, sealed 500R/0S and original reference pass; menu observer silent.
- `baseline`: native/process exit 0; 99.422 seconds; same gates pass; menu interval exactly91 ticks.
- `wait`: native/process exit 0; 98.875 seconds; fatal/sealed 500R/0S pass; original-reference gate fails frame 2, wrapper exits1; interval exactly151 ticks. Diagnostic usability does not upgrade this failure.

Each has one closed selector call, constructor/later-reset association, twelve ordered raw-early records with matching trace folds, readable same-thread owner associations, and full immutable postlaunch identity equality. Fresh initial userdata is identical: 24 files, 13393136 bytes, digest `ea7e9042a0fcce9753a0c0ee30242cee731fe9025e0e8f11dace1b462d9c2ec0`. Seed1, rules, explicit offline no-capture settings, normal speed, origin/reset/early probes and fight suffix remain fixed.

Concrete command/full-inventory comparisons show only declared differences: retry disposable paths; disabled-to-enabled MENU_PROBE plus paths; baseline-to-wait exact first `90:Z` to `150:Z` tape replacement plus paths. Initial cache content equality is separately verified; OS/driver cache equivalence is not claimed. Two comparison-only normalization assertions initially mishandled directory boundaries; corrected strict boundary comparison passed, with initial error retained. No actual command/input was altered by those assertions.

Root viewed step14/15/16/19 screenshots for all three completed arms: character selection, READY TO FIGHT, loading transition, Mario/Mario Final Destination three-stock GO. The pre-override UI shows Chrom/random CPU as in the historical fixture; actual ready-go readback is Mario/Mario human P2, end/normal, stock 3, items off and corresponding stage flags. Screenshot timing is next-present, not atomic key/scene observation.

Enabled baseline begin/confirm ticks are 1283/1374; wait 1252/1403. Step14/15/16 ordering and same-thread pre-selector association pass. Equal sampled begin vectors do not establish equal complete prehistory. Within-arm algebraic distances are 78/130 begin-to-confirm,20/40 confirm-to-selector and1/1 selector-before/after within bound 10000. These are recurrence relationships, not executed calls or simulation frames. The additional confirmation-to-selector difference also prevents assigning the entire downstream gap solely to the neutral wait.

## Independent review and next experiment

Two complementary Astra agents stayed read-only. `/root/initialization_hypothesis` challenged causal interpretation and selected a bounded next consumer observation. `/root/experiment_readiness` independently recomputed native receipt binding, fatal gates, sealed traces/reference verdicts, origin/reset/early eligibility, intervals, postidentity and allowed cross-arm changes. Both accept the bounded conclusion. Root completed the reviewer's separate screenshot obligation. Source acceptance of prior 79 tests/ten negative mutations remains separate from this new game-backed local diagnostic evidence.

Smallest proposed next observation: uniquely validate a removable hook around original helper `0x710137bc30`, active only between existing menu begin/confirm boundaries and only for entry x0 equal to actual global `0x71052391c0`. Preserve original arguments/execution; record bounded complete before/after vectors, original caller LR, x1 range descriptor, thread and sequence tick. Reject overflow, unreadable or incomplete observations; do not infer full coverage from a partial chain.

Source anchors from the bounded review: helper definition `build/work/gen_eh_o2/c_019f.c:7232`; six-element permutation `0x71014cdf90` in `c_01bb.c:11057`; its five helper return LRs are `0x71014cdfe0`, `0x71014ce00c`, `0x71014ce040`, `0x71014ce074`, `0x71014ce0a8`. Range-dependent rejection/full-width paths mean invocation counts are not advance counts. Inline/uncovered consumers exist; this is a candidate test, not presumed coverage or proof the permutation executes here.

After source validation, independent review and a new frozen build, run disabled original-reference control then one enabled original-tape baseline. No matching calls rejects this helper explanation for the interval; choose a bounded writer observation next. Calls with unexplained vector gaps imply partial coverage; investigate the first uncovered transition. A complete observed chain identifies the caller whose original purpose must be inspected; only then earn a repeat of the existing single +60 contrast to distinguish invocation frequency from range/rejection behavior. Observer/reference/prerequisite failure stops progression. Legitimate original menu consumption may require an explicit history-sensitive fixture or separately justified battle-initialization contract, not suppression or arbitrary seeding. This observer is proposed, not implemented.

## Preservation and open gates

Local integration packet: `artifacts/local/offline-trial-20261023-0226/`. It retains cache rechecks, retry deltas, command/inventory comparisons, verdicts, review summaries, pressure samples and hashes of120 closed output files. All prior references, rejected source artifacts, historical +60 frame 2/499-frame failure, reconstructed f28f3988, SDK/reference failures, empty-cache abort, disabled-b resource/zero-replay failure and protection reports remain intact. Both frozen packages and all 433 protected historical entries remain checked separately (430 original paths, three exact archived documents).

The three build caches are now used/mutable; do not treat them as pristine copies for a new experiment or rerun into existing output directories. Preparation state now records completed games and each verdict, preserving its earlier states.

M3.5 remains in progress: writer attribution and repeated uninstrumented agreement are not established. Handshake isolation and paired v2 remain source-accepted; paired real preparation, host/join, differing-history, seed and observer-off controls remain unrun. The new disabled reference control is now available within its exact identity; a future pair still needs all negotiated/applied-rule/readiness/attempt/closed-output/native-admission obligations.

M7.8 resource acceptance, reservation lifetime and supported MEM_KEEP disposition remain open; provider rejection supplied no technical result. M7.1 separately owns initial-base membership/publication and complete-or-refuse continuations. Actual restore proof still requires applicable readiness, uninterrupted battle versus save/advance/restore, 500 real frames and exactly two replay runs, then correction/refusal and depth expansion as earned. Forward-only zero replay cannot close those gates.

Retrospective: the first native refusal demonstrated that an earlier capacity pass cannot replace native-boundary sampling. A path-only retry preserved failed evidence without changing semantics. The menu observer finally discriminated the neutral interval; stop broad consumer censuses and test one executed candidate next. Final documentation/whitespace/frozen-identity checks are retained in the local packet.
