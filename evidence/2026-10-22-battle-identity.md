# M1.1: bind prelaunch battle evidence to existing identities

Date: 2026-10-22. Scope is source tooling, not a game-backed result. Existing uncommitted runtime/test work and all failed controls were preserved. No game was launched, normal executable replaced, save changed, or private input modified.

## Packet and concrete gap

The existing `scripts/make_release.py` runtime manifest already records normalized staged source identity, source commit/dirty state, runtime file SHA-256/size, interface version and compiler version text. `scripts/setup.py` already supplies hashing and version mapping. The local trial wrapper records an executable hash, but neither mechanism binds a trial to its effective module/content/config/save/tape inputs. This allows unlike inputs to be described as the same candidate.

M1.1 reuses those mechanisms through `scripts/battle_identity.py` and opt-in `scripts/run.py --identity-runtime ... --identity-output ...`. No independent provenance service, alternative build system or runtime observer was added. New package manifests additionally record the compiler executable SHA-256. Older compiler declarations remain declarations; the current setup compiler hash is labeled observed, not retroactively asserted as the compiler that built an old DLL.

Decisive validation: identical disposable fixtures produce identical inventory; each material file/setting change changes identity or refuses; mismatched/missing inputs refuse before the child starts; prior evidence cannot be overwritten. Stop once the bounded tooling and production launcher seam meet these tests. Actual stale-object invalidation remains M1.4; three complete identified matches remain M1.2.

## Implemented coverage

- Strict package/current staged-source identity, including added files; interface/version checks reuse setup. Main ELF structural/text-size classification must agree with setup's 13.0.5 declaration. This is the inherited version classification plus hashes, not an independent game authenticity verifier.
- Package and deployed runtime executable/SDL/glslang identities must agree. Executable basename is recorded because it changes runtime behavior. Game/module DLL inventory and binary input directory are hashed; optimized `nro_bin_eh_o2` is the runtime default.
- Full content/config/initial-userdata inventories, sequence file and effective SSBU/RECOMP/VK setting hashes, compiler/setup-state/launcher/tool identities. Known external SDK, config (including sibling graphics.ini), route, module/fighter, font/timezone and opus inputs are bound; relative paths use child working-directory semantics.
- Output/input collisions refuse before launch; new evidence uses exclusive creation. Missing/empty required inputs, unreadable files, links in inventories, and detectable file mutation during hashing refuse. NRO autobuild is refused. Discovered active Skyline plugins require explicit disabling for this base-game scope rather than being silently omitted.
- No raw content/save bytes, environment values or absolute paths are emitted. Hash identity does not replace privately retained launch commands or readable fixture/rules definitions.

## Validation and review

`python -m unittest discover -s tests -p test_battle_identity.py -v`: **16 passed**, including production launcher ordering with a mocked child, mutation/missing-input cases, strict added-source refusal, runtime mismatch, relative override content, default optimized modules, external fighter directory, plugin refusal, executable name, output collision, unreadable/changing input, version rejection and evidence preservation. Added this suite to the existing Windows source CI workflow; no hosted CI run is claimed.

Three bounded read-only Astra low-effort review rounds found and resolved external SDK/route/plugin coverage, log collisions, executable-name identity, external fighter paths and the incorrect initial NRO default. Final review independently ran all 16 tests and found no remaining concrete blocker within this scope. No reviewer edited files or ran games.

Read-only local inventory attempt used `artifacts/local/runtime-rng-checkpoint/package` and `build/work/ssbu_rng_checkpoint_probe.exe`. It **refused** because deployed `ssbu_glslang.dll` differs from the frozen package. Retained report: `artifacts/local/m11-identity-validation/smoke-result.json`; no inventory pass or gameplay result was produced. This establishes a real package/deployment identity gap, not causality for previous RNG/protection failures. Do not silently refresh the normal DLL, modify the old manifest, or relabel previous trials. A consistent isolated candidate is needed for the next identified run.

Source-test logs and structured validation reports remain under `artifacts/local/m11-identity-validation`. Project-document validation and diff checks are recorded there after integration. Initial document validation failed only because this evidence file had not yet been created; the final check supersedes that structural failure, not any runtime failure.

## Limits and next proof

This is a prelaunch inventory. It does not freeze concurrent writers, attest loaded DLLs, prove an old module was rebuilt by the observed compiler, establish a collision-free cross-machine semantic config identity, or qualify gameplay. Keep inputs frozen and existing post-trial checks. Full hashes are computed before the child starts, never on gameplay threads. No historical control is upgraded.

M1.1 tooling acceptance is complete. M1.3 critical-hook validation is now dependency-ready; M1.4 cache correctness remains the immediate implementation packet before formal M1.2's three identified complete matches. A source read identifies a concrete M1.4 seam: `build.py:cmd_compile` can reuse a timestamp-new object before checking current content/config, and its recorded key omits compiler bytes. Reproduce this with disposable fixtures before changing it; do not assume all build paths share the same defect.

The updated ledger moves RNG attribution to M3.5 and keeps M7.8's finite resource closeout. `docs/VALIDATION.md` maps defects to affected trials: forward-only attribution and focused fixture work can proceed independently where they do not exercise unsafe capture/restore paths; SDK reference failures and restore qualification gates remain intact. M6.1 examples stay concrete replay/correction cases. FSD-009 and M5.2/M5.3 now require paired bounded diagnostic bundles with manual export/sharing; no upload/dashboard implementation is part of M1.1.
