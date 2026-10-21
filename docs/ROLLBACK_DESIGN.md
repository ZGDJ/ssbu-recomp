# Smash rollback ownership and hardening contract

This is the design/acceptance companion to [FSD](FSD.md). OpenSmash upstream `c7c874977ea7510c291ec8c278a58883a2f4e368` already implements experimental rollback; this document distinguishes its mechanisms from the proof still required. [ADR-0007](../adr/0007-opensmash-adoption-and-hardening.md) provisionally retains that custom backend. [ADR-0006](../adr/0006-ggpo-contract-and-slippi-methods.md) remains historical context for ownership and research, with its GGPO-first adoption assumption superseded. External sources below were inspected on 2026-10-18; they are methodological references, not claims of a dependency installed here.

## Existing implementation and source hardening

`r1_state.c` and `r1_ring.c` own checkpoint/continuation machinery; `rb_rollback.c` coordinates capture and rerun passes; `rb_input.c` retains actual/predicted inputs; `rb_wire.c` encodes messages; `rb_net.c` owns session, receive queues and diagnostic checksums. `os_threads.c`, `nnaudio.c` and the NVN backends contribute state and external effects. Existing native-stack/fiber handling is an implementation to validate, not proof of complete restoration.

M7 source packets address these observed risks without replacing M1–M6 qualification:

- **M7.1:** complete-or-refuse restore: validate all required state before mutation, or fail the session if atomic refusal cannot be guaranteed; no partial-success restore.
- **M7.2:** retain terminal-state recovery until corrected causal inputs permit exactly-once outcome commit; the inherited fight-off path currently releases the ring immediately.
- **M7.3:** never discard an unrecoverable mismatch and finalize its simulation; stop with a bounded diagnostic failure.
- **M7.4:** require full match epochs and admissible frame windows; reject missing/malformed epochs and far-future ring overwrites.
- **M7.5:** distinguish transport heartbeat from simulation/input progress; bounded stall/disconnect instead of endless waiting or indefinite guessed play.
- **M7.6:** define authoritative hash coverage and enforce desync failure. Current fighter-summary/pad hashes are telemetry, not complete state proof; do not equate received-input horizon with corrected/validated commit horizon.
- **M7.7:** reject incompatible executable/runtime/module/content/rules/input identities before starting; game-build integer and link-time warning are insufficient.
- **M7.8:** learned-page and allocation failures cannot silently omit required checkpoint state; exercise controlled exhaustion and restore coverage.

Each packet requires source regressions and independent review where appropriate. Actual-battle confirmation, equivalence, coverage, performance and two-machine evidence remain separate gates.

## Frame and ownership contract

Project convention: `S[f]` is authoritative state immediately before consuming both players' input `I[f]`; `step(S[f], I[f]) = S[f+1]`. The inherited ring labels state after pass n as frame n and calls its first capture frame 0: ring frame n corresponds to S[n+1] when inputs begin at 1. Its correction at input f loads a ring state at or before f−1 and reruns forward. Verify this mapping at late-base and rematch boundaries; if GGPO is later adopted, document its callback mapping separately. Save an initial checkpoint before any speculative input. Correcting input at f restores S[f], then reruns every affected tick exactly once in order. Presentation count and fighter animation advancement are separate from this clock; hitlag/freeze does not imply a stopped network frame.

Checkpoint capture is at the proven quiescent boundary, not arbitrary native execution. Include authoritative input history, pending commands, simulation counters, RNG, allocation/object identity and native continuation invariants. Input records and confirmed-input receipt history used by the coordinator survive a simulation rewind. Never rewind sockets, acknowledgments or already-received corrected inputs with battle RAM.

Define three separate horizons: simulated state, latest actual input available for every player, and frames eligible for irreversible commit. Receipt/ACK alone does not prove corrected simulation has been rerun and validated. The implementation must define a conservative commit rule and how it obtains that signal; the public GGPO interface inspected does not expose a generic confirmed-frame getter. Do not invent one.

Checkpoint buffers remain immutable and valid until their owner releases them. Restoring cannot invalidate retained snapshots through aliasing. Define allocation failure, stale snapshot, double-free and session-close behavior. A K-tick correction horizon generally needs the current boundary plus K prior boundaries in a simple per-tick ring; derive exact retention from chosen frame convention, input delay and backend, and test oldest-boundary access. Never evict state still needed by an accepted correction.

## Implementation boundaries

Preserve the current C/HLE runtime. Expose and validate input, one tick, capture, restore and diagnostics through the inherited offline and network drivers, avoiding duplicate simulation paths. The engine owns authoritative state; the coordinator owns input receipt/history, prediction and confirmation; host services own external effects. A checkpoint must not capture the coordinator or sockets. Keep device polling outside replay and effect policy outside the transport.

Do not choose a generic snapshot framework, replacement scheduler or transport abstraction ahead of measured failures. Inventory the existing selective/learned-page snapshot ring and prove every exclusion. Retain optimizations only with coverage and profiling evidence; do not replace the representation simply because the previous plan deferred it. Offline and network coordinators must use the same battle stepping path.

During M2 boundary discovery, trace `runtime/nvn_gl.c` / `runtime/nvn_vk.c` submission/completion, `runtime/nnaudio.c` audio queues/events and `runtime/os_threads.c` clock/wait/continuation behavior. Skipping display or muting audio must not prevent guest-visible completion or substitute wall-clock-dependent results during catch-up. Compare audio-device-present/absent and presentation-enabled/suppressed paths. Record service queues and completion state in the ownership inventory; avoid assuming they are cosmetic.

## Optional future GGPO adapter obligations

The following library-specific calls apply only if a later ADR adopts GGPO. They are not commands for the inherited backend. Save/restore ownership, deterministic inputs, replay diagnostics and safe confirmation apply regardless of backend.

The pinned [public API](https://github.com/pond3r/ggpo/blob/7ddadef8546a7d99ff0b3530c6056bc8ee4b9c0a/src/include/ggponet.h) requires save/load/free and diagnostic callbacks plus one-frame advancement and event handling. Use `ggpo_synchronize_input` (singular in this header) for normal and replayed frames. Notify `ggpo_advance_frame` only after a successful tick. Replay uses historical synchronized input, not fresh device sampling or resubmission. Service `ggpo_idle`; respect synchronization/prediction errors. Handle time-sync and disconnect events without changing simulated tick duration. Frame delay and prediction horizon are distinct settings.

Use a deterministic, fixed-size input encoding with initialized bytes and explicit player mapping. Record startup configuration and seed/state agreement independently of network connection success. Avoid reentrant session calls from arbitrary workers; define one coordinator thread and callback ordering/ownership before implementation. These are project integration constraints, not claims that all runtime jobs must be serialized.

The [developer guide](https://github.com/pond3r/ggpo/blob/7ddadef8546a7d99ff0b3530c6056bc8ee4b9c0a/doc/DeveloperGuide.md) requires deterministic simulation, encapsulated state and simulation without rendering. Our GPU service may still need guest-visible work during a non-presenting tick; proving that separation is our responsibility.

Use forced offline restore/replay testing before networking. Once the library is integrated, exercise [GGPO's synctest backend](https://github.com/pond3r/ggpo/blob/7ddadef8546a7d99ff0b3530c6056bc8ee4b9c0a/src/lib/ggpo/backends/synctest.cpp) with deterministic checksums and readable state diffs. Also retain independent uninterrupted/all-correct oracles and upstream behavior comparisons: backend self-consistency cannot establish original gameplay accuracy. Synthetic adapter tests do not close actual-battle gates.

## Ultimate-specific fixture obligations

These are investigation/test categories, not assertions about undocumented Ultimate structures, addresses or exact sampling cadence. Pin all cases to 13.0.5 and record the discovered implementation.

- **Input history:** press/hold/release edges, buffered actions, analog transitions, player mappings and per-player profiles. Trace polling/consumption before assuming one sample suffices. If meaningful ordered subsamples exist, encode them; do not discard them to fit a preferred API. Store authoritative game-side previous input/buffer/counters in checkpoints. Test late corrections around hitlag and DI/SDI-sensitive sequences against gameplay outcomes, not only tape bytes.
- **Combat state:** shields/parries, hitlag/hitstun, launch/landing/tech/ledge transitions, grabs/throws and repeated-hit interactions. Discover authoritative counters, collision history, hit eligibility and motion/script state; do not snapshot only position/damage.
- **Object and fighter lifetimes:** corrections that create or prevent spawning, destroy/recreate objects, change ownership and alter future allocations. Include companions/multiple battle entities, transformations, resource meters, delayed actions and RNG-dependent mechanics wherever present in the selected roster. One-v-one means two players, not necessarily two authoritative objects.
- **Initialization:** preload/complete required modules/assets before a shared ready barrier, or make later authoritative loading deterministic. Pin fighter variants/Mii moves, stage forms, rules, control profiles and seeds; each player's chosen profile must be represented consistently on both peers, not necessarily identical to the other player's profile.
- **Match end:** incorrect last-stock KO corrected to survival, changed simultaneous-KO result, timeout/last-hit changes and disconnect while an outcome is speculative. Defer module/object teardown, results publication, saves and irreversible transitions until the causal frame is safely committed, or prove the transition is rewindable. Do not leave this gap under the phrase 'transitions outside rollback.'
- **Repeated correction:** multiple overlapping late inputs, repeated restores of one boundary, oldest retained checkpoint, rejected too-old corrections, and long-run resource growth. Preserve failing tapes and first divergent subsystem.

Select a small explicit mechanics fixture set before M4.1; exhaustive roster qualification remains M6.2. Every listed mechanic becomes a verified case or a documented not-applicable entry for that fixture. The full product still requires all roster entries and declared interaction classes.

## Effects, session boundaries and failure policy

Maintain an event policy for audio, rumble, camera/UI, file writes and network output: deferred, deduplicated, reconstructed or intentionally speculative. Audio already heard cannot be erased; document that artifact instead of promising impossible cancellation. Execute all gameplay-affecting work while suppressing intermediate presentation. Compare rendering-enabled and presentation-suppressed authoritative hashes, then separately inspect audiovisual behavior.

Agree initial state before advancing; build identity is insufficient. Match/session epochs reject late packets from a previous match, especially immediate rematches. Test initial-hash mismatch, old-epoch packets, temporary interruption, prediction cap, resume, disconnect and peer frame skew. Apply pacing outside simulation; no variable gameplay delta time to compensate for lag. A checksum mismatch must produce a bounded diagnostic failure, not silent continued 'healthy' play.

## What to learn from Slippi

The project's [component overview](https://github.com/project-slippi/slippi-wiki/blob/master/GETTING_STARTED.md) places rollback across game assembly modifications and emulator code. Our analogous division is battle hooks plus a host rollback coordinator. This supports targeted integration; it does not establish Ultimate feasibility.

The pinned [SlippiSavestate.cpp](https://github.com/project-slippi/Ishiiruka/blob/60f7b63496fb6ec7b9180a04f16f3edc0ad89fe2/Source/Core/Core/Slippi/SlippiSavestate.cpp) selects memory regions, computes heap bounds and preserves excluded blocks during restore. Learn the process of proving state coverage and optimizing only measured exclusions. Its active capture path should not be described as a generic complete Dolphin snapshot. Do not copy Melee addresses/exclusions into Ultimate or infer that audio is universally safe to omit. OpenSmash must qualify its own native stack/fiber/service implementation.

The pinned [SlippiNetplay.cpp](https://github.com/project-slippi/Ishiiruka/blob/60f7b63496fb6ec7b9180a04f16f3edc0ad89fe2/Source/Core/Core/Slippi/SlippiNetplay.cpp) handles frame-indexed input queues, acknowledgments and frame-associated checksums. The [EXI integration](https://github.com/project-slippi/Ishiiruka/blob/60f7b63496fb6ec7b9180a04f16f3edc0ad89fe2/Source/Core/Core/HW/EXI_DeviceSlippi.cpp) distinguishes finalized frames and stalls for unavailable input beyond a bounded window. Transfer the disciplines of bounded history, finalization and pacing; derive our limits experimentally. Do not copy Melee delay/window constants or its emulator timing.

These inspected components show a custom game/emulator integration; they are not evidence that Slippi is a GGPO drop-in or that its networking can be copied unchanged. GGPO callback conformance and Slippi-inspired engineering are separate ideas. No third-party code is copied or dependency added by this audit; check applicable licenses before any later reuse.
