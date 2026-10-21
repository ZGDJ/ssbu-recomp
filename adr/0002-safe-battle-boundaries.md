# ADR-0002: Explicit continuation coverage

Historical status (partially superseded by ADR-0007 on 2026-10-21): accepted constraint; snapshot representation deferred. Date: 2026-10-18.

Migration note (2026-10-21): the historical text below describes the WindowSmash planning baseline. [ADR-0007](0007-opensmash-adoption-and-hardening.md) supersedes its deferred backend/representation and GGPO-first assumptions where applicable; ownership, safety and qualification requirements remain in force.

Context: native stacks/fibers, host thread/wait tables and setjmp/device state extend beyond guest RAM.

Decision: capture only at quiescent battle boundaries with documented invariants for every authoritative continuation. Inventory restored/reconstructible/excluded state. Compare replay with uninterrupted references. Do not discard GPU/event work merely because it looks graphical.

Alternatives: broad committed pages may help once host coverage is solved; selective serialization needs ownership knowledge; explicit resumable execution/deterministic scheduling is a fallback. No format selected yet.

Consequences: discovery gates implementation. Reconsider when changing worker/fiber state survives boundaries or services cannot be reconstructed; create a design ADR before altering execution semantics. See [FSD-002/005/006](../docs/FSD.md).
