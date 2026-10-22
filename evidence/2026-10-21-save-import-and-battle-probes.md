# Completion-save import and actual battle probes

Date: 2026-10-21. Task M1.6; requirements FSD-001/FSD-011. Root performed import, launch, visual inspection and integration; root/audit independently inspected fixture and rewind-driver configuration. Base commit `46a8f6cc56587939c1ce93fd6a1293c8475ab1e1` plus the uncommitted validation changes recorded in the prior audit. Runtime/generated game code unchanged.

The owner clarified that no downloaded save had been applied and authorized end-to-end installation/testing. Found the supplied archive `smashultimate100_4.7z` at workspace root (the prompt included an extra zero). OpenSmash was closed; process enumeration found no SSBU executable before installation. The earlier DLC-screen navigation failure came from generated startup save data, not the downloaded completion save.

## Installation

Inspected archive listing and rejected absolute/traversal/drive paths and non-file/directory entries. Extracted under ignored `artifacts/local/save-import-20261021/extracted`. Archive contains a `save_data` directory with system, Mii, spirits and custom-stage data. The system file has the expected existing size (5,982,968 bytes); size agreement is not content authenticity.

Backed up all existing `build/saves` to local `before-userdata`, additionally preserved the old `save_data` tree as `previous-save_data`, then installed the archive's tree at `build/saves/save/save_data`. All 24 installed files matched their extracted SHA-256 hashes. Archive/file hashes and backup paths are in local `import.json`. No save or archive is committed. The save's advertised 100% completion is not independently exhaustively verified.

## Normal battle smoke

Used `scripts/run.py` with a disposable imported save, separate `ssbu_save_probe.exe`, 150-second requested limit, `tests/seq_completo_1305.txt`, fixed seed 12345, online/rollback off, movie skip, fighter hashes and screenshots. Configured Python 3.12.3, installed Windows x64 runtime, locally built Ultimate 13.0.5 game/module libraries, existing RTX 4070 setup. No dependency installation or runtime rebuild needed.

Exited 0 after 154 seconds. Input sequence passed menus/selection and reached a battle. Inspected frame 1800: Chrom versus CPU Wolf on Fountain of Dreams, seven-minute/three-stock display. Collected 3,507 distinct fighter frames (1..3507), 7,014 entity rows. This is actual battle smoke, not a complete match, full-roster qualification, deterministic replay or rollback proof. Installed save hashes remained unchanged; only disposable-copy saves were exposed to testing.

## Two controlled forward trials

Fresh imported save copies for both processes; identical script, seed 1, deterministic diagnostic mode, Mario mirror, Final Destination normal form, three stocks, items/hazards off requested, neutral human P2. Configuration includes `SSBU_DEBUG_MATCH`, `SSBU_KEYBOARD_PLAYER=2`, `SSBU_RB_NET_AUTOP2=1`, `SSBU_DETERMINISTIC=1`, `SSBU_DEBUG_END=600` and online/rollback off. Exact invocations are local `forward-a/command.json` and `forward-b/command.json`; bounded orchestration is `run_controlled.py`.

Verified runtime match log: both kind 0/Mario, P2 human type 0, stage id 3 / end, normal form, stock 3, item appearance 0, records 3/3. Inspected a Mario-mirror Final Destination screenshot. Name-to-kind diagnostic initially prints -1 because an optional external constants file is absent, but actual match construction uses named UI-character hashes and logged resolved records are kind 0; do not mistake the initial diagnostic for the actual fighter selection.

Both processes exited 0. Trial A records 820 fighter frames/1,640 rows; B records 807 frames/1,614 rows. Every one of the 807 overlapping frames has identical logged entity fields (excluding the intentionally process-running hash). Full coverage differs, so the runner exits 1 and records `coverage_equal: false`, `different_frames: 0`. Preserve this as a failed equal-coverage check, not a full pass. `DEBUG_END` counts presented ready-go frames and asynchronous shutdown can append differing tails; establish an authoritative exact-step boundary before qualification.

The common interval exceeds the preselected 600-frame minimum, but these are limited fighter telemetry fields. Script mode supplies one P1 input sequence and neutral P2, not two independent tapes. Deterministic mode actively reseeds script RNG and suppresses dropped-refresh extra steps; it requires independent behavioral comparison before equivalence claims. M1.2, M2 and M3 remain open.

## Retention and next work

Private raw saves, screenshots, logs, commands, comparisons and binary/input SHA-256 identities live under ignored `artifacts/local/save-import-20261021/`. The installed save is ready for normal `Play SSBU.bat`. No network peer or recurring service was started. Preserve the import backup until the owner is satisfied.

## First requested depth-one rewind probe

Normal game DLL is supported through the inherited learned-page mechanism. Starting from another fresh imported save, added `SSBU_RB_SIM=120,1,60`, `SSBU_RB_SIM_VERIFY=1`, `SSBU_RB_SIM_SKIP=0`, `SSBU_RB_SIM_LITE=0` and a separate `SSBU_R1_LOG` to the controlled configuration. This requests a rewind every 120 real passes after 60 captures, depth one; actual depths must be checked because skipped captures can increase them.

The process exited 0 after 79 seconds, but the runtime refused its base save: 2,293 MB free commit versus 2,392 MB snapshot plus 1,024 MB game reserve. It explicitly logged no rollback ring. Therefore zero rollback capability is established. The snapshot guard was not bypassed and no system/pagefile settings changed. The final fighter-log row was truncated on shutdown; the strict simulation comparator rejected it as malformed. Raw logs retained in `rewind-one`; do not truncate the evidence to manufacture a pass.

## Deferred-shader depth-one probe: actual rewind, failed verification

Repeated from a fresh imported save with the sole additional override `SSBU_VK_LOAD_AT_START=0`. Source inspection confirms this loads each prepared shader container at its loading screen instead of retaining all containers from startup. This override was local to the test; normal graphics settings, commit-memory reserve and pagefile settings were unchanged.

Exited 0 after 64 seconds. The runtime initialized learned-page tracking, created the base/ring and logged **five actual depth-one rollbacks** at passes 119, 238, 357, 476 and 595. The verifier reported differences after every rewind: 5,305 page comparisons total across checks; window-1 difference counts 690/371/106/117/498, window-2 7/6/6/7/6, extras 2/2/2/6/2. These are per-check counts, not unique physical pages. Logged examples include guest regions and stack/TLS. No claim that every differing page is authoritative gameplay state; ownership classification remains required.

The intermediate ring report records 497 captures and four loads, but a fifth rewind occurs afterward. RA kind labels likewise stop before all final fighter records, and the final fighter row is truncated. The strict comparator exits nonzero (`INVALID: malformed fighter hash line`). This is failed validation even though the process exits successfully. Preserve complete raw files in `rewind-loading`; do not discard mismatching or unlabelled tails to report success. The built-in verifier also excludes extras from its headline bad-run counter; our evidence records extras explicitly.

The snapshot-memory refusal and shader-load sensitivity are measured research findings, not proof of a supported memory/performance envelope. Do not bypass memory checks or weaken depth-eight/full-roster requirements. Next establish complete exact-interval logs, then map differing tracked pages to state owners and compare presentation settings using matched baselines. Keep ADR-0007 provisional; these observations justify investigating checkpoint/state boundaries, not automatically replacing the transport.

All tests have exited. Installed save hashes still match the imported archive. Original generated save backups remain intact. Project-document validation is required for the accompanying ledger update. M1.6 closes save installation and observed launch outcome only; M1.2/M2/M3/M4 qualification stays open.

Independent verifier review: raw page hashing groups address windows, not gameplay categories. Captured extras include stack/TLS, catch-table and presentation allocator bookkeeping. After coherent trace completion, compare restored bytes against the selected snapshot while continuations remain held, then use a bounded `SSBU_RB_SIM_VERIFY=2` probe to identify first differing offsets and their owners. Do not add blanket exclusions. This separates restore errors from rerun-induced differences; it remains research ahead of deeper/network testing.
