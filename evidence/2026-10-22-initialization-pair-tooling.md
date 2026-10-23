# Initialization pair tooling — source-only review candidate

Scope: M3.5's identified NET_INIT_ONLY host/join experiment. Base HEAD `11287ff8598c37db8561ff291cb7e85e446942ed`, branch `feat/rollback-validation-audit`. This packet changes only three new tools, one new offline test module and this evidence. Root owns ledger/handoff, build preparation, admission decisions, all games and independent review. No builds, real game launches, runtime edits or commits were performed here. Other concurrent evidence/ledger changes belong to their owners.

The next discriminating observation remains actual successful host/join initialization: unequal selector entry narrows handshake-to-selector consumption; equal entry but different returned seed/owner narrows original selector branches/ownership; equal owner but different reset narrows reset/lifecycle. Equal observations do not establish complete-state or selector-branch equality. Fatal, identity, agreement or completeness failure stops progression. Original-reference mismatch remains failure even if peers agree.

Read together with [handshake isolation](2026-10-22-handshake-isolation.md), [independent candidate review](2026-10-22-handshake-isolation-candidate-review.md), [offline next experiment and threat checklist](2026-10-22-offline-initialization-next.md), [workflow](../docs/AGENT_WORKFLOW.md) and [validation](../docs/VALIDATION.md).

## Implementation and inherited machinery

- `tools/run_initialization_pair.py`: preparation-only by default; explicit launch requires the canonical input-plan SHA256 acknowledgement. It uses existing `battle_identity.capture`, fresh userdata and warm-cache copies, separately prepared builds, and direct bounded executable commands. It does not build or invoke the old paired launcher. Its command schema records exact argv/cwd/effective environment, plan hash, identity fingerprint, launcher bytes and initial save/cache identities. The inherited `run.py` inventory field remains present; an additional `pair_launcher` field identifies the actual launcher.
- `tools/check_initialization_pair.py`: read-only fail-closed gate. Each peer requires complete identity/command/launcher evidence, integer zero exit, readable logs without the existing fatal/hold-release pattern, exact initialization acknowledgements, a first host/join handshake with positive sent/received counters, identical negotiated match records, explicit seed and derived match ID consistency. Missing/contradictory evidence fails. Capturing/replaying activation diagnostics fail. Optional absent R1 log is permitted because capture is disabled; any present R1 log must pass fatal/readability checks.
- Every trial, including observer-off repetitions, requires the unchanged sealed trace reader's exact 500 real/zero speculative passes, original-reference comparison and peer comparison. Original-reference outcomes are computed separately before peer configuration/fatal acceptance, so those independent failures cannot suppress a readable reference verdict. No new reference is synthesized or automatically promoted.
- `tools/initialization_endpoints.py` copies the existing retained `artifacts/local/prematch-timing-20261022/analyze_observations.py` function into tracked tooling, importing the unchanged origin/reset parsers. Observer-on trials require closed/readable same-thread selector/owner/reset associations, stable later recurrence, twelve ordered raw observations and trace-fold agreement, plus cross-peer observed values. Observer-off means those three probes are zero and silent; tracing/reference obligations remain enabled.
- `check_runtime_trial --forward-only`, existing identity implementation, and rollback comparators are unchanged. No evidence is rewritten to make NET look disabled. Existing rollback replay requirements remain intact.

## Preparation, inventory and admission

Root supplies two existing isolated build roots containing the frozen deployed work files, binaries, state/config/sysdata, and any required dependencies. Their cache directories must initially be absent. Root also supplies an immutable complete userdata template and nonempty warmed cache template. Paths must be absolute and the output/build/template/package/reference/control roots must not overlap. Copies use new destinations; old attempts are never overwritten or deleted. Preparation can leave a partial new packet/cache if it fails; preserve it and select fresh paths for retry.

A passing disabled new-binary control is mandatory: unchanged forward gate, sealed 500R/0S, original reference, matching source/executable identity, MEM_KEEP and SKYLINE zero. The plan names and hash-pins the original reference rather than adopting a matching peer trace. This precondition remains unrun for the real new candidate; synthetic tests do not satisfy it.

Before any process launch, production wiring performs a full `battle_identity.capture` rehash for both peers, validates every package-manifest file, compares immutable inventories, and rehashes both fresh saves and caches. After this heavy operation it records a metadata/evidence fingerprint and obtains fresh capacity samples 15 seconds apart: at least 20 GiB commit headroom and 20480 MiB physical, at most 512 MiB committed drift, and no recognized game/build process. Admission is refused on unavailable/invalid observations. A single-game admission is never reused.

After admission, a cheap screen compares small command/identity evidence hashes and metadata of frozen source/package/module/ELF/tool paths and declared input roots. It does not walk the 75k-file cache or rehash content descendants. The final sample must remain at most five seconds old even after this screen; slow metadata checks refuse launch. The report explicitly labels this stage `metadata`, not full content verification. This inventory is **not concurrent-writer or loaded-module attestation**; root must maintain exclusive input ownership. Content descendants are fully rehashed before admission and after the run, leaving a possible transient change-and-restore window unproven.

Both owned processes have bounded waits. Failure to start the second peer triggers cleanup of only the owned first PID/tree. Timeout/nonzero/missing peer evidence cannot pass. Cleanup waits before post-run verification; cleanup errors remain failures. After runs (including partial-launch cleanup), a full identity/package rehash is mandatory. Only userdata and application cache are mutable exclusions; immutable digest removes initial_userdata and identity fingerprint, while cache is separately checked before launch. Missing/failed post-run reports fail the pair gate. Whole rechecks and cleanup are not gameplay proof.

The integration owner reported even single-game capacity now fails at 7.50/7.18 GiB commit headroom. This implementation issued no admission or launch token and did not resample resources. No games are authorized by a synthetic pass.

## Plan interface and commands

Use unoptimized configured project Python. A plan is private JSON with these required keys:

```text
output: new absolute pair evidence directory
runtime: absolute frozen runtime package
save_source: absolute complete pristine userdata template
cache_source: absolute nonempty warmed cache template
reference: absolute retained original 500R/0S fight.txt
reference_identity: battle_identity.file_id(reference)
disabled_control: absolute passing new-binary disabled trial
package_source: exact manifest tree_digest
package_executable: battle_identity.file_id(runtime/ssbu_native.exe)
save_identity: battle_identity.tree_id(save_source)
cache_identity: battle_identity.tree_id(cache_source)
exe: deployed bare executable filename, matching package bytes
seconds: integer 1..900
seed: integer 1..18446744073709551615 (both startup and explicit handshake seed)
port: integer 1024..65535
instrumented: true for origin/reset/early; false for probe-silent repetitions
peers: {host: {build: absolute path, sequence: absolute tape},
        join: {build: different absolute path, sequence: absolute tape}}
environment: explicit approved SSBU paths/rules/settings (see allowlist in validate_plan)
```

`environment` requires `SSBU_ROMFS`, `SSBU_ONLINE_LOOPBACK=1`, `SSBU_ONLINE_STUN=off`, `SSBU_ONLINE_UPNP=off`. Supply applicable absolute NRO/fonts/timezone/Opus/config paths and intended DEBUG_MATCH/DEBUG_END/VK_PREP values explicitly. Arbitrary additional controls are rejected. The launcher owns NET/INIT_ONLY, all eight zero guards, local host/join route, both seeds, tapes, observer switches and trace/log/save paths. It accepts `@fight`, rejects `@match1on`; root reviews the actual neutral local-pad fight suffix. Poll-timed tapes are not authoritative frame-input equality. Separate sequence paths permit later declared history contrasts; this tool does not automatically advance the experiment matrix.

```powershell
deps/python/Scripts/python.exe tools/run_initialization_pair.py PRIVATE_PLAN.json
# Preparation only; inspect the new packet. No launch occurs.
# For a reviewed launch, use a plan with fresh output/build cache paths:
deps/python/Scripts/python.exe tools/run_initialization_pair.py PRIVATE_LAUNCH_PLAN.json --launch --reviewed-plan CANONICAL_PLAN_SHA256
deps/python/Scripts/python.exe tools/check_initialization_pair.py PAIR_DIRECTORY --output NEW_REPORT.json
```

The digest is `battle_identity.digest(plan)` (canonical JSON), not the JSON file byte hash. Root's acknowledgement is an explicit operation guard, not proof that an independent human/agent review occurred. Output/report creation is exclusive. Preparation and launch do not share a reusable token; a prepare-only attempt is preserved and a launch attempt uses fresh output/cache paths.

## Offline verification, limits and review freeze

Configured Python passed 66 tests: 18 new pair-tool tests, 25 unchanged runtime-trial tests, 16 identity tests and 7 bounded-trace tests. Identity-test subprocess/game boundaries are mocked; their printed launcher messages are synthetic. New coverage includes full synthetic observer-on and observer-off successes; missing sections/artifacts, contradictory flags, false roles/agreement, zero messages, seeds/match IDs/match choices, failed/incomplete peers, late zero-exit fatal, truncated/speculative/reference-divergent traces, incomplete or unequal endpoints, unchanged forward-mode refusal, memory/drift/staleness refusal, immutable module/package mutation, allowed post-run save mutation, critical metadata mutation, and owned-PID cleanup after second-peer launch failure. Test fixtures use disposable temporary files. No native game/build execution occurs.

One intermediate new-test failure was a fixture collision: the admission-failure test had already created its synthetic inventory report, so exclusive production report creation correctly refused overwrite. The test now starts the launch-path check without that fixture report. No runtime evidence was affected. Initial implementation disabled tracing with observers; integration review correctly rejected that interpretation before any games. Final source requires traces/reference in both modes.

Review targets: direct launcher environment parity and declared dependencies versus `run.py`; real log grammar/order and handshake limitations; complete identity field/plan/path binding; package/source metadata coverage and transient-writer limitations; actual host-process detection coverage; failure cleanup and independent peer/report propagation; original reference retention and endpoint adapter's non-atomic restrictions. Full preparation against real private inputs, capacity sampling duration, actual launch behavior and post-run loaded behavior are **unrun**. Synthetic inventory tests mock the existing independently tested capture boundary; they do not certify real content/package preparation. Root must independently review and prepare before any game, then run disabled control, same-history pair, differing history, second seed and observer-off repetitions in the established order. No network/rollback capability is closed.

Frozen raw SHA256 values for fresh review:

```text
7b17ca882dd0f56f03899a8fd1d9f8ab2bc707653fe742142de6990fcb54bd12  tools/check_initialization_pair.py
56215ae6857c6d1d726aa2ff1191d47d2ec002467b656967b54f590888e7e0a5  tools/run_initialization_pair.py
4cffc0fdc5cb007f115d8c20ca306836ab696779f3199d4e067212f0a2ddb98b  tools/initialization_endpoints.py
6732b808d8a88198ac8a8ea598ba45d3d7348db2f7ac208129833f4696e945ba  tests/test_initialization_pair.py
```

Retrospective: importing the old pair runner would have hidden version, capture and evidence assumptions. The current identity and forward endpoint helpers supplied reusable boundaries. Integration review exposed the important distinction between observer-off and trace-off, and between full rehash and fresh resource admission. Those corrections are enforced and tested; original failed controls and root-owned documentation remain untouched.

## Remediation v2 — findings 1/2, new review candidate (2026-10-22)

This is an **implementation follow-up**, not independent acceptance. The [first independent review](2026-10-22-initialization-pair-review.md) remains REQUEST CHANGES for its exact earlier freeze. All earlier text, hashes and failed counterexamples above are retained. Reviewer-owned report, `artifacts/local/initialization-pair-review-20261022/reproduce.py` and `reproductions.json` were read but not modified or rerun with their overwriting entry point. Finding 3 remains root's separate offline-helper task. No runtime/shared-script edits, builds, real games, resource resampling or commits occurred.

### Finding 1: expected negotiation and original application readback

The plan now additionally requires two explicit dictionaries:

```text
expected_match:
  p1_chara, p1_colour, p1_controls,
  p2_chara, p2_colour, p2_controls,
  stage, form, flags, second, hazards, items, rule_kind, stocks
expected_ready:
  p1_kind, p2_kind, stage_id, rule_stock
```

All values are JSON nonnegative integers except controls (`none` or `own layout`). Chara/stage/flag/second values are parsed from hexadecimal runtime fields but represented as JSON integers; seed remains the separately required plan seed. This bounded implementation admits only explicit stock rules (`rule_kind=1`, positive `stocks`), with declared header `rule_stock` equal to the expected per-player stock count. `SSBU_DEBUG_MATCH` must be nonempty so existing ready-go diagnostics are available. Root must supply actual intended values; no new semantic defaults or reference fixture are inferred.

`application()` parses the existing production grammar from `runtime/rb_net.c:hs_print` and `runtime/debug_mode.c:hs_apply`, `match_player_hook`, and `debug_mode_frame`. It compares all negotiated fields with the plan, rejects both exact production unapplied-rule and unavailable-player-panel diagnostics, requires all eight ordered original player-record readbacks (two matching human players, six inactive slots), and requires exactly one subsequent ready-go readback. The ready-go fields must match expected fighter kinds, stage ID/chosen stage/form/flags/hazards, item appearance, rule/header stocks and both fighter-record stocks. Missing, duplicated, malformed, out-of-order, nonhuman or extra active player records fail.

Source inspection alone initially suggested checking only the two active player records. Reading the retained real baseline log confirmed that production emits all eight, including inactive slots 2–7; the implemented parser and synthetic positive reflect that actual grammar. No new runtime readback was invented. The controls-layout payload and stage-history block are not exposed by this readback; declaring/observing their summaries does not establish their complete contents or atomic application. Existing endpoint and complete-state limitations remain.

### Finding 2: admitted attempt and closed-output binding

Preparation now creates an exclusive `attempt.json`, format 2, with a fresh UUIDv4, creation time and canonical plan digest. Every command includes this attempt ID alongside its existing plan/identity fingerprint. The launcher writes an exclusive `completion.json`, also format 2, on successful and failed/partial attempts. It binds:

- UUID and canonical plan digest;
- canonical digest of the actual two recorded admission samples;
- each started peer's PID, start-request and start-return timestamps, observed termination timestamp, actual exit value and timeout/closed flags;
- hashes of the closed peer command, identity, game log, launcher log, trace and result, plus R1 log when present;
- hashes of plan, attempt, admission and inventory-recheck root records;
- retained launch, cleanup, recheck and missing-output errors.

`result.json` now repeats the attempt/role and complete recorded lifecycle, rather than merely `exit: 0`. The completion gate requires exactly host/join membership, distinct positive PIDs, ordered lifecycle times, no timeout/errors, closed zero-exit peers, exact required output membership and matching hashes. It validates the paired budgets, finite numeric samples, 15–45 second sample interval, drift, absent game/build processes and five-second freshness independently at **both** start-request and start-return timestamps for each peer. The host start-return precedes the join request, and the recorded host termination observation must follow it. Missing admission/UUID/completion, stale or resource-failed samples, incomplete membership and prior-attempt/same-role differing output substitution fail even when the trace still equals the original reference.

Actual native creation is bracketed around `Popen`; its precise internal OS creation instant is not independently observed. `ended_at` is the timestamp at successful `wait` observation, not a kernel termination-event timestamp; the waits may observe an already-ended peer. The manifest detects accidental inconsistency/substitution, not adversarial resealing, cryptographic provenance, precise simultaneous execution or loaded-code attestation. Byte-identical substituted files are inherently indistinguishable by hashes. The existing five-second resource rule and nonconcurrent-writer inventory limitation are unchanged.

The launcher checks freshness immediately before **each** native `Popen`, then again on return. A slow host creation or a pause before join cannot authorize the second launch with stale samples. Heavy identity/cache hashing still precedes admission; the post-admission metadata screen remains cheap. Both timeout and cleanup `taskkill` calls now have ten-second subprocess timeouts; owned-process waits remain thirty seconds. Cleanup failures and unclosed peers are retained, never upgraded to success. The standalone gate report is also written after failed/partial launch cleanup, preserving readable original-reference outcomes independently of admission, identity, rule, fatal or completion failures.

### v2 offline tests and source-validation boundary

Commands (configured Python, no optimization):

```powershell
deps/python/Scripts/python.exe -m unittest discover -s tests -p test_initialization_pair.py -q
deps/python/Scripts/python.exe -m unittest discover -s tests -p test_runtime_trial.py -q
deps/python/Scripts/python.exe -m unittest discover -s tests -p test_battle_identity.py -q
deps/python/Scripts/python.exe -m unittest discover -s tests -p test_bounded_trace_cmp.py -q
```

Results: **26 pair tests + 25 runtime-trial + 16 battle-identity + 7 bounded-trace = 74 passing tests**. Process, taskkill and capacity boundaries in the new launch tests are mocked; real temporary outputs are hashed. A mocked successful launch exercises the actual completion writer and standalone gate together. Negative cases include the reviewer's four exact counterexamples, resealed symmetric wrong negotiation, missing/wrong application readbacks, extra active slots, absent expected fields, missing UUID/admission/completion, wrong membership/PIDs/timestamps/flags, stale or insufficient admission with self-consistent manifest hashes, `exit:0`-only results, same-role log substitution, each-native-start expiry, delayed native creation, partial spawn and timed-out cleanup. Tests verify readable original-reference verdicts survive these failures. When the retained reviewer artifact exists, the test checks its historical counterexamples still say `passed` and verifies its bytes remain unchanged.

An intermediate test failure exposed an outdated mock returning a MagicMock from `wait`; lifecycle serialization now requires the actual integer return that production supplies, and the test mock was corrected to return a concrete negative exit. The failed run is a source-test iteration only; no historical evidence was rewritten. Existing forward-only configuration and rollback replay gates remain unchanged. `tools/initialization_endpoints.py` is unchanged from the first freeze.

Root must request a **new independent review round** for this v2 freeze. Review should challenge the explicit field/production-readback mapping, all-eight-player grammar, completion membership and hash binding, both native-start freshness boundaries, termination-observation limits and bounded failure cleanup. Real-input preparation, native startup/application, runtime packet exchange and real post-run inventory behavior remain unrun. This implementation does not resolve finding 3 or authorize games under the retained capacity refusals.

Frozen v2 raw SHA256 values:

```text
7f79cd8a56b41b175144c39f8122c046784d7b7492e4ba10a5e709cd44c5ac13  tools/check_initialization_pair.py
a9293a476e630b3e438b24206a3952d3a4aedb415c5c762e3e939d8cb2e79aa4  tools/run_initialization_pair.py
4cffc0fdc5cb007f115d8c20ca306836ab696779f3199d4e067212f0a2ddb98b  tools/initialization_endpoints.py
30c43b1d02d688c6a32e4a4fe0ce765626492e0e2dc4cc5a955cb6cec4d48b1c  tests/test_initialization_pair.py
```

Retrospective: complete trace equality did not validate intended rules, and a valid input inventory did not bind closed outputs to a particular admitted attempt. The v2 tests exercise those independent obligations, including production failure diagnostics and the launcher-to-gate success path. Independent acceptance remains a separate next step.
