# ADR-0008: Private pair sessions independent of lobby membership

Status: accepted product direction; implementation and qualification pending. Date: 2026-10-22.

## Context

The owner prioritizes reliable private wireless 1v1 rollback, without required public search or a public relay. Owner scope update: first delivery targets a controlled two-person private versus session and rematches. Persistent four-member membership, pair changes and up to two delayed live spectators follow as a later product phase. There is no automatic rotation schedule. Simultaneous 3-4-player battles remain deferred. The implementation is location-independent; geographic examples are test scenarios only. [Network audit](../evidence/2026-10-22-private-network-audit.md) distinguishes the inherited ordinary direct transport from the rollback route.

## Decision

Keep ADR-0007's provisional checkpoint engine and custom rollback coordinator. Use the versus battle simulation with a controlled private 1v1 setup flow. Qualify a private host/join pair first. Separate lobby membership, selected battle participants and packet route; the host of a social lobby need not be a battle participant or forward battle inputs.

The first supported route must exchange the active pair's rollback messages without a third-party relay or public matchmaking dependency. The embedded host mini-lobby is a candidate implementation, not grounds for a rewrite by itself. Measure its local dispatch cost before replacing it. Local-network connection must work without external STUN/UPnP services; cross-household reachability must have explicit failure diagnostics and separately qualified NAT/manual-forwarding behavior. Optional rendezvous/relay support may follow, but must not silently replace a requested direct route or become mandatory for correctness.

Use a small concrete pair-session contract: selected peer identity, full session/match epoch, slot/profile mapping, readiness, send/receive, route status and closure. Bind received messages to the selected peer before handshake or input processing; a player field in a payload is insufficient. Preserve received inputs and connection state across battle rewinds. Reuse existing socket/codec/lifecycle code where it satisfies this contract; do not build a general plugin framework or duplicate transport stack.

Keep exactly two active input lanes for this release. Spectators neither send battle inputs nor contribute to the confirmation horizon. Rotate only after terminal commitment or explicit session abort/cleanup. Start each new pair with fresh identity, input queues, timing state and readiness. Initially abort/close a lobby clearly when its owner leaves; automatic host migration is not required. Delayed spectating is mandatory for the later four-member product, not for the initial two-person version. Publish only corrected committed inputs, with bounded independent viewer queues and retention. Viewer backpressure must shed viewer work, never delay fighters. FSD-018 defines bootstrap, recovery and performance gates. Simultaneous multiplayer remains deferred.

The lobby controller coordinates membership, code, active-pair readiness and spectator assignment; it never approves simulation frames. Initially host it in the creator's game. A separate server is optional future deployment, not a prerequisite or paid-resource authorization. Preserve one lobby/code through pair changes without manual rehosting. Any internal pair endpoint change is automatic. Normal setup uses the in-game F1/versus flow, not mandatory file editing. Do not take on Local Wireless rollback integration.

## Controlled 1v1 setup and diagnostics

Create/join a private session, assign exactly two human-controlled battle slots, let each player select their fighter, apply one supported host-selected rules preset on both PCs, and return to the same session after committed results for rematch. A CPU panel in the inherited select screen is a temporary setup workaround, not a gameplay requirement or a user-facing step. Validate slot ownership and absence of AI input before admission. Synchronize explicit supported settings including timer, stock/rule type, stage/form, hazards, items, fighters/costumes and per-player control profiles; verify applied configuration and initialization on both sides before the first speculative tick. Unsupported or mismatched settings refuse visibly. Initial scope may use a narrow declared preset. Actual Online/Battle Arena and Local Wireless rollback integration remain deferred; menu presentation is independent of simulation choice.

Paired test evidence must be easy to export outside the game, including while it is frozen. Extend the existing family support tooling with a dedicated rollback launcher/collector and an agent-readable manifest; preserve setup support. Each peer exports its own bounded, sanitized ZIP for manual sharing, with shared session/match identity where available and explicit gaps for legacy runs. Show the active mode and reason when rollback is unavailable; a fallback has separate qualification and cannot be reported as rollback. See FSD-019 and the diagnostics implementation prompt. A branch push distributes source, not a qualified runtime or automatic family update.

## Alternatives

Retaining unqualified lobby coupling risks sending rollback through an external endpoint despite ordinary direct status, and treating a waiting member as an opponent. Replacing everything with GGPO would not fix checkpoint correctness or by itself supply private connectivity. Building simultaneous four-player rollback now adds independent coordination/performance scope before the two-player foundation is proven.

## Consequences and validation

FSD-016/017/018 and M5.4-M5.11 make route and rotation requirements explicit. Source transport tests may proceed beside M7, but do not close M2-M5 actual-battle gates. Preserve the existing Local Wireless behavior: it bypasses rollback by default; private rollback UI must not imply otherwise. Test active-peer binding, old epochs, reconnect/reset, malformed/duplicate/reordered packets, route failure and no-public-service operation. Measure rollback-specific end-to-end RTT, jitter, loss, stalls, correction depth, catch-up and memory on separate PCs including Wi-Fi. Do not promise that direct is universally fastest or that receipt alone proves corrected state.

## Reconsideration triggers

Revise this decision if measured host dispatch/routing cannot meet the supported budget, peer binding cannot be made reliable within existing ownership, or required family networks cannot establish the declared direct route. Document evidence and explicit fallback tradeoffs. ADR-0007's engine replacement triggers still apply. Neither lobby conveniences nor additional players may weaken correctness gates.
