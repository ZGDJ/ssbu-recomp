# Default replay capacity and prepared second attempt

Bounded preparation toward M4.1 on `feat/rollback-validation-audit`, starting HEAD `bce516f0aaaea70fa8f35c45d3b726e48f4fea31`. Integration owns shared edits and serialized trials. Raw packet: `artifacts/local/replay-readiness-20261025/`. [Prior adapter and refusal](2026-10-25-default-replay.md) remain retained; formal M4.1 dependencies and acceptance are unchanged.

## Decision and observation

Determine whether the unchanged terminal runtime can enter the first default ring replay with the accepted original fixture. Sufficient capacity permits a separately labeled trial with fresh post-identity admission; insufficient capacity stops before native execution. Do not lower the reserve or close user applications.

Initial read-only inspection found 5.77 GiB available commit and 11,273 MiB physical. The packet's timestamped readiness sample subsequently found **4.3119 GiB available commit and 10,072 MiB physical**, below the unchanged 10 GiB / 10,240 MiB thresholds; no game/build processes were present. This is a readiness-only observation, not a two-sample native admission or another failed game trial. No game launched and `default-attempt2/` remains absent.

The user explicitly authorized changing `C:\pagefile.sys` to 16,384 MiB initial / 32,768 MiB maximum, without an automatic restart. The process was not elevated. Windows rejected the RunAs request with **"The operation was canceled by the user."** No elevated helper ran and no requested setting was applied. Readback confirms automatic management remains enabled with no explicit pagefile settings. Allocation grew under automatic management from 5,888 MiB at inspection to 7,956 MiB at disposition; this is not application of the requested custom setting. The helper, before-state and disposition are retained. No restart was requested, and this attempt left no custom pagefile change pending activation. Applying the authorized setting still requires Windows administrator consent; after application, inspect active allocation/commit limit and restart if needed before fresh readiness checks. Authorization persists, but a canceled OS consent is not bypassed.

## Frozen preparation and independent review

`run_trial.py --plan` generated a distinct `default-attempt2` command in this packet without creating trial output or userdata. The driver, post-run verifier and menu analyzer differ from the accepted predecessor only by packet namespace/attempt label. Launcher, identity module and admission adapter are byte-identical. Runtime/package/build/reference/tape remain unchanged. At execution the driver exclusively creates the new directory and copies the original imported save.

Freeze SHA-256: `e7cb41a74b0c9ac67f747b0cc8b8568f796c73d62a853a332c16428fdf88c942`. Two parallel read-only shared-checkout Astra reviews (medium effort, default service tier, live-discovered Codex provider) accepted the prepared launch contract with no new blockers. Both verified 35 raw and 296 normalized runtime hashes. Readiness additionally verified eight package files, 271 preservation entries and 31 exact extracted production bodies. Their scope excludes the later system-change disposition and actual execution. Prior timestamp finding and its accepted correction were carried into both briefs.

The integrator independently verified the 35 raw / 296 normalized hashes. Six unchanged admission tests pass again via `deps/python/Scripts/python.exe -I -m unittest discover -s tests -p test_replay_admission.py -v`; the accepted prior 76-test result remains historical evidence. No runtime/source change warrants rebuilding or repeating the full unchanged matrix.

## Next experiment and limits

After system capacity is available, recheck frozen hashes, original package/deployed identity and process exclusion. Execute the frozen `run_trial.py` once with `deps/python/Scripts/python.exe -I`, with an outer timeout longer than its 1,020-second child timeout and cleanup. The launcher must obtain two fresh post-identity samples satisfying commit/physical reserves, bounded drift, interval and collection-to-launch freshness. A preliminary capacity sample or pagefile setting cannot replace this admission.

The accepted settings remain SIM=120,1,60; LS=1; verify=2; skip/lite=0; restore-verify=0, with unchanged offline/no-network/no-legacy settings. Require **500 real frames and exactly two depth-one replay runs**, complete seal, fatal-log gate and equality against original `bounded-forward-500-a`. Separately run `analyze_boundary.py default-attempt2` and `verify_inputs.py default-attempt2` with the same isolated Python; menu/RNG comparability and full post-run identity are mandatory even though they are outside the driver. Preserve 91 menu ticks, 78 advances, 20 post-confirm advances and seed b77b0413. Record all gates; refusal, divergence or incomplete trace stops the batch and selects the next causal investigation.

This packet adds reviewed launch preparation and capacity evidence, not a native replay pass. The unchanged terminal package's disabled control remains 500R/0S. M7 source acceptance stays distinct from complete-state/gameplay qualification. The battle path remains commit readiness -> default replay -> integrated restoration/refusal controls -> broader correction/depth and terminal coverage; formal M4.1 dependencies and wider fixtures remain mandatory.

Retrospective: checking elevation before a system mutation avoided a partial configuration change; recording OS consent failure separately prevents confusing user authorization with an applied setting. No additional tooling is needed before the prepared experiment.
