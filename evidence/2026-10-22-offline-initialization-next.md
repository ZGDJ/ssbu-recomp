# Next offline initialization decision

Research-only packet, 2026-10-22. Inspected clean branch `feat/rollback-validation-audit`, HEAD `11287ff8598c37db8561ff291cb7e85e446942ed`. Exclusive write: this report. Root owns ledger/handoff, helper adoption, builds and all launches. No game, build, runtime edit or commit performed. This is an experiment recommendation, not fresh gameplay acceptance.

Read AGENTS, current continuation/handoff/ledger, workflow and relevant validation requirements; reused [ownership](2026-10-22-battle-seed-ownership.md), [independent boundary challenge](2026-10-22-battle-seed-boundary-challenge.md), [timing result](2026-10-22-prematch-timing.md), [reviewed menu observer](2026-10-22-prematch-boundary.md) and [handshake isolation](2026-10-22-handshake-isolation.md). M3.5 forward-only investigation does not depend on network readiness or blanket completion of M7. Capture/restore retains its separate prerequisites.

## Decision

Run the already-reviewed menu-boundary experiment, without seed/owner/reset modification, on the matching current frozen package: menu-disabled baseline, menu-enabled baseline, then the single +60 contrast. Its unanswered question is whether the global source differs before the treatment, during the sampled neutral interval, or between confirmation and selection. This discriminates the next correction boundary; another consumer census does not.

Do not describe the experiment as repairing initialization. The existing failure is consistent with history-dependent original seed selection; the intended product/fixture contract still needs an explicit decision about whether different pre-match histories must produce identical battle initialization. A startup entropy setting is insufficient to impose that contract.

Current source was checked at the existing ownership boundaries:

- `runtime/nnsdk.c:44`: a nonempty fixed seed selects constant clock values at four callers; its numeric value does not alter those constants. `runtime/os_threads.c:1091` initializes a stateful random-byte stream, then advances it. Neither provides an offline per-battle reset.
- Private generated selector `build/work/gen_eh_o2/c_01bc.c`, `f_71014d8620`, labels `71014d8ef4..8f2c`: flag +0x9c controls the final draw into input +0x98. Clearing that flag suppresses a global advance. Labels `71014d88c0..88ec` independently select an alternate seed when the selected record and byte +8 allow it. Mode zero is not an eligibility proof.
- Private constructor `c_019b.c`, labels `7101345314..5324` and `71013454b0..54e8`: original input copy supplies owner +0xf8 and subsequent original recurrence. Retain the previously audited later reset from that owner; no evidence warrants suppressing it.
- `fighter_sdk/fighter_host.c:1298` still replaces the first-fighter vectors under deterministic mode without changing their original owner. Frame-one agreement can therefore mask upstream initialization differences. It is not an authoritative seed fix.

No copied generated code is included. These checks confirm selected source paths; they do not newly prove loaded execution, branch coverage or transitive absence of earlier random decisions.

## Executable resources and a concrete stale-helper trap

Read-only verification in this packet found:

- Current `setup.tree_digest()` = package manifest digest `770a5d8c9979c83718a9e4be810089e8e184e3e1ec52213f4377156e8f267826`; complete source maps match. Every declared file in `artifacts/local/runtime-handshake-isolation/package` hashes correctly. Executable is the previously reviewed `8b91dbf80026d0a71f952fab92623e3d86d79d7081e2a278a86ddbade01d00f8`.
- Every entry in `artifacts/local/prematch-boundary-20261022/tools-freeze.json` still hashes correctly, including launcher, comparators, helpers and original tape/reference. Old `disabled`, `baseline`, `wait` trial output directories are absent; old prepared build/cache directories exist.
- Original tape hash `2fd61c62b48cd52c909eb44b08b51832a9294b25bf1bd26b0a629652089f8760`; original reference `e5ef275192ed6c0d244107689e59924e95e0f1e7b710c3b90c58224560be8de2`. Existing wait tape is exactly the original bytes with the first `90:Z` replaced once by `150:Z`; retained protocol identifies this as zero-based token 15. Preserve CRLF, token count, other waits/holds and complete `@fight` suffix.

**Do not invoke the old `run_trial.py` unchanged from current root.** It hardcodes `runtime-prematch-boundary/package` (old source digest ad738986...), whereas `scripts/battle_identity.py` requires its manifest to match the current tree. Old `verify_frozen.py` also expects that old source/protected-path layout. Do not weaken either check or temporarily overwrite current runtime files. The current matching package contains the same menu observer and can run offline with initialization isolation explicitly disabled. A new disabled control is required on it.

Old helpers also have narrower contracts than their names imply: `admit_trial.py` writes a one-shot token but `run_trial.py` checks only its `admitted` Boolean, not freshness; root must enforce immediate use. `analyze_observations.py` records `original_reference=FAILED` without returning failure for that fact; `analyze_boundary.py` can mark a reference-failing diagnostic usable. Their exit codes are not overall acceptance. Explicitly conjoin the separate original-reference gate and identity results. No helper here supplies the required cross-arm identity comparison automatically.

## Root-only trial recipe

The following is a preparation recipe for root to review/adopt, not code executed by this researcher. It uses new output paths and copies, preserving historical helpers, caches, packages and reports. Run from repository root with unoptimized configured Python. The cache-copy preparation may be expensive; abort on disk shortage rather than altering old inputs. Recheck current source/package identity immediately before adoption; active runtime changes invalidate this recipe's candidate.

Prepare a fresh packet by running this Python snippet with `deps/python/Scripts/python.exe` (no `-O`):

```python
from pathlib import Path
import hashlib, json, shutil, subprocess, sys
assert not sys.flags.optimize
r = Path.cwd()
old = r / 'artifacts/local/prematch-boundary-20261022'
out = r / 'artifacts/local/offline-initialization-next-20261022'
out.mkdir()  # refuse reuse, including a partially completed preparation
sys.path.insert(0, str(r / 'scripts'))
import setup
package = r / 'artifacts/local/runtime-handshake-isolation/package'
m = json.loads((package / 'manifest.json').read_text())
assert m['tree_files'] == setup.tree_files()
assert m['tree_digest'] == setup.tree_digest()
assert m['tree_digest'] == '770a5d8c9979c83718a9e4be810089e8e184e3e1ec52213f4377156e8f267826'
for name, item in m['files'].items():
    assert hashlib.sha256((package / name).read_bytes()).hexdigest() == item['sha256']
for name in ('prepare.py', 'admit_trial.py', 'run_trial.py',
             'analyze_observations.py', 'analyze_boundary.py', 'verify_inputs.py'):
    text = (old / name).read_text()
    text = text.replace('prematch-boundary-20261022', 'offline-initialization-next-20261022')
    text = text.replace('runtime-prematch-boundary/package', 'runtime-handshake-isolation/package')
    if name == 'run_trial.py':
        anchor = "settings['SSBU_SKYLINE']='0'"
        assert text.count(anchor) == 1
        text = text.replace(anchor, anchor + "\nsettings['SSBU_RB_NET_INIT_ONLY']='0'")
    (out / name).write_text(text, encoding='utf-8')
shutil.copy2(old / 'wait-sequence.txt', out / 'wait-sequence.txt')
subprocess.run([sys.executable, str(out / 'prepare.py')], check=True)
for label in ('disabled', 'baseline', 'wait'):
    work = out / (label + '-build/work')
    for name in m['files']:
        shutil.copy2(package / name, work / name)
    shutil.copy2(package / 'ssbu_native.exe', work / 'ssbu_menu_boundary.exe')
    assert hashlib.sha256((work / 'ssbu_menu_boundary.exe').read_bytes()).hexdigest() == m['files']['ssbu_native.exe']['sha256']
(out / 'deployment.json').write_text(json.dumps(m, indent=2))
```

This reuses the old preparation's independent warm-cache copies and full cache hash comparison against the retained warmed source; it does not compile. Root should pin the adapted helper bytes, source/package and every input before admission and preserve a post-run inventory. Do not reuse `build_candidate.py`, `verify_frozen.py`, `finalize.py` or historical evidence-writing scripts. The preparation manifest does not replace prelaunch or postlaunch battle identity.

Then execute **one arm at a time**, substituting `baseline` and finally `wait` only after the preceding control passes all obligations below:

```powershell
$py = Get-Content build/python_path.txt
$packet = 'artifacts/local/offline-initialization-next-20261022'
& $py "$packet/admit_trial.py" disabled
if ($LASTEXITCODE -ne 0) { throw 'No game admission' }
& $py "$packet/run_trial.py" disabled
# Record its exit. On failure stop progression; retain and analyze readable evidence.
& $py "$packet/analyze_observations.py" "$packet/disabled"
& $py "$packet/analyze_boundary.py" disabled
& $py "$packet/verify_inputs.py" disabled
```

Root must inspect each exit/report; this is intentionally not an unattended three-arm batch. Fatal/configuration/completeness failure prevents attribution; a complete reference failure may be analyzed diagnostically but never promoted. If admission becomes stale during an interruption, retain it and produce a fresh attempt with distinct outputs rather than consuming it. Actual resource availability was not sampled by this researcher; no token or game slot is claimed.

Each arm retains the existing 900-second launcher budget, seed 1, concrete Mario/Mario human-P2 end/normal stock-three items/hazards-off rules, fresh identical initial saves, warmed application-cache policy, normal speed and exact fight suffix. Require explicit R1/RUNAHEAD/RB_SIM/RB_NET/LS/MEM_KEEP/SKYLINE and RB_NET_INIT_ONLY zero. Origin/reset/early probes and screenshots stay symmetric; only MENU_PROBE differs between the first two arms, then only the declared tape token differs. Verify effective command settings and runtime rule readback rather than trusting inherited defaults.

Fresh single-game admission is two samples 15 seconds apart, no game/build process, >=10 GiB commit headroom, >=10240 MiB available physical and <=512 MiB committed drift. Root monitors host pressure during the run. No paired token is needed for these serialized offline runs; no threshold reduction or closing user applications is part of this recipe.

Required conjunction: unchanged `check_runtime_trial.py --forward-only` fatal/configuration gate; sealed exactly 500R/0S; unchanged `tests/bounded_trace_cmp.py TRIAL/fight.txt artifacts/local/save-import-20261021/bounded-forward-500-a/fight.txt`; complete original origin/reset/12 ordered raw-early records with trace folds and same-thread owner associations; menu silence or complete menu records as applicable; phase/screenshot evidence; pre/post immutable identity and exact cross-arm input differences. The wrapper invokes the first two comparison tools; the separate adapters supply observations, not replacement gates. Require the begin-to-confirm 91/151 sequence-tick relationship and original step14/15/16 phase ordering. These are not authoritative simulation-frame input timing or atomic observations.

## Outcomes and stopping criteria

1. Disabled baseline fails original reference, fatal, completeness or identity: stop before enabled arm. The candidate/reference or startup issue precedes menu observation. Preserve the failed attempt; no new reference and no delay sweep.
2. Disabled passes but enabled baseline fails: stop before +60. Observer perturbation is a live explanation, not proven causality; retain exact pressure/phase differences and do not implement a seed correction from this pair.
3. Both baselines pass; +60 differs already at begin: the treatment cannot explain that earlier difference. Stop this question and select one earlier existing boundary for investigation. Do not keep collecting waits.
4. Begin agrees, confirm differs: narrow the next question to consumption during the sampled interval, subject to concurrent writers and observation overhead. Select a bounded executed-consumer observation only if it can distinguish a concrete correction; algebraic recurrence distance is not a call count.
5. Begin/confirm agree, selector entry differs: narrow to confirmation-to-selector initialization. A late input/owner write cannot repair earlier choices.
6. Selector entry agrees but returned seed/owner differs: investigate alternate-record/context/branch inputs or intervening mutation. Existing endpoint equality cannot rule out selected-record execution. Do not infer eligibility from mode zero alone.
7. Owner agrees but reset differs: inspect reset identity/lifecycle; reject the premise that seed input alone fixes it.
8. All observed endpoints and original reference agree: no correction justified by this trial. At most this is a non-reproduction under the recorded controls. Proceed to repeated uninstrumented histories and second seed as separate declared cases; preserve historical failure and distinguish startup seed from battle seed. Matching endpoints do not prove complete initialization equality.

Stop after the first discriminating completed contrast or failed prerequisite. A fixture/correction claim needs repeated uninstrumented behavior and explicit original gameplay semantics, not simply one matching trace.

## Smallest semantic candidate after the boundary decision

There is already a narrower experiment than a runtime patch: `SSBU_DET_OFF=1` suppresses only the first-fighter vector rewrite in the inspected code, while bit 2 governs the separate fighter stepping gate and bit 4 the separate control mutation (`fighter_host.c:1298,1405,1416,1454`). Keeping deterministic mode enabled and setting only bit 1 can test preservation of original constructed/consumed RNG state. This is **not** the same treatment as turning deterministic mode off, and it cannot make different original owner seeds equal. Do not combine it with the menu contrast.

If root selects this later experiment, first inspect the actual baseline mask, compare mask 0 versus 1 with all other conditions fixed, use the existing frozen binary and retain original construction/reset observations. Require absence of the forced-vector write and continuity with original owner/reset behavior; allow already-consumed constructor state rather than demanding a pristine recurrence at constructor return. Compare against original reference and record any expected first-frame difference as a failure of that historical reference, not automatic fixture acceptance. Establish original-behavior provenance and repeated uninstrumented results before proposing a separately named reference. This source-supported setting can test removal of one nonauthoritative intervention; it is not yet a supported production correction or a fully original gameplay baseline.

Reject arbitrary reseeding at menu, selector return, owner or reset. Direct input +0x98 with flag zero changes consumption, needs guarded original-path eligibility, and does not cover earlier stage/context decisions. A deterministic battle contract needs an explicit input/seed mapping and original semantics justification. Do not bless a new fixture because it agrees with itself, or replace the original with a trace from the failing +60 arm.

## Independent paired-tooling threat checklist

For later review of the separate initialization launcher/gate, require negative tests and production wiring for each applicable item:

- Admit the pair as a pair with fresh two-process capacity, separate ports/userdata/output paths and no third game. One admitted single process, stale token, partial launch or resource-failed peer cannot qualify a pair. Bounded cleanup must cover only owned processes.
- Pin both source/package/executable/module/input identities, game 13.0.5, roles, seeds, rules, tapes and initial saves. Reject missing, contradictory, swapped, stale or cross-peer evidence and command/identity disagreement. Prelaunch inventories alone do not prove loaded hooks.
- Require literal NET=net and INIT_ONLY=1, all eight required zero controls, actual runtime acknowledgement, exactly first setup and successful current host/join agreement on both peers. Reject loop/disabled handshake/fallback, false agreement, stale cached nonzero seed, second setup and mismatched seed/stage inputs. An acknowledgement line alone is not successful original construction.
- Keep both local pads explicit and distinguish shared negotiated choices from frame input delivery. No remote-input, speculation, readiness or rollback qualification follows from this diagnostic.
- Propagate either peer's nonzero exit, timeout, incomplete launcher result, missing/unreadable logs or zero-exit fatal even after a sealed trace. Record both peers independently; aggregate success cannot mask one failure.
- Require sealed 500R/0S and completed selector/owner/reset endpoints per peer, closed readable same-thread associations and raw-fold coverage where enabled. Reject duplicates, unusable observations, unexpected capture/replay, empty traces and a peer never reaching battle.
- Retain every original-reference verdict separately from peer equality and observational usability. Do not use offline `--forward-only` for NET, modify its evidence, remove replay obligations from rollback comparators, or turn a record parser into an acceptance gate.
- Demonstrate the disabled new-binary original-reference control before the admitted same-history pair, then differing history, second seed and uninstrumented repeats. Report branch/earlier-state omissions even on endpoint agreement. No automatic promotion of a newly mismatching network fixture.
- Check immutable inputs again after both runs, retain failed reports/logs, and test shared-file collisions, evidence substitution and interrupted cleanup. Pair identity must associate a particular run/setup, not merely common executable hashes.

## Preservation, validation and retrospective

The +60 frame-two RNG mismatch with 499 differing frames, b77b0413/fa10bec7 observations, reconstructed historical f28f3988, SDK/reference failures, empty-cache abort, disabled-b resource/zero-replay failure, original/revised protection reports and all no-admission outcomes remain unchanged and unresolved within their recorded scopes. The reservation provider rejection remains absence of technical result. M7.8 and M7.1 remain separate; the next actual rollback proof still requires uninterrupted/default save-advance-restore comparison, 500 real frames and exact two replay runs before delayed correction/depth expansion.

Validation performed here: bounded source/helper reads; current normalized source/package verification; old pinned helper/input hash verification; exact tape replacement check. No new test/build/game acceptance is claimed. Root-only preparation and launch snippets above were inspected but not executed. `deps/python/Scripts/python.exe tools/check_project_docs.py` passed; `git diff --check` passed. Concurrent ledger and paired-tool additions observed at closeout belong to other work and were not edited or reviewed here.

Retrospective: the useful new finding is operational, not another RNG census: old prepared trials cannot pass current strict source identity unchanged. Reusing the current frozen package with fresh helper/output copies avoids a needless rebuild while retaining the disabled control. Admission freshness and reference-result conjunction remain explicit root responsibilities until separately tested tooling enforces them.
