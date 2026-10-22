# Initialization-only handshake isolation design

2026-10-22; Astra A, delegated task `/root/handshake_isolation`. Source inspection only; no runtime edit, build or game. Exclusive write scope is this report. Inherited dirty work is preserved. This extends the [initialization contract](2026-10-22-battle-initialization-contract.md), without repeating the seed-ownership audit.

## Decision and firm activation verdict

**There is no existing Windows switch combination that runs the successful real host/join handshake while guaranteeing that snapshot coordination is inactive.** The missing capability is isolation of the already-supported handshake and original construction, not another seed write.

Exact activation chain:

- `runtime/rb_net.c:48-64`: any nonempty `SSBU_RB_NET` not starting with `0` enables `rbn_on`; `loop` is separately recognized.
- `runtime/rb_net.c:152-156,269-270`: handshake requires that network switch, excludes loop, and can only be disabled by `SSBU_RB_NET_HANDSHAKE=0`.
- `runtime/rb_rollback.c:43`: `rbg_on` directly mirrors `rbn_on`.
- `runtime/r1_ring.c:1389,1396-1399`: initial `g_rgs_on=-1`; `rgs_wanted` chooses network rollback before examining `SSBU_RB_SIM`. Thus `SSBU_RB_SIM=0` cannot override network activation.
- `runtime/r1_state.c:103-125`: `ra_wanted` ORs ring activation with runahead; `r1_on` ORs that result with `SSBU_R1`. Explicit `SSBU_RUNAHEAD=0` and `SSBU_R1=0` cannot override it.
- `runtime/r1_state.c:2786-2805,2620-2647`: active R1 initializes capture/learned-set infrastructure and runahead hooks; `ra_init` installs kick hooks and invokes `rbn_init`.
- `runtime/rb_rollback.c:144-164`: the first gameplay coordinator step attempts capture/rebase before choosing the no-ring fallback. `SSBU_RB_NET_TEST_NOMEM` therefore exercises resource/capture paths; it is not a snapshot-free diagnostic mode. Large `TEST_LATEBASE` values also retain coordinator hooks and alter startup pads/epoch.

`SSBU_RB_NET=0` prevents this activation but also prevents the wanted handshake. Loop, Local Wireless bypass, no-room local bypass and failed-handshake fallback do not answer successful host/join initialization equality.

## Smallest supported seam

Add one explicit opt-in initialization diagnostic, for example `SSBU_RB_NET_INIT_ONLY=1`, with an exported predicate owned by `rb_net.c`. Keep the production default byte-for-byte equivalent in decision behavior. Root owns final naming and implementation.

1. Retain `rbn_on`, `rbn_handshake_wanted`, `rbn_rx` handshake dispatch, real transport, handshake seed publication/reseed, and `debug_mode.c`'s exact successful `hs_apply` and original-record call. Suppress **only network game coordination**, by making `rbg_on` false under the validated diagnostic. Do not suppress `rbn_on`: that would lose handshake/receive and connected-port semantics.
2. Admit diagnostic only with exact intended real-network configuration and the other snapshot/capture controls explicitly disabled. Reject conflicts before hook installation/heap registration; do not silently choose one mode. In particular, graphics runahead defaults can activate through `ra_wanted` when `SSBU_RUNAHEAD` is absent. Validate the same five-switch policy with NET deliberately changed to `net`, and retain explicit MEM_KEEP/Skyline zero. Check actual parser semantics: `SSBU_RB_SIM_VERIFY=0` is truthy by presence in its dormant configuration reader, so absence of coordinator activation, not that literal alone, is the isolation proof.
3. In initialization-only mode, fail closed when handshake is unsuccessful or bypassed, before fallback state construction. Existing `hs_apply` converts failure into a local one-stock match (`runtime/debug_mode.c:435-444`); its promised walkoff depends on disabled `rbg_pad`. A retained failure/bypass must never look like an agreed sample. Reject a second match/setup in the first version and use fresh processes, rather than adding rematch/reset semantics to this seam.
4. `rbn_init` currently runs only from `ra_init` (`runtime/r1_state.c:2639`). If preserving pre-match ping behavior is required for actual handshake timing comparability, invoke that existing function once from the diagnostic startup path. It only starts the transport ping worker (`runtime/rb_net.c:506-521`), not a capture coordinator. Do not call `rbn_start` to replace it: that establishes the gameplay epoch/input queues and match-block protocol.
5. Emit a single explicit isolation admission marker describing real handshake, local pads, no snapshot coordinator and first-setup-only scope. Retain existing successful-handshake logs/seed, observers and trace identities. Admission should reject any active capture mode rather than logging a warning and proceeding.

This seam changes diagnostic scheduling relative to enabled rollback because holds, base capture and start barrier are absent. It nevertheless exercises the same host/join handshake and original construction. It cannot prove behavior under actual rollback scheduling.

Concrete integration boundaries: validate before the first `r1_on` activation decision (`runtime/r1_state.c:108`), which also covers `r1_register_heap` callers; `runtime/nnhid.c:472,1277` invoke R1 initialization/heap registration separately. `debug_mode_init` (`runtime/debug_mode.c:660`, called from `runtime/boot.c:274`) is an available explicit diagnostic initialization point for idempotent `rbn_init`. Do not assume its order alone protects earlier R1 decisions. `hs_apply` must reject unsuccessful diagnostic return immediately after its `rbn_handshake` call, before both the cancellation-2 bypass and local fallback. Count setup at `idx==0`, not each player-record call, so entry 1 remains valid.

The player-record hook currently uses generic `hook_install` (`runtime/debug_mode.c:673`, `FN_PLAYER_RECORD=GA(0x7101788260)` at line 384), as does the auto-player-2 copy hook at line 670. For the diagnostic's claimed real path, require pinned 13.0.5 identity/unique resolution and fail closed on either required hook failure, using the existing required-hook facility where applicable. Do not infer hook installation from handshake configuration or silently admit a missing hook. Keep default-path behavior unchanged unless separately justified.

## Pads, epochs and lifecycle boundaries

`runtime/nnhid.c:534-548` uses `r1_net_on` solely here to report port 2 connected; `runtime/r1_state.c:2776` maps that to `rbn_on`. Preserve it so original construction sees the same connected-player topology. With R1 off, `fill_pad` skips `r1_poll`, `r1_pad` and `r1_pad_id` (`runtime/nnhid.c:596-599,654-655`); therefore no remote pad exchange, prediction, input delay or role remapping occurs. Local script still drives port 1 on both peers; port 2 can receive local physical input unless scripted-device controls suppress it. Require neutral/disconnected live devices and a declared identical local-pad fixture, or stop inference at pre-gameplay initialization boundaries.

The ring coordinator creates gameplay frame zero, calls `rbn_start`, exchanges start/barrier state and emits `matchNon` (`runtime/rb_rollback.c:144-186`). None happens in the proposed diagnostic. Existing scripts waiting for `@match1on` will hang; use existing `@fight`/forward trace intervals and explicitly label their epoch. Do not manufacture a `match1on` mark or network checksum qualification. Match-block exchange/checksum finalization driven by `rbn_start`/`rbn_drain` is likewise absent.

`rbg_fight_off` owns session reset (`runtime/rb_rollback.c:373-391`), which will not run. Fresh-process, one-setup admission avoids claiming rematch behavior. Host seed cache remains nonauthoritative for current agreement, as previously established. This seam neither restores state nor re-applies seed during a restore.

## Rejection tests and game scope

Before building, independently review exact runtime diff. Source-extracted executable tests should exercise production predicates/callers, with fatal paths recorded rather than terminating the fixture:

- Default unset/zero diagnostic preserves existing NET/SIM/RUNAHEAD/R1 activation.
- Diagnostic+real NET and explicit off controls yields `rbn_on=1`, `rbg_on=0`, `rgs_wanted=0`, `ra_wanted=0`, `r1_on=0`; `r1_init` takes only existing trace-only path. Verify heap registration likewise stays off.
- Conflicting R1/SIM/RUNAHEAD/graphics default, disabled NET, loop, disabled handshake and malformed diagnostic settings refuse before any capture or hook registration. Test exact configured capture switches rather than generic string assumptions.
- Successful handshake traverses unchanged `hs_apply` writes and original record builder; failed/bypassed handshake does not enter local fallback; second setup refuses. Ensure both player-record calls for the same setup remain legal.
- Receive dispatch still reaches handshake handlers; connected port 2 remains present, while neither pad callback enters `rbg_pad`. Ping initialization runs once if retained; `rbn_start`, ring capture/load, watchdog and match reset are never entered.

The first game decision is whether successful handshake-normalized initialization survives differing pre-match histories. Equal selector-entry/owner/reset endpoints retain the current synchronization boundary. Different entry after agreement restricts audit to handshake-to-selector; equal entry/different output restricts it to original branch/owner transfer. Neither result requires another late seed override.

Run identical seed/history paired baseline before a differing-history pair, then a second explicit nonzero seed and repeated uninstrumented counterparts. Preserve identities, complete logs, fatal and sealed-trace completeness gates, exact agreed seed/roles and branch inputs. Historical original-reference comparison remains separate and cannot be waived because the handshake deliberately changes initialization. A new fixture must be justified by original construction semantics and uninterrupted behavior. Local identical-pad 500R/0S evidence can support an initialization/forward fixture, **not network input correctness, rollback, or complete-state equality**. Mandatory replay gates remain mandatory for the subsequent actual rollback packet, not satisfied by this zero-replay diagnostic.

Fresh paired-process resource admission must cover both games; existing one-game reserve is not automatically a two-process budget. No game is authorized by this report alone as admitted. Preserve existing admission failures, M7.8 resource acceptance and M7.1 membership/publication prerequisites. If two processes cannot be safely admitted, source acceptance of this seam is the finite stopping point until capacity is available.

Retrospective: activation names obscure that NET implicitly enables R1 despite explicit zero switches. A single checked isolation mode and a test covering the full activation chain can enable the missing initialization comparison without expanding the restore implementation or weakening its acceptance gates.
