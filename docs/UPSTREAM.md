# Upstream provenance and architecture

Fork: [ZGDJ/ssbu-recomp](https://github.com/ZGDJ/ssbu-recomp). Parent: [Denkishi/ssbu-recomp](https://github.com/Denkishi/ssbu-recomp). Audited baseline: `c7c874977ea7510c291ec8c278a58883a2f4e368`.

`origin` is the fork; `upstream` is the parent. Never automatically reset/merge upstream; revalidate hooks, state and replay after relevant changes. Preserve [README-UPSTREAM.md](../README-UPSTREAM.md), [LICENSE](../LICENSE), credits and contribution rules. This upstream has a project license and real experimental rollback.

Planning provenance: [WindowSmash at cb110e7](https://github.com/ZGDJ/WindowSmash/tree/cb110e7e0638acd126fdbe16da5e4011f8e966cf). Requirements, ADR history, workflow, validator and ledger identities migrate. Runtime/build fixes, baseline utilities and their results do not. See [migration evidence](../evidence/2026-10-21-migration.md).

## Source seams

- [rb.h](../runtime/rb.h), [rb_input.c](../runtime/rb_input.c), [rb_wire.c](../runtime/rb_wire.c), [rb_timesync.c](../runtime/rb_timesync.c): input history, prediction, packet format and pacing.
- [rb_net.c](../runtime/rb_net.c): handshake, receive queues, match identity, confirmation and checksums.
- [rb_rollback.c](../runtime/rb_rollback.c): checkpoint selection, resimulation, progress limits and teardown.
- [r1_ring.c](../runtime/r1_ring.c), [r1_state.c](../runtime/r1_state.c), [rb_learned.c](../runtime/rb_learned.c): page history, native continuations, protected-page learning and exclusions.
- [nnhid.c](../runtime/nnhid.c): input consumption; [fighter_host.c](../fighter_sdk/fighter_host.c): limited fighter hash feed.
- [setup.py](../scripts/setup.py), [lifter tools](../tools/lifter): build/translation; follow [BUILDING.md](../BUILDING.md).
- [rb_test.c](../tests/rb_test.c): game-free toy simulation, not engine proof.
- [lobby test](../tools/net/test_ssbu_lobby.py): loopback room/matchmaking/relay checks, not rollback proof.

The [audit](ROLLBACK_AUDIT.md) maps failure paths to hardening tasks. Existing native-state code is a candidate implementation, not proof of a safe boundary. Upstream measured-match claims remain attributed reports until reproduced with our fixture/build identities.
