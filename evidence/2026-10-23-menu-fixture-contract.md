# Menu fixture contract

2026-10-23 UTC, M3.5 / FSD-004, FSD-013. Root integration on `feat/rollback-validation-audit`, HEAD `11287ff8598c37db8561ff291cb7e85e446942ed`; the worktree is dirty by design and every earlier packet stays as it was. This document follows the [writer integration](2026-10-23-menu-writer-integration.md) and specifies the fixture treatment it called for. It is written entirely from retained records: no game, build or runtime source change. Packet `artifacts/local/menu-fixture-20261023/` (design brief, review briefs, reviews, `frozen-source-fixture.json`).

## What the writer result established

All 78 recurrence steps between the validated begin and confirm samples of the 91-tick menu interval are stores by original guest code on the main thread, mapped exactly to `f_7101b1a360` (36), `f_7101b1ac70` (2) and `f_71019eb330` (40) (`artifacts/local/menu-writer-20261023/mapping-summary.json` `3a68cf2b…`, `mapping-r4-comparison.json` `d10bd24b…`, `cross-arm.json` `3438552d…`, `frozen-source-r4.json` `e22cb0a4…`). Consumption is tick-locked bursts on 15 of 91 ticks with no off-thread or host-module event, and the enabled endpoints equal the disabled control. The pre-fight advance of the global xorshift128 generator is therefore a legitimate function of the menu tick history, and the preserved +60 reference failure is a tape-dependent legitimate RNG history rather than a writer, seed or reset defect.

## The contract

**An original forward reference is comparable only with a run whose pre-fight RNG identity equals the identity the reference was recorded with.** The identity consists of eight fields that every retained arm with a menu interval record already carries in `boundary-analysis.json`, from the menu wait-begin sample through the selector call that seeds the fight:

| Field | Source field | Reference `bounded-forward-500-a` |
| --- | --- | --- |
| Interval length | `menu.interval_sequence_ticks` | 91 |
| Begin vector | `vectors.begin` | `270810be,d5359241,34690e0d,fc2d6112` |
| Confirm vector | `vectors.confirm` | `c453539a,b42451fb,66af19c2,ec155499` |
| Menu-interval consumption count | recomputed xorshift128 distance begin→confirm (bound 10000) | 78 |
| Selector-before vector | `vectors.selector_before` | `e85db69b,d55f4f49,1443f6da,b29795b4` |
| Selector-after vector | `vectors.selector_after` | `d55f4f49,1443f6da,b29795b4,b77b0413` |
| Post-confirm consumption count | recomputed distance confirm→selector_before | 20 |
| Owner seed | `vectors.selector_after[3]` | `b77b0413` |

Both counts are derived from the vectors, never read from the `algebraic_distances` field; the verdict reads no reference gate and no file name. An arm without an interval record (menu observer disabled, unusable analysis, or any identity vector missing) is **not evaluable** and is never classified comparable. Identical pre-fight tick history (same tape, same step-15 wait) is the mechanism the records support for reproducing the identity; the identity itself, not the tape, is what the contract checks, because the tape is an input and the identity is what the generator actually did. The tape hash and the sampled `wait` value (90 or 150) are recorded as provenance beside each verdict.

The selector segment is part of the identity because the records show pre-fight consumption after the confirm sample that also varies with the tape: every accepted arm records confirm→selector distance 20 and owner seed `b77b0413`, the wait arm records 40 and `fa10bec7`, although the two tapes are identical after the step-15 line (the [boundary result](2026-10-23-menu-boundary-result.md) already notes this). The writer packet instrumented only the begin/confirm interval; the post-confirm segment is recorded but unattributed, so the contract reaches the seed the fight is built from without claiming to know what consumed those 20 advances.

The contract is falsified by any run whose identity equals the reference identity and whose original reference comparison fails. A non-comparable run that happens to pass does not falsify it (the contract is a necessary condition for comparability, not a sufficient one), and an unevaluable run says nothing.

## What the retained records say

Accepted (identity equal, original reference passed, controlled tape `artifacts/local/save-import-20261021/controlled-sequence.txt` `2fd61c62…`):

| Arm | Executable | Ticks (begin/confirm) | Reference |
| --- | --- | --- | --- |
| `offline-initialization-next-20261022/baseline` | `8b91dbf8…` | 1283/1374 | passed |
| `menu-consumer-20261023/disabled` | `08cf746c…` | 1254/1345 | passed |
| `menu-consumer-20261023/baseline` | `08cf746c…` | 1255/1346 | passed |
| `menu-writer-20261023/disabled` | `7e14bc76…` | 1257/1348 | passed |
| `menu-writer-20261023/enabled` | `7e14bc76…` | 1267/1358 | passed |

Five arms, three distinct frozen executables, five different absolute sequence origins, one identity (all eight fields equal, including selector vectors, post-confirm count 20 and owner seed `b77b0413`). Each row is read from that arm's `boundary-analysis.json`, `gates.json` (`reference` exit 0), `result.json` (executable hash), `command.json` (`--seq` tape) and `reference.log` (`IDENTICAL fighter telemetry: real=500`).

Rejected: `offline-initialization-next-20261022/wait`. Its tape `wait-sequence.txt` (`05307f1a…`) differs from the controlled tape in exactly one line, `90:Z` → `150:Z` at step 15. Its record carries the same begin vector, interval 151, confirm `fec6ba1d,669c9f22,2aeec16b,9acb5375`, recomputed distance 130, selector vectors ending in `fa10bec7`, post-confirm distance 40. The contract rejects it on six criteria (interval 151 ≠ 91, confirm vector differs, consumption 130 ≠ 78, selector vectors differ, post-confirm consumption 40 ≠ 20, owner seed `fa10bec7` ≠ `b77b0413`) before any gate is read; the retained gate agrees (`gates.json` `reference` exit 1, `reference.log` `FAIL: fighter telemetry differs at real frame 2`, 499 differing frames per the [boundary result](2026-10-23-menu-boundary-result.md)). The failure stays preserved and failed: it is the contract's one rejected case, not a result to be rerun, reseeded or relabeled.

Not evaluable: `offline-initialization-next-20261022/disabled-attempt2` (same tape, reference passed, `menu_disabled: true`, no vectors). It is a sixth same-tape reference pass but carries no identity fields, so the contract does not count it. `offline-initialization-next-20261022/disabled` (attempt 1) has no boundary analysis and failed its own gates; it is not a contract case.

The handoff's "five agreeing same-tape runs" is therefore the five rows above; the retained records confirm the count.

## The falsification test

`tests/test_menu_fixture_contract.py` (`deps/python/Scripts/python.exe -I -m unittest discover -s tests -p test_menu_fixture_contract.py -v`, 19 tests) reads only the 37 retained files it names by path and SHA-256, and fails if any is missing or changed. It asserts the identity constants against the baseline record, accepts the five arms by criterion, rejects the wait arm by criterion with the six reasons above, refuses to classify the probe-disabled arm, and checks that the contract's prediction agrees with each retained gate. Twelve negative mutations on in-memory copies: wait vectors with interval 91 (still rejected), baseline vectors with interval 151, one extra menu-interval advance (distance 79), all four vectors shifted by one with both distances unchanged (rejected on the vectors), the baseline's menu interval with the wait arm's selector segment (the round-1 objection: rejected on selector vectors, post-confirm count and owner seed), one extra post-confirm advance (21), an edited recorded distance (ignored, recomputed), a flipped gate result (does not change the verdict), a comparable run with a failed reference (reported as falsifying), an unreachable confirm vector, six partial-record shapes including a missing interval key and a missing selector vector (unevaluable), and tampered retained bytes (refused).

What the retained records cannot provide: a same-tape run with a different identity, or a different-tape run with the same identity. On the retained data a rule as weak as "same tape hash" would sort all seven arms identically, so the test cannot show that identity equality is sufficient for reference agreement, only that it is necessary, that every retained agreement and the one retained failure sort correctly, and that each identity field is load-bearing under mutation. That is the limit the acceptance item "repeated uninstrumented same-tape agreement" exists to narrow.

## What the contract leaves open

- It diagnoses references; it does not qualify rollback, restoration or complete-state equality, and it does not close M3.2's 10,000-tick/state-coverage gate.
- It excludes reseeding, reset suppression and hash weakening by construction: nothing in it changes the generator, the reset path, the trace format or the comparator. A reference that is not comparable is set aside, not repaired.
- Repeated uninstrumented same-tape agreement for the diagnostic interval is not yet recorded as its own acceptance item; the five rows are instrumented (menu observer on) or observer-adjacent arms from three packets.
- Both consumption counts are algebraic recurrence distances between non-atomic samples, not observed call counts; the writer packet's exact mapping makes the menu-interval count an attribution for that interval only. The 20 post-confirm advances are recorded and part of the identity but unattributed.
- Whether the step-15 wait is the only tape parameter that moves the identity is not established; the records contain one varied parameter.

## Reviews and freeze

Round 1 briefs and reviews live in the packet: `round1-brief.md` (`2709948c…`), `contract-review.md`, `readiness-review.md`; the draft freeze reviewed in round 1 is `frozen-source-fixture-r1.json` (`7de5d1e2…`, identity before remediation).

### Round 1 outcome

Contract/hypothesis reviewer: one blocking objection, fixed. The identity as drafted stopped at the confirm sample, while the retained records show a varying post-confirm segment (20 versus 40 advances, owner seed `b77b0413` versus `fa10bec7`) that the writer packet never instrumented; a run equal on the four drafted fields but different there would have been classified comparable and, on failing, reported as falsifying the wrong claim. Remediation: the identity now extends through the selector vectors, the recomputed post-confirm count and the owner seed (table above); all five accepted arms agree on the added fields and the wait arm differs on all three, so no retained verdict changed. Non-blocking notes applied: a missing interval key or selector vector is unevaluable rather than an error; the tape-path resolution is documented in the test; the sampled `wait` value is checked as provenance. The reviewer confirmed the exclusion of reseeding, reset suppression and hash weakening holds by construction for the contract and its test and by statement for future runtime work, that the interval length is a needed field (vectors fix advances, not elapsed ticks), that the test shows necessity only, and that M3.5's acceptance and M3.2 are untouched.

Readiness/validation reviewer: no blocking objection. Verified at file:line that the test opens only the 37 pinned files, that every accepted and rejected arm carries the fields the contract uses, that the wait arm is rejected by criterion, that all mutations act on deep copies, that the test passes under `-I` via discovery and directly from another directory, that the runtime digest is `2a6b83f8…` with 296 entries, that all 65 files in the writer packet's `frozen-source-r4.json` still hash as recorded and none is packet-edited, that the only files modified after the predecessor's closing state are the seven in `changed_files`, that `tools/check_project_docs.py` passes, and that ledger, handoff and continuation prompt state the same next step. Non-blocking note on the relocated-checkout failure mode applied as documentation.

After remediation: 19 tests pass both ways; `tools/check_project_docs.py` passes; the final freeze `frozen-source-fixture.json` hashes the test, this document, the other changed documents, the packet files (briefs, both reviews, scripts) and the 37 retained records, with the runtime tree digest unchanged at `2a6b83f8932df748c21a0ff0d3ce1a39b250678fb717e35f139a3dba82155f9e`. The contract is adopted as M3.5's fixture treatment. A later change gets a new freeze name.
