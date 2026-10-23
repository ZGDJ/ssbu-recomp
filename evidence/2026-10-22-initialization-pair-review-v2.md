# Independent initialization pair review v2

Date: 2026-10-22. Independent second review; not a continuation or replacement of the [first review](2026-10-22-initialization-pair-review.md). Branch `feat/rollback-validation-audit`, HEAD/base `11287ff8598c37db8561ff291cb7e85e446942ed`. Ownership: this report and ignored `artifacts/local/initialization-pair-review-v2-20261022/` only. No implementation edits, builds, game launches, resource samples, cache preparation or commits.

## Verdict

**Accept the frozen v2 source remediation within the tested scope. No blocking finding remains from round one.** This accepts the pair tooling and the local offline native-admission correction as source tooling, not an actual successful initialization pair, launch authorization, M3.5 completion or rollback qualification. Retained capacity refusals remain binding. Real-input preparation and all new-candidate gameplay controls remain unrun.

The four v2 tool/test SHA256 values in the final versioned section of [tooling evidence](2026-10-22-initialization-pair-tooling.md) match. All eleven entries of `artifacts/local/offline-initialization-next-20261022/helper-freeze.json` match. Repository `scripts/run.py`, `scripts/battle_identity.py`, `tools/check_runtime_trial.py` and `tests/bounded_trace_cmp.py` have no changes against HEAD. The earlier report and every existing file in its review-artifact directory were hashed before testing and verified unchanged afterward.

## Findings resolved

1. **Rules/application:** the plan now declares every negotiated field plus explicit applied fighter kinds, stage ID and stock count. The gate compares both peers to those declarations, rejects the exact production unapplied-rule and missing-panel diagnostics, requires eight ordered player readbacks with two human players and six inactive slots, and checks ready-go fighter/stage/rule readbacks. Inspected the actual formatting and writes in `runtime/rb_net.c:267` and `runtime/debug_mode.c:97`, `:474`, `:482`, `:541`; these are existing production readbacks, not invented test-only messages. Independently resealed wrong stock, applied item and colour mutations fail. Full controls-layout payload and stage-history contents remain outside the readback claim.
2. **Admitted distinct attempt:** exclusive UUID attempt and completion records bind plan, admission samples, commands, identities, logs, traces, results and inventory rechecks. Completion checks require both roles, distinct positive PIDs, ordered finite lifecycle observations, zero exits, closed outputs and exact output hashes. Missing admission, stale join timestamps and unresealed same-role output substitution fail. The original-reference result is computed independently of rule, fatal, identity and completion failures. A manifest is consistency evidence, not protection against an actor rewriting and resealing the entire packet.
3. **Offline native freshness:** copied `run.py` completes identity capture before `native_admission.run_admitted` takes its two new samples. Metadata is compared after admission, followed by freshness validation at the native `subprocess.run` boundary. Receipt validation is required by `run_trial.py`; INIT_ONLY and all offline capture guards are explicitly zero. The five integrated tests execute copied `main()` with disposable identity inputs and mocked clock/sample/native boundaries. Slow identity completes before fresh sampling; stale samples, slow metadata, changed metadata and low commit prevent native invocation. The successful case also passes the unchanged forward-only gate. The superseded seven exact-block tests were not counted or rerun; retained extension failures were not rewritten.
4. **Original minor objections:** each pair `Popen` has a fresh admission check immediately before and after creation; slow host creation and expiry before join fail with owned cleanup. Both pair `taskkill` calls now have ten-second timeouts and subsequent waits are bounded at thirty seconds. Partial startup and cleanup failures remain failed completion records. No real process was killed during this review.

## Identity/import and preservation checks

A separate fresh Python process imported the copied launcher without calling `main()`, then confirmed that `battle_identity` and `native_admission` resolve to the local copied scripts while `setup` resolves to the original repository helper. The copied identity implementation is byte-equivalent to the repository implementation and identifies its adjacent copied `run.py` through `__file__`; its identity-tool hash identifies the copied file itself. The copied launcher's only substantive changes are repository dependency/path selection and the admitted native call with output closure.

Source inspection confirms that `run_trial.py` records the copied launcher command and `verify_inputs.py` gives the same local identity directory import precedence. Its post-run comparison removes only the identity digest and mutable initial userdata; other identity fields remain compared. Full post-run verification is a separate required helper invocation, not automatically executed by `run_trial.py`. This review did not execute that real-input wrapper or post-run workflow. Its reconstructed environment must still match the concrete launcher environment; implicit ROMFS/Opus fallback branches were not exercised by the five tests. Any mismatch fails the full identity comparison rather than relaxing it.

The offline wrapper still preserves fatal and reference gates as required success conditions. It stops its reference subprocess after a failed fatal gate, so it does not promise a separate reference verdict for that offline failure path. The pair gate does preserve independent readable reference outcomes on other errors; this was explicitly exercised. Observation-adapter success cannot override either wrapper's failed acceptance gates.

Both pair observer modes retain sealed 500R/0S and original-reference/peer comparison. Observer-on additionally requires complete origin/reset/early endpoint associations and matching observations; observer-off still requires traces and rejects emitted probe records. Endpoint parsing and existing replay gates were not weakened. Non-atomic samples and selected fields do not establish complete-state equality or executed-store attribution.

## Executed validation

Configured unoptimized `deps/python/Scripts/python.exe`, with `-B` to avoid new bytecode artifacts:

- `-m unittest discover -s tests -p test_initialization_pair.py -v`: 26 passed.
- `-m unittest discover -s tests -p test_runtime_trial.py -v`: 25 passed.
- `-m unittest discover -s tests -p test_battle_identity.py -v`: 16 passed.
- `-m unittest discover -s tests -p test_bounded_trace_cmp.py -v`: 7 passed.
- `artifacts/local/offline-initialization-next-20261022/test_native_admission.py`: 5 passed.

**79 tests passed.** Native process creation, capacity sampling and taskkill boundaries are mocked. Identity tests hash disposable fixtures; printed launcher messages are synthetic. Pair launch tests exercise the actual completion writer and gate with mocked processes and real temporary output hashing, including cleanup failures. No compile/build suite was run.

Additional independent fixture mutations: one successful control and ten expected refusals (unapplied rule, missing panel, symmetric wrong rules, wrong applied items, wrong applied colour, zero-exit fatal, changed identity, missing admission, stale join and same-role log substitution). Both peers retain `original_reference: passed` in each of these otherwise failing packets. Resealing rule/fatal/identity mutations isolates semantic checks from output-hash rejection. Missing/stale/substituted evidence is checked without resealing away the inconsistency. Full reports are retained in `independent-mutations.json`; suite logs, test summaries, import paths, frozen-hash checks and historical before-hashes are alongside it in the exclusive v2 artifact directory.

## Unrun limits and next boundary

No actual private-input preparation, cache copies, full real-input rehash, native startup, host/join exchange, ready-go application, native termination or loaded-module behavior was tested. Metadata screens rely on exclusive input ownership and do not prove absence of transient change-and-restore. Pair start timestamps bracket `Popen`; termination times record successful wait observations, not kernel event times. A slow native creation may already have started a process before the post-return check rejects it. The checks do not establish simultaneous gameplay or OS-level attestation.

The next integration boundary remains a separately reviewed concrete plan and real-input preparation, with the unchanged disabled original-reference control and fresh capacity admission before any authorized game. This review grants no launch permission. Same-history pair, history contrast, second seed and observer-off repetitions remain unrun. Formal M2/M3/M4/M5 and M7 prerequisites remain unchanged.

Retrospective: independent resealed mutations distinguish rule/fatal validation from merely detecting changed file hashes. The native-path tests now reach the boundary missed by the original exact-block tests; keep that distinction explicit in future acceptance claims.
