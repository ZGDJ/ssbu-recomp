# Independent initialization pair review — request changes

Review date: 2026-10-22. Reviewer owns only this report and ignored `artifacts/local/initialization-pair-review-20261022/`. Reviewed branch `feat/rollback-validation-audit`, HEAD `11287ff8598c37db8561ff291cb7e85e446942ed`. Runtime and implementation files were read-only. No builds, game launches, resource resampling or commits occurred. Single and paired capacity refusals remain binding.

## Verdict

**Request changes before source approval or real-input launch preparation.** The observer-off trace correction is verified. The pair launcher's full pre-admission rehash, metadata screen and full post-run rehash are materially correct improvements within their explicitly limited inventory scope. They do not close the following independently reproduced or source-established objections. Root integrates fixes and requests a new independent round; this round stops here.

All four raw tool/test hashes exactly match `2026-10-22-initialization-pair-tooling.md`. All seven local helper hashes match `helper-freeze.json`; all six Python helper copies compile syntactically. The runtime package/source acceptance from the prior round is not reopened or promoted to gameplay acceptance.

## Blocking findings

### 1. P1 — agreed match text is accepted even when production says it was not applied

Locations: `tools/check_initialization_pair.py:180-188`, `tools/run_initialization_pair.py:28-71`; production `runtime/debug_mode.c:474-482`.

The gate compares the two negotiated match strings and checks the seed, but never requires declared expected fighters/stage/rules or compares parsed rules against that declaration. DEBUG_MATCH/DEBUG_END are optional plan fields. More seriously, production explicitly logs an unapplied rule kind or an unavailable player panel, and neither diagnostic is rejected. Handshake agreement precedes these writes; its acknowledgement is not evidence of successful application.

Reproduction: run `deps/python/Scripts/python.exe artifacts/local/initialization-pair-review-20261022/reproduce.py`. Starting from the supplied successful synthetic fixture, append either exact production diagnostic to the join log:

- `[rbnet] handshake: player 2: rule kind 1 here, 0 agreed (not changed: set the same rules on both)`
- `[rbnet] handshake: player 2 has NO panel on this game's select screen and player 1's state was not read: this match will not be the agreed one`

Both return `passed`. Changing both peers from `stocks 1` to `stocks 99` and `hazards 0` to `hazards 1` also returns `passed`, with unchanged reference traces. These are artifact-level counterexamples, not claims that a real 500-frame run with these conditions has occurred. Identical short fighter traces do not prove rule semantics.

Smallest fix: require explicit expected negotiated match fields in the reviewed plan, parse and compare them for both peers, and reject the production application-failure diagnostics. Require the appropriate existing runtime rule/application readback where available. Add symmetric wrong-rule, unapplied-rule and missing-panel negatives. Preserve seed/reference/endpoint checks independently.

### 2. P1 — standalone gate does not bind successful evidence to an admitted run

Locations: `tools/check_initialization_pair.py:130-225`; `tools/run_initialization_pair.py:195-241`.

`inspect_pair` never reads `admission.json`. The supplied success fixture contains no admission evidence and nevertheless passes; the independent `missing_admission` reproduction confirms this. It also accepts `result.json` containing only `exit: 0`. Command/identity fingerprints bind input descriptions, but no launcher completion record binds the game log, trace, result, process lifetime and admission to that particular attempt. Same-role logs/traces from a different attempt with the same seed/match can be substituted without altering the validated command/identity/recheck files. Match ID is derived only from seed, so it cannot identify the attempt. Runtime nonce text is not cross-bound by this gate.

Production `launch` does perform admission, so this is not a claim that its ordinary path skips sampling. It is a fail-open artifact-consistency gate and stale/substituted-evidence gap under the requested threat checklist.

Smallest fix: retain an exclusive per-attempt launcher completion manifest binding plan/attempt identity, admission sample digest, each actual process start/end and exit, and hashes of each closed output. Validate it in the gate, including paired budgets, interval, freshness at each recorded start, and required output membership. Missing/stale admission and same-role prior-attempt output substitution must fail. This provides accidental-substitution consistency, not cryptographic or loaded-process attestation. Preserve independent readable original-reference verdicts on other failures.

### 3. P1 — adapted offline helper freshness guard is upstream of the expensive identity capture

Locations: local `run_trial.py:41-44`; `scripts/run.py:203-214`; `scripts/battle_identity.py:capture`.

The new helper correctly checks both resource samples, thresholds, interval, drift and age, then checks age again immediately before starting **Python `scripts/run.py`**. That child performs `battle_identity.write/capture` over source, binaries, modules, content and other inputs before its native `subprocess.run`. There is no freshness check between that full hashing operation and the game process. A capture lasting more than the remaining five-second window, or an intervening pause, therefore permits a stale native launch. Syntax/exact-block tests cannot establish end-to-end freshness. The pair launcher corrected this ordering; the offline helper still has it.

Smallest fix: use a reviewed offline launch path that completes heavy identity/preparation work before obtaining admission, checks unchanged metadata afterward, and checks freshness at the actual native process boundary. Retain full post-run verification and explicit INIT_ONLY=0. Add an offline test with a mocked slow identity operation proving no native process starts after expiry. Do not execute these helpers against real games until that ordering is corrected.

## Other reviewed boundaries and limits

- Source tracing confirms `host:<port>` and `join:127.0.0.1:<port>` select real host/join modes; loopback controls socket binding, STUN/UPNP are explicitly off. Host lobby and client sockets are distinct runtime roles; equal configured room port is not itself a collision defect. Actual socket establishment remains unrun. Config-file fallbacks still need review in the eventual concrete plan.
- Handshake grammar/order matches production `rb_net.c`: successful first-round agreement, match print, then INIT_ONLY acknowledgement. The runtime synchronizes seed and applies stage/history/global RNG before original construction; no source-level capture/replay enablement was introduced here.
- Both observer modes require sealed 500R/0S, original-reference and peer comparison. Divergence and incomplete traces fail independently. Instrumented endpoint parsing checks ordered raw folds and constructor/owner/later-reset associations, but remains non-atomic and does not prove selected-branch or complete-state equality.
- Pair tests exercise fatal zero exit, missing/failed peers, incomplete observations, metadata mutation, post-run mutation and partial-launch cleanup. Owned cleanup targets retained PIDs, not all games. However `taskkill` subprocess calls have no timeout, so the stated bounded cleanup claim is stronger than implementation; add a timeout and preserve failures before relying on that claim. No real process was killed in review.
- Metadata is explicitly a screen, not recursive content attestation. Exclusive input ownership remains necessary. The final pair freshness check is before the host/join launch loop; check each start if the first launch is delayed.
- Local helpers correctly select the current handshake-isolation package and explicitly set INIT_ONLY=0. Their analysis reports still do not enforce original-reference conjunction themselves; root must require successful wrapper reference/fatal/completeness gates, post-input verification and explicit cross-arm input comparison. No caches/builds were prepared, and no helper's real-input preparation was exercised.

## Validation and retained artifacts

Offline suites: 18 pair tests, 25 runtime-trial tests, 16 battle-identity tests and 7 bounded-trace tests passed (66 total). Identity tests mock process boundaries; their launcher messages are synthetic. An initial typo used `test_check_runtime_trial.py` and discovered zero tests; the correct `test_runtime_trial.py` was then run. Independent mutation results and frozen hashes are retained in `artifacts/local/initialization-pair-review-20261022/reproductions.json`; the reproduction script is alongside it.

Documentation validation and whitespace checks passed after writing this report. The first documentation check exposed a Windows default-encoding issue in this new report; it was converted to UTF-8 and checked again. Historical failures, references, runtime package, helper freeze and other owners' work remain untouched. No source acceptance, real-input preparation, successful host/join initialization or rollback qualification follows from these tests.

Retrospective: the fixture covered agreement text and input identities well but omitted production application-failure diagnostics and attempt/admission binding. Add those small negative cases and test freshness at native process creation, not just the helper's subprocess boundary.
