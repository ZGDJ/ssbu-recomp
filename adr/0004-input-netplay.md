# ADR-0004: Input-driven local battle

Historical status (partially superseded by ADR-0007 on 2026-10-21): proposed; library/protocol/topology deferred. Date: 2026-10-18.

Migration note (2026-10-21): the historical text below describes the WindowSmash planning baseline. [ADR-0007](0007-opensmash-adoption-and-hardening.md) supersedes its deferred backend/representation and GGPO-first assumptions where applicable; ownership, safety and qualification requirements remain in force.

Context: inherited Local Wireless forwards session traffic, not a rollback interface.

Proposal: two logical inputs drive a local battle on each PC, coordinated by a separate rollback session. Reuse lobby concepts only where compatible; avoid competing battle synchronization systems.

Alternative: retaining Local Wireless battle progression requires reverse-engineering its delays/timeouts/state. Local mode instead requires two input lanes and reproducible initialization; its semantic equivalence needs proof.

Consequences: design to the GGPO reference contract now ([ADR-0006](0006-ggpo-contract-and-slippi-methods.md)); adopt/pin the actual library only after offline gates. A library cannot supply missing engine state/stepping. No transport dependency chosen by this proposal. Prove confirmation-horizon access rather than assuming a public getter; choose an alternate backend only with documented evidence.

Promote after local two-input simulation, rewind/correction and performance pass, with [FSD-008](../docs/FSD.md) design. Reconsider if local mode changes gameplay or cannot be driven reproducibly.
