# Rollback continuation handoff

Updated 2026-10-22 after implementing and reviewing handshake initialization isolation. Branch `feat/rollback-validation-audit`; tested packages were built from dirty base `38550dda6b0a926366cc37eec0f5c26e4776d043`. This packet includes the inherited observer/runtime and documentation changes; inspect actual HEAD when continuing. Committing it does not change the recorded build provenance. The [ledger](../milestones/README.md) alone owns status; follow [workflow](AGENT_WORKFLOW.md) and [validation](VALIDATION.md). Use the [continuation prompt](ROLLBACK_NEXT_PROMPT.md) to resume.

## Current decision

[Integrated contract evidence](../evidence/2026-10-22-battle-initialization-contract.md), [Astra A ownership](../evidence/2026-10-22-battle-seed-ownership.md) and [Astra B challenge](../evidence/2026-10-22-battle-seed-boundary-challenge.md) establish:

- Successful network setup already publishes the agreed seed and synchronizes OS/global RNG plus stage context/history before original construction. Offline fixed-seed timing evidence does not prove this network path defective.
- Original selector input+0x98 with flag+0x9c cleared controls the ordinary seed-retention path. Selected-record paths may replace it independently; mode zero alone is not a guard. Skipping the draw also changes global consumption.
- Original constructor transfers that input through owner+0xf8; original later resets correctly use the owner. First-fighter vector rewriting is nonauthoritative and discards original state/consumption. A late owner/vector patch cannot repair earlier choices.
- Cached g_hs_seed survives match reset. A future override must require current successful setup, not merely a nonzero seed. Rematches and snapshot restoration require separate lifecycle evidence.

Root implemented the opt-in initialization diagnostic, completed source tests and fresh independent review, and built an isolated package. No games ran. This enables a missing experiment; it does not correct or qualify seed selection. See [isolation evidence](../evidence/2026-10-22-handshake-isolation.md). M1.1/M1.4/M1.2/M1.3 retain completed scopes. M3.5/M7.8 remain in progress; M2.1 still requires M7.1/M7.8.

## Next discriminating work

Reuse the completed initialization ownership audit. M3.5's immediate offline question is how to establish reproducible battle initialization while preserving original gameplay semantics and accounting for the retained reference failures. Select the smallest supported correction or justified fixture treatment using the existing selector/owner/reset evidence. Check earlier random decisions, alternate-record selection and reset ownership; test differing pre-match histories, multiple seeds and repeated uninstrumented agreement. Preserve original references and report unexplained historical failures separately. A new observer is useful when its possible results change the correction or validation decision.

Offline forward-only progress does not wait for network readiness or blanket M7 completion. Applicable safety gates still govern capture/restore trials, and required SDK controls remain incomplete until their reference obligations are satisfied. This separation prevents network readiness from becoming a prerequisite for the offline work needed to reach it.

Separately, at network readiness, test the actual successful host/join initialization path with differing histories and multiple seeds. Equal endpoints support the existing synchronization for that tested scope; unequal entry state directs investigation to handshake-to-selector, while unequal output with equal entry directs it to selector branches/ownership. Preserve and reconcile in-flight handshake-isolation work with its owner; source audit or a new isolated candidate alone does not admit a game or qualify the network path.

The new `SSBU_RB_NET_INIT_ONLY=1` diagnostic retains the real handshake but suppresses R1/RBG activation; it uses local pads, supports only first setup and fails on bypass/failure/conflicting controls. NET must be `net`; R1/RUNAHEAD/RB_SIM/LS/MEM_KEEP/SKYLINE/AUTOP2/P2NONE explicitly `0` (use full environment names from evidence). No remote-input gameplay, snapshot or replay claim follows. The old paired launcher is unsuitable. Prepare/review a distinct identified initialization gate; unchanged `--forward-only` correctly rejects NET and must not be bypassed.

Paired capacity failed a declared conservative two-game budget of 20 GiB commit/20480 MiB physical: 10.01/10.15 GiB commit, 16371/16468 MiB physical, no games/builds. No launch token issued. Do not reuse a single-game admission for a pair. Disabled original-reference control and all enabled/history/seed/repeat controls remain unrun. M7.8/M7.1 and offline replay prerequisites remain for actual rollback qualification.

Once prerequisites hold, the next actual rollback control is an identified uninterrupted battle versus default save/advance/restore, retaining 500 real frames and mandatory exact two replay runs. Fatal, completeness, original/reference, replay and identity gates all apply. Only after passing default should refusal/correction controls and depth expansion proceed. Preserve original references; any new initialization fixture needs a declared gameplay-semantic justification and separate historical comparisons.

## Frozen candidate and preservation

Prior observer package `artifacts/local/runtime-prematch-boundary/package`: source digest `ad7389863a11b2158c97c7640fac3c4b46e9690d0ffbecc9c8c4a01d0930fa76`; executable SHA256 `5af99bfb01f143d16c65f7d36a3fd93c779f03eb4c6c86a9651cbb1278d4f7fe`. This prior package remains preserved; it does not contain the isolation mode.

New package `artifacts/local/runtime-handshake-isolation/package`: source `770a5d8c9979c83718a9e4be810089e8e184e3e1ec52213f4377156e8f267826`, executable `8b91dbf80026d0a71f952fab92623e3d86d79d7081e2a278a86ddbade01d00f8`. Configured-Python build passed in 20.390 seconds; eight package files verified. Reuse this frozen build; no game DLL was rebuilt. Fresh [candidate review](../evidence/2026-10-22-handshake-isolation-candidate-review.md) approves source only.

All 433 historical entries remain preserved. The two instruction originals remain under `artifacts/local/initialization-workflow-20261022/before/`; intentionally revised runtime inputs have exact originals under `artifacts/local/handshake-isolation-20261022/before/`. The new final verification reports original/archived locations and separately verifies both packages plus old/new source identities. The preceding handoff is archived byte-for-byte under `artifacts/local/battle-initialization-20261022/before/docs/ROLLBACK_HANDOFF.md`. New verification/closeout reports are in that packet.

The reviewed pre-wait observer remains available, with runtime controls unrun. Select it only if wait-boundary observations change a correction decision. Its [reviewed protocol](../evidence/2026-10-22-prematch-boundary.md) remains menu-disabled baseline -> enabled baseline -> single +60; preserve seed 1, fresh saves, warm-cache policy, rules, fight suffix, five rollback/capture switches plus MEM_KEEP/Skyline zero, and every original gate. Samples are non-atomic, 91/151 sequence ticks apart; recurrence distances are algebraic compatibility.

Fresh admission immediately before any selected game remains two samples 15 seconds apart: 10 GiB commit reserve, 10240 MiB physical available, <=512 MiB commit drift and no game/build process. Use configured project Python for builds and unoptimized Python for assertion-based local helpers. Root alone owns builds and serialized game slots.

## Retained failures and open obligations

Preserve [timing evidence](../evidence/2026-10-22-prematch-timing.md): original-tape baseline passed fatal/sealed 500R0S/original reference; +60 failed original reference at frame 2 RNG, with 499 differing frames. Selector inputs agreed, entry RNG differed, and b77b0413/fa10bec7 followed owner/reset observations. Pre-treatment timing/host pressure differed; wait causality and historical reconstructed f28f3988 remain unresolved.

Preserve [SDK comparison](../evidence/2026-10-22-sdk-forward-comparison.md), empty-cache startup abort, disabled-b insufficient-commit/zero-replay failure, complete traces and original/revised protection reports. Historical protection=177 is narrowed to setup 1 through initial-base validation before reuse injection. M7.8 reservation lifetime/MEM_KEEP disposition and M7.1 separate 176-to-177 membership/publication remain open. The reservation provider rejection supplied no technical result and was not retried.
