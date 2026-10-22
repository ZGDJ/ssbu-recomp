# Pre-match RNG boundary integration

2026-10-22, M3.5 / FSD-004,FSD-013. Branch `feat/rollback-validation-audit`, HEAD `38550dda6b0a926366cc37eec0f5c26e4776d043`. Source and documentation remain uncommitted. **Source implementation, independent frozen review and isolated package build passed. Gameplay controls were not launched because both bounded admission checks failed the declared commit reserve.** This enables the missing observation; it does not resolve forward determinism or qualify rollback.

## Question and scope

The [preceding timing pair](2026-10-22-prematch-timing.md) produced a passing baseline and a failed +60 reference control, with selector seeds b77b0413/fa10bec7. Pre-treatment timing already differed and no RNG sample existed at wait start. The smallest discriminating observation is global RNG at logical step-15 wait start and immediately before its Z confirmation, followed by existing selector/owner/reset observations. No arbitrary reseeding or gameplay correction was introduced.

Astra A exclusively implemented the removable header, strict record parser and their source fixtures; see [implementation evidence](2026-10-22-prematch-boundary-implementation.md). Root alone edited `runtime/nnhid.c` and `fighter_sdk/fighter_host.c`, integrated, froze and built; root owns all game slots and local helpers. Astra B independently audited phase attribution and bounded upstream consumers, then reviewed the frozen implementation; see [initial review](2026-10-22-prematch-boundary-review.md) and [final review](2026-10-22-prematch-boundary-final-review.md). All used live-catalog codex/gpt-6-astra, medium/default. Token usage is unavailable.

Task IDs are retained in `artifacts/local/prematch-boundary-20261022/delegation.json` and `final-review-delegation.json`. They share prefix `node:delegated-task:command%3Amcp%3A0b6e72c6-15e0-401a-91b4-7d8942475f89%3Adelegate-task%3A` with suffixes `prematch-boundary-20261022-a`, `prematch-boundary-20261022-b`, `prematch-boundary-20261022-b-final` and `prematch-boundary-20261022-b-final-2`. The first final review failed with "Selected model is at capacity. Please try a different model." It returned no technical result. One same-model retry completed with byte-specific GO. The unrelated reservation rejection was neither retried nor rephrased.

Incoming five document changes were backed up before implementation. Other installer worktrees remain untouched. HEAD did not move. Initial process/commit inspection found no game/build owner; all game slots stayed unused. The packet preserves 433 entries, including the earlier 331 protected artifacts and prior timing outputs.

## Candidate and checks

Frozen normalized source digest: `ad7389863a11b2158c97c7640fac3c4b46e9690d0ffbecc9c8c4a01d0930fa76`. All 294 source entries and seven raw review hashes match `frozen-source.json`; final reviewer independently verified these. Original current package remains unchanged at `artifacts/local/runtime-seed-coverage/package`, digest d32f7b7d9c2c92af73e9080106ce9a7f255251e38e977b7e78fa95c5ba98da08 and executable 93bc70dbe8068e0789d04bd184b22aafabf84dbedca3925765e9f475384b2a6b.

New package: `artifacts/local/runtime-prematch-boundary/package`. Executable SHA256 **`5af99bfb01f143d16c65f7d36a3fd93c779f03eb4c6c86a9651cbb1278d4f7fe`**, 2937856 bytes. Dirty source status is explicitly recorded; manifest pins compiler and package files. The isolated build compiled 55 host files (15.2 seconds reported), completed in 23.031 wrapper seconds and passed the nine-file package audit. No game DLL was rebuilt. Identical package files were deployed into separate disabled/baseline/wait builds with executable alias `ssbu_menu_boundary.exe`; `deployment.json` pins them.

The initial build used system Python and failed in `gen_sdktest.py` before compilation because Pillow was absent. Its staged directory is retained as `artifacts/local/runtime-prematch-boundary-failed-pil`, with `build-failed-pil.log` and result. The corrected invocation used the existing configured `deps/python/Scripts/python.exe` (Pillow 13.0.0), the same frozen source and fresh output paths. No dependency installation or runtime fix was needed. Commands and outcomes are in `build-result.json` / `build.log`.

Validation:

- A: 92 O1/O3 exact-header executable fixture runs and 34 parser-negative cases passed. Checked-read, LastError, prerequisites, invalid sequence/thread/interval, repeated calls and terminal unusable coverage are retained with generated units and logs.
- Root: eight exact previous/current sequence-body runs at O1/O3 and waits90/150 passed four equivalence comparisons. State/input logs are unchanged; begin-to-confirm is 91/151 ticks. Callback is stubbed here, so this does not prove observer neutrality.
- Root: affected reset, origin, seed-probe and critical-hook regression suites passed; results/logs in `regressions.json`.
- Root local adapter: valid pair and silent disabled fixture accepted; wrong interval, thread and late unusable rejected. These use explicitly synthetic inserted records on retained baseline logs; they are not gameplay evidence (`adapter-validation.json`).
- Reviewer: exact source/test reconstruction, retained C results, independent parser rerun, prior provenance, tape equivalence and unchanged combined gates passed. No blocking source objection remained.

No combined rollback analyzer, mandatory replay rule, fatal checker or strict original-reference comparator was changed. The new parser proves only record coverage. Root helpers require unoptimized Python and separate conjunction of process/fatal, exact500R/0S, original-reference, origin/reset/raw-fold, menu and frozen-identity results. Admission files must be generated immediately before each launch, not reused stale.

## No-launch results and preservation

Warm-cache preparation finished in 438.36 seconds: all 74871 files in three independent copies equal the retained warmed source inventory. Caches remain mutable during eventual play; OS/driver caches are not claimed identical. Fresh save copies are created by each trial launcher, not shared. Original tape/reference remain unchanged; only token 15 differs in the contrast (90:Z to150:Z), with holds, other 90 tokens and raw fight suffix identical.

The declared admission heuristic requires no game/build process, at least 10 GiB available commit, at least 10240MiB physical availability, and <=512MiB committed drift across two snapshots 15 seconds apart. This is conservative packet policy, not a measured peak requirement or runtime guarantee. No user app was closed, no pagefile setting changed, and the threshold was not lowered to obtain a run.

- Prebuild check at22:36:26/42 UTC: commit headroom 6947446784 /7113035776 bytes (6.47/6.62GiB), physical 10748/11007MiB, no game/build. Commit reserve failed; other checks passed.
- Fresh disabled-arm check at22:40:21/37 UTC after build: headroom 9406013440 /9418588160 bytes (8.76/8.77GiB), physical 12345/12362MiB, no game/build. Commit reserve again failed; other checks passed. No admission token was issued and no game was launched. Baseline and +60 were therefore not attempted.

These are failed admission checks, not failed or passing game controls. No new500-frame/reference/replay result exists. Preserve the prior +60 frame 2 RNG failure, disabled-b zero-replay shortfall, empty-cache startup abort, historical reference mismatches, protection original rejection/revised reports and full traces unchanged.

Postbuild verification initially caught this packet's added observer paragraph in protected `docs/VALIDATION.md`. The exact original bytes were restored; the paragraph is retained privately and the contract is documented below and in linked implementation/review evidence. Both the failed verification and revised passing report remain. `postbuild-revised-verification.json` confirms source/raw identity and all 433 protected hashes. This preserves the historical validation document instead of silently changing a pinned evidence input.

## Observer contract and next gameplay experiment

`SSBU_RNG_MENU_PROBE=1` requires the validated origin/reset/early probes and dedicated trace/hash mode. It samples step 15 logical wait start and immediately before confirmation for Z/hold 8, wait 90 or150. Begin is after logical step 14 release but before the guest receives that pad state. Begin-to-confirm91/151 is sequence ticks, not wall time or authoritative frames. The checked 16-byte read and before/after counters narrow races without atomicity. Invalid observations emit terminal unusable and are rejected by the strict record parser; interleaved lines are not repaired. Disabled calls stay silent/readless.

Once fresh headroom admission passes, reuse this exact package for **menu-disabled baseline -> enabled baseline -> enabled +60**. Root serializes runs and observes host pressure during each. All five rollback/capture switches, MEM_KEEP and Skyline remain explicitly0; fixedseed 1, rules, fresh save, warm-cache policy and post-fight inputs stay fixed. Keep origin/reset/early probes and screenshots symmetric. Stop on a failed disabled or enabled baseline, diagnose before retry; delayed mismatch remains failed diagnostic. Require fatal checks, sealed 500R/0S, ORIGINAL reference, full input identities and existing selector/owner/reset/raw-fold coverage before interpreting the added samples.

Compare begin, confirm, selector-entry/return vectors, selection inputs and owner/reset records. Different begin moves divergence earlier than treatment. Equal begin/different confirm bounds observed divergence to the sampled neutral interval subject to concurrency/perturbation. Equal begin/confirm with different selector entry moves it after confirmation. Equal observations cannot prove complete-state equality or explain historical f28f3988. Algebraic search is bounded 0..10000 advances and reports compatibility, not executed call counts. B's static 30-site census identifies possible consumers, not executed writers.

M3.5/M7.8 remain in progress; M7.1 and M2.1 dependencies remain unchanged. Reservation lifetime, MEM_KEEP disposition and separate176-to177 membership/publication issue are unresolved. No full-state restoration, gameplay qualification or causal attribution is claimed.

## Retrospective

Observed friction: the implicit system Python failed before compilation, whereas the configured project Python completed the identical candidate in23.031 seconds. Future local build invocations should resolve `build/python_path.txt` first. Preservation checking also caught an attempted edit of a pinned validation document; new observer contracts belong in new packet evidence until that input's historical role is explicitly separated. Both failed/revised reports were retained. Admission blocked games twice; preserving that prerequisite avoids repeating the prior high-pressure confound. Source/test/review time and summed parallel time are not inferred from incomplete timestamps.

Final closeout: project-document validation and whitespace checks passed. All 433 protected entries, 22 pinned tool/input files, eight package files and three deployed executable hashes reverified. No game/build process remained. Full results are in artifacts/local/prematch-boundary-20261022/final-validation.json; no game control was launched.
