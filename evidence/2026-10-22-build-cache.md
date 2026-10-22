# M1.4: content-authorized lifted compiler reuse

Date: 2026-10-22. Source acceptance complete; no gameplay qualification follows from source tests.

## Defect, proof and stopping criterion

`tools/lifter/build.py:cmd_compile` accepted a timestamp-new object before checking source/header/config content and could adopt an object with no successful-build record. Its content key omitted compiler bytes. Disposable pre-fix regressions preserve six failures in `artifacts/local/m14-cache-validation/prefix-tests.txt`: preserved-timestamp source/header/compiler/config changes, adoption of an unknown object, and failed compilation leaving a partial object subsequently reused.

The supported optimized main path replaces the compile callback; NRO compilation has a separate timestamp-only scheduler, also replaced by `build_opt` for optimized modules. Game-data objects and DLL linking sit downstream. Acceptance therefore exercises these paths with their actual effective settings, rather than assuming the main-loop fix covers them.

Decisive validation: source/header/compiler/config changes must rebuild despite timestamps; unchanged content must reuse; failed or interrupted work must lack reusable success records; separate build directories must remain isolated. Reuse `_srchash.json` and existing optimized hints/fallbacks. Stop at affected tests and independent review; do not expand this into a general provenance framework.

## Next gameplay packet

M1.2 requires three consecutive complete identified 13.0.5 fixture matches with KO, respawn and return to menu. Prepare a separate runtime package and deployment under ignored `artifacts/local`, preserving the normal executable, game DLL, dependencies, installed saves, historical package and M1.1 mismatch report. A new forward-only walk-off tape adapts the existing imported-save navigation and results waiters. The first bounded attempt stops on a stalled waiter, fatal failure, or observed natural match/menu completion before considering repetition.

Explicitly disable run-ahead, offline rollback simulation, network rollback and learned tracking. This experiment does not exercise capture/restore and is not blocked by all M7 work. The existing SDK reference failures and unrun restore controls, protection=177 refusal, M7.1 initial-base ordering and M3.5 RNG attribution remain unchanged.

Copied historical game/module binaries are identified inputs, not proof of a fresh reproducible compilation. The debug match parser does not apply its parsed `time` setting and does not establish every rules toggle; actual rules need verification. The existing rollback trial gate requires `r1.log`, absent with capture disabled: preserve its refusal, never fabricate that log or weaken the gate. These limits must be reported separately from any observed match progress.

## Implemented cache and validation

The existing per-object-directory `_srchash.json` now authorizes reuse by content instead of timestamps. Missing/legacy records rebuild conservatively. Keys bind source, supported local/generated/platform/nocrt headers, compiler executable bytes and actual compiler flags/policy. Optimized wrappers supply their effective configuration; fallback/hint identity also changes with compiler/header/policy inputs. Pending records are invalidated before compilation, and unsuccessful output is not published as reusable. Game-data, module shim and included EH/R1 shim C dependencies use the same mechanism. DLL keys include object contents and link inputs; failed links retry. Nocrt auxiliaries live beside each build's response file, preventing cross-directory sharing.

Independent review reproduced two additional defects during integration: included shim C changes were initially missed, and diagnostic `build_opt.py one` could overwrite a main object while its old success record remained valid. Both were fixed with regressions. `one` now invalidates the record in its actual output directory before compilation and propagates failure status.

Validation: `python tests/test_build_cache.py` passed **58 tests** independently; a final additional production `build_game_dll` content/reuse/failure regression brings the author's and root integration suites to **59 passing**, with production code unchanged after review. `python tests/build_opt_sched_test.py` passed Linux, macOS and Windows scheduler fixtures independently. All tests use disposable compiler boundaries, not private game data. Logs remain in `artifacts/local/m14-cache-validation`, including original failures and intermediate results. Existing M1.1 tests also passed **16/16**. The two affected suites were added to source CI; no hosted run is claimed.

Scope: lifted main/plain/optimized, NRO/plain/optimized, game-data and their link/auxiliary cache paths. Host incremental compilation, source-generation/lifting timestamp policy and arbitrary external system SDK/include dependencies were not redesigned. The candidate host is built in a new clean scratch directory. Inputs must remain stable during a build; this is not a concurrent-writer snapshot or binary-provenance attestation. No runtime source changed in this packet, so the M7 capture/restore control matrix was not repeated or credited to it.

## Isolated candidate

A clean `deps/python/Scripts/python.exe scripts/make_release.py --build artifacts/local/runtime-m14-cache --out artifacts/local/runtime-m14-cache-dist --allow-dirty` build passed the package audit. Compiler temporary files were confined to `artifacts/local/m14-compiler-temp`. Package source digest: `412d6b36ef192cbdcb5a9e405e1de335239d11e7c1badc2bf7aa130e88f07c0a`; dirty base commit `969a238d55`. This is a local testing package, not a published release.

The deployment is `artifacts/local/m14-offline-candidate`. Main/SDK inputs, config/sysdata and historical main/module DLLs were copied from the existing build; the new runtime executable/SDL/glslang come from the new package. Content remains the supplied read-only local fixture. Trial userdata is a disposable copy. No historical manifest was changed. The first attempt `walkoff-a` failed before identity capture/game launch because the runner also expects the normal executable basename in the isolated directory. That launcher failure remains intact. Adding the same package executable under that basename only inside the isolated deployment enabled separately labeled `walkoff-b` to pass prelaunch identity capture.

Private commands, package build log, trial identity and raw logs are in `artifacts/local/m14-candidate-validation`. Protected-before records cover 37 normal-play/save/historical-package/report files. No claim is made that copying historical DLLs demonstrates compilation under the corrected cache.

## M1.2 attempt result and exact blocker

`walkoff-b` passed prelaunch inventory and launched the isolated candidate. The requested 240-second run exited **0** after **261.625 seconds** including inventory/startup/shutdown. Its actual ready-go record reports Mario/Mario, player 2 human, Final Destination stage id 3, normal form, three stocks and item appearance 0. Screenshots `fight_01500.bmp` and `fight_03300.bmp` show both fighters still holding three stocks at the left ledge, at approximately 6:41 and 6:09 remaining. These screenshot labels are diagnostic poll/presentation observations, not an authoritative tick oracle.

The sustained-left input did not produce the required KO/respawn sequence. At shutdown the tape was still on step 20, repeatedly pressing A while waiting for 38..50 draws; actual draws remained around 255. There is one fight-on record, no natural fight-off record and no demonstrated menu return. **No complete match is qualified; do not run the unchanged tape three times and call it acceptance.** The forward-only probe stops here at its bounded fixture failure.

The unmodified `tools/check_runtime_trial.py` returned **failed**, solely for absent `r1.log`, preserved in `walkoff-b/runtime-gate.json`. Snapshot paths were explicitly disabled, so no replacement log was fabricated. `forward-observations.json` separately records exit zero and zero matches for the checker's exact fatal regex in the real game log. That narrower observation does not supersede the failed gate or any historical SDK/reference failure. The old replay reference was not compared to this different forward-only input tape and was not changed.

`post-trial-validation.json` verifies all **37 protected identities unchanged**, and both normalized source digest and per-file source identities still match the new runtime manifest. No game process remains running. Normal-play executable/game DLL/glslang, installed saves, frozen RNG checkpoint package and original M1.1 refusal are preserved. Existing unrelated uncommitted edits were not reverted or included in a new commit.

Next decisive gameplay gate: adapt the concrete tape to actually cross the blast zone (for example, verified jump-plus-direction after ready-go), observe KO and respawn, then natural last-stock end and results/menu return. Verify every fixture rule through actual readback/screens, including the timer and currently uncovered toggles. Before formal M1.2 completion, produce the main/module DLLs under the corrected cache in a separate build and retain their build evidence, then require three consecutive complete identified matches. The forward-only fatal-gate layout mismatch needs an explicitly reviewed solution without weakening existing rollback/reference gates. None of these blockers is blanket M7 hardening; RNG attribution stays M3.5, resource closeout M7.8, and initial-base ordering M7.1.

Final source/document checks: 59 integration cache tests, all three scheduler targets, 16 identity regressions, project-document validator and diff whitespace checks pass. These establish the bounded M1.4 acceptance, not gameplay or complete compiler/system dependency provenance.
