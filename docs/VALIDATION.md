# Validation contract

Distinct proof levels: **source-only**, **game-backed local**, **cross-process/cross-machine/network**. One cannot close another. The adopted upstream is OpenSmash `c7c874977ea7510c291ec8c278a58883a2f4e368`; its source and historical run reports do not count as newly reproduced gameplay evidence.

## Source checks and build prerequisites

Run the migrated project-document validator at repository root:

```powershell
python tools/check_project_docs.py
```

The upstream game-free rollback unit test documents this standalone build (a configured compatible C compiler is required):

```powershell
clang -O1 -Iruntime tests/rb_test.c runtime/rb_input.c runtime/rb_wire.c runtime/rb_timesync.c -o artifacts/local/rb_test.exe
& ./artifacts/local/rb_test.exe
```

Create the ignored `artifacts/local` directory first. A passing test covers its toy simulation, wire encoding, input queues and timing helpers; it does not execute actual battle snapshots, native continuations or terminal lifecycle. Record compiler identity and exit codes. Do not run indiscriminate discovery across upstream diagnostic scripts: inspect each script's prerequisites and side effects first.

For a real build use root upstream [BUILDING.md](../BUILDING.md), particularly the manual `scripts/setup.py` path and required private inputs. For source-behavior qualification, build the runtime under test rather than silently substituting an unrelated prebuilt runtime. Avoid automatic source updates during a pinned evidence run. Record exact commands/options and resolved build directory; it may be outside the checkout.

`tests/rbn_cmp.py`, `tests/rb_sim_cmp.py` and `tests/rbn_pair.py` are inherited diagnostics to inspect before use; required logs, environments and private game inputs are not supplied by this planning migration. Successful log comparison only proves its actual compared fields/frames. Preserve malformed, empty or insufficient comparison failures and report counts/exclusions explicitly.

No assertion is made that the former WindowSmash `source-checks.yml`, relay unit suite, `baseline_manifest.py`, `difftest.py` or `functest.py` exists or applies here. Existing upstream workflow results and any newly migrated CI certify only jobs actually run. Do not hide intermittent failures with retries, skips or `continue-on-error`; preserve the first failure and minimize it.

## Baseline identity

Before game-backed work record source commit and dirty-diff identity; toolchain and build configuration; runtime/executable hashes; game/module/content identifiers; relevant DLL/dependency identities; selected fixture/rules/control profiles/seed; and tape hashes. Capture before and verify after the stopped-build trial. An automated manifest tool needs OpenSmash-specific discovery and tests before it can certify this inventory; the WindowSmash inventory schema is not transplanted as a working tool.

Use size/SHA-256 and explicit missing roles. A declared version is not authenticated by naming it, and a source-tree digest alone does not prove which source produced an executable. Keep absolute private paths, keys, saves, dumps and generated game code out of committed evidence. Record relevant SDK/system-library versions and compare clean builds after updates. A local inventory fingerprint is distinct from M7.7's peer compatibility digest.

## Source-hardening acceptance

M7 tests must cover refused/partial restores (M7.1), speculative terminal reversal and exactly-once commit (M7.2), unavailable correction state (M7.3), missing/old/colliding epochs and bounded frames (M7.4), stalled gameplay with live heartbeats (M7.5), hidden-state divergence and desync shutdown (M7.6), incompatible peer identity (M7.7), and learned-page/allocation exhaustion (M7.8). Extract small test seams where necessary; a fake snapshot or simulated KO proves the guard's source behavior only. M1–M6 still require real battle, repeated rewind, semantic equivalence, performance, roster and network qualification.

## Evidence and closure

Use [TEMPLATE.md](../evidence/TEMPLATE.md): task/requirement, tested revision/diff identity, environment, commands/exit codes, expected/actual results, artifacts and reviewer. Game evidence also requires executable/module/content identity, fixture/rules/seed, tape hash, hardware/drivers/compiler, frames/trials and first divergence.

Before committing, identify base plus a diff hash/patch artifact; never invent a self-referential commit. Keep private raw traces under ignored `artifacts/local/`, committing sanitized summaries/hashes. State raw retention. Missing inputs mean blocked, not skipped-success. Reviewer compares acceptance with evidence; structural checks cannot certify truth.

## Oracles and failures

Inventory authoritative/excluded/reconstructible state including native continuation invariants. Use per-frame region hashes; justify exclusions and pointer normalization without hiding aliasing. Compare restores with an uninterrupted oracle and corrected predictions with an all-correct-input oracle. Preserve divergence/seed/minimized tape even if reruns pass.

For semantic changes, also compare named mechanics to the pinned upstream recomp under equivalent conditions (FSD-013). Record instrumentation/input differences and unavailable comparisons. Deterministic replay of modified behavior cannot prove preservation of the original behavior.

Apply the [rollback ownership contract](ROLLBACK_DESIGN.md): before-input frame boundaries, immutable checkpoint ownership, forced replay diagnostics (GGPO synctest only if GGPO is adopted), repeated overlapping correction, oldest-history tests and confirmation-safe terminal outcomes. Never compare hashes from different epochs or mismatched before/after-input boundaries. Callback mocks validate integration plumbing only. Record effect-policy artifacts separately from authoritative divergence.

Apply trial counts/depths from [FSD.md](FSD.md); no silent reductions or empty-fixture passes. Use event logs plus audiovisual checks as applicable. Report tails/memory, not just averages. Reopen affected tasks/dependencies when evidence invalidates assumptions. Independently review high-risk state/scheduling changes.

CI green covers only jobs run. Private 13.0.5 gameplay remains a separate gate. Never upload game data or run untrusted PRs on private-data runners.
