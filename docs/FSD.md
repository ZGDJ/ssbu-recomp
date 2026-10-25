# Functional specification: SmashRollback

Revision: 2026-10-22. Requirements live here; [milestones](../milestones/README.md) own status and [ADRs](../adr/README.md) own decisions.

The [Smash rollback design contract](ROLLBACK_DESIGN.md) defines frame conventions, adapter ownership, confirmation and primary-source Slippi learnings. It is required design context for FSD-002 through FSD-010 and FSD-014/015.

## Adopted implementation

OpenSmash upstream `c7c874977ea7510c291ec8c278a58883a2f4e368` supplies an experimental custom rollback implementation: `runtime/r1_state.c`, `r1_ring.c`, `rb_rollback.c`, `rb_net.c`, `rb_input.c` and `rb_wire.c`. [ADR-0007](../adr/0007-opensmash-adoption-and-hardening.md) adopts it provisionally. Existing source and upstream reports do not close our gameplay gates. M7 tracks source hardening; M1–M6 remain the independent qualification sequence. Build prerequisites are in upstream [BUILDING.md](../BUILDING.md).

## Vision and fixture

Preserve Ultimate battle behavior on Windows x64 with competitive 1v1 rollback. **13.0.5 and the full roster are the target from the start.** Keep recompiled logic and recover interfaces/state needed to control it. A frame means an authoritative simulation tick, not a presented buffer. A checkpoint must reproduce future authoritative behavior.

Provisional experiment: 13.0.5 Mario mirror, Final Destination, three stocks, seven minutes, hazards/stage morph/spirits/Final Smash meter off, normal launch rate, no items or CPU. This is a test fixture, not a universal tournament ruleset or roster limit. Add object-heavy fighters before closing rewind coverage; qualify DLC and selected Mii configurations explicitly.

Open choices: available private inputs; final stage/rules list and Mii settings; minimum hardware; acceptable input delay/window/network envelope. Source-only work can proceed; mock gameplay cannot replace missing private inputs.

Private wireless play is the product priority: first two PCs in a direct private 1v1 session without required public matchmaking/relay, then a persistent four-member code-based lobby with any two active players and mandatory delayed live spectating for the others. Offline play remains a validation mechanism, not a couch-play feature initiative. See [ADR-0008](../adr/0008-private-pair-sessions.md). Implementation is location-independent; supported network conditions are measured, not defined by cities. Same-network and Internet routes need separate qualification.

## Requirements

### FSD-001 - Reproducible baseline

Record source/diff identity, executable/toolchain/config hashes, module/content identifiers, fixture and tape. Acceptance: reproducible 13.0.5 build and three consecutive scripted offline matches including KO, respawn and return to menu. Tooling can precede private inputs; gameplay acceptance cannot be waived.

### FSD-002 - Simulation stepping and safe boundary

Advance one battle tick, then quiesce authoritative jobs; document native thread/fiber continuation invariants. Initially keep loading/match transitions outside the rewind window. Acceptance: 600 commanded ticks produce 600 simulation steps independently of rendering cadence, with no outstanding authoritative mutation at capture. A present counter is not a tick oracle.

Keeping transitions outside the window requires FSD-015's confirmation barrier; it does not permit speculative teardown. Tick/input semantics must remain correct across hitlag/freeze/slowdown, independently of visible animation.

### FSD-003 - Two frame-indexed input lanes

Version both players' buttons/sticks/sampling metadata and profile mapping. Discover the meaningful polling/consumption cadence before enforcing one sample per tick; preserve ordered subsamples if needed. Never poll live devices during historical replay. Acceptance: independent player control, correct press/hold/release/buffered-input history, and gameplay outcomes invariant under host input changes/display cadence, including corrections around hitlag and DI/SDI-sensitive fixtures. Checkpoint game-side input history/counters as authoritative state.

### FSD-004 - Deterministic forward replay

Investigate time, RNG, scheduling, FP and loading. Acceptance: two 10,000-tick replays from identical state/inputs agree every tick, first locally then in separate processes. Cross-machine qualification is FSD-009. Justify hash exclusions and pointer normalization; pixels are not the authoritative oracle. Preserve first-divergence reports. This sample does not prove all gameplay.

### FSD-005 - Complete checkpoints

Inventory guest memory, allocators, scripts, fighters/articles, stage, RNG, queues, clocks/jobs, native stacks/fibers/handles, GPU writes and audio. Classify each as restored, reconstructible or excluded with evidence. Acceptance: save/advance/restore/replay equals an uninterrupted oracle at depths 1/2/4/8 for at least 100 boundaries each, covering attacks, grabs, hitstop, projectiles, allocation churn and KO/respawn. Include object-heavy fixtures. Prove native continuation coverage; heap-plus-Cpu is not presumed sufficient.

Include speculative spawn prevented by correction and absent spawn created by correction, destruction/recreation/ownership changes, future allocation identities and RNG advancement. Test companions/multiple entities and relevant transformation/resource mechanics through named fixtures. Coordinator receive/ACK/input history survives restoration; do not rewind it with simulation state.

### FSD-006 - Prediction correction and effects

Correct deliberately wrong remote inputs after 1/2/4/8 ticks. Acceptance: match an all-correct reference at every corrected boundary; no duplicate gameplay/audio events, speculative save/network writes, stale resources or deadlocks. Suppress intermediate presentation while retaining needed GPU writes/events. Event logs and documented audiovisual inspection prove different aspects.

Test overlapping corrections, repeated restores and oldest retained state with bounded resource growth. Compare presentation-enabled and suppressed authoritative hashes. Specify effect deferral/deduplication/reconstruction and permitted speculative artifacts: sound already heard cannot be undone. No replay-induced duplicate effects is a requirement; impossible erasure is not.

### FSD-007 - Performance and memory

Measure checkpoint size, capture/restore, simulation, presentation, p95/p99 catch-up and peak memory. Target 60 Hz (~16.67 ms/display interval). Acceptance: agreed hardware floor/window and declared budget met in heavy scenes. Eight-tick correctness tests do not promise an eight-tick performance envelope. Unresolved hardware/window blocks release. No FPS-only acceptance.

### FSD-008 - Versioned rollback session

Qualify the inherited frame-numbered inputs, prediction caps, delay, acknowledgments/redundancy, bounded history, validation/checksums and disconnects after the offline gates. Source hardening may proceed independently of those gameplay gates. Handshake compares runtime/executable/module/content/rules/input-schema identities, not just main build ID. Acceptance: incompatible peers reject before battle; confirmed state matches the offline oracle; missing input causes bounded stall/abort. The inherited custom backend and relay topology are provisional; production suitability remains unproven.

Apply the ownership and confirmation contract to the inherited backend; do not add a competing GGPO transport merely for API conformity. Agree seeded initial battle state and readiness, explicit slot/profile mapping and a match epoch. Test old-epoch packets during rematch, initial-hash mismatch, time-sync/frame skew, interruption/resume and disconnect during speculative end. Pacing must not change gameplay tick duration. Obtain a valid confirmation horizon through the chosen adapter; connection success or receipt ACK is insufficient. Desync causes a bounded diagnostic failure.

### FSD-009 - Impairments and cross-machine proof

Reproduce delay, jitter, loss, duplication, reordering and bursts. Initial test cases: RTT 0/50/100/150 ms, jitter 0/10/30 ms, loss 0/1/3 percent; these are tests, not support promises. Acceptance: declared pairwise cases across two machines maintain confirmed-state agreement and latency/disconnect policy. Preserve failing seeds; qualify CPU/GPU/compiler differences explicitly.

For the two-PC gate, export paired diagnostic bundles with a shared match ID, build/config identity, frame-correlated inputs and rollback events, and comparable confirmed-state fingerprints with declared coverage. Recording must be bounded and unable to stall gameplay; report dropped/incomplete records explicitly. Begin with manual export/sharing. Upload services and dashboards are deferred; this requirement does not expand M1.1's prelaunch inventory scope.

### FSD-010 - Full-roster competitive coverage

Enumerate 13.0.5 fighters including DLC/selected Mii configurations and version rules/stage coverage. Acceptance: every fighter has representative mechanics, gameplay, rewind/correction and performance evidence; define pairwise/high-risk interactions without claiming every matchup from one test per fighter. Track untested/failed/verified. Full-roster milestone stays open until every entry qualifies. No items does not remove fighter-created objects/RNG.

Select explicit early input-history, combat, lifecycle/RNG and terminal-event fixtures before the first rewind gate; see design contract. The [13.0.5 roster matrix](ROSTER_MATRIX.md) records the selected planning cases, provisional rules and untested qualification entries. Mark non-applicable mechanics with reasons. Preload required modules/assets before ready or prove deterministic later loading. Full-roster coverage remains distinct from the initial fixture set.

### FSD-011 - Hooks and safe artifacts

Critical hooks uniquely match pinned module identity or disable rollback with an actionable error. Acceptance: missing/ambiguous/changed-signature negative tests; source CI requires no private data; evidence sanitized. Preserve notices and resolve distribution policy before release. No generated game code or dumps in Git.

### FSD-012 - Verifiable autonomy

One ledger, dependency gates, bounded packets and evidence-backed status. Acceptance: new agents identify ready work, run checks and leave reproducible handoffs. Validator rejects invalid task/dependency/status/evidence references; it cannot certify gameplay truth. Independently review high-risk state/scheduling work.

Every new work packet identifies a concrete defect or named next gameplay proof, a decisive observation and a stopping condition. Reuse verification infrastructure; optional hardening does not outrank evidence needed for deterministic battle/correction. Source safety acceptance and gameplay gates remain mandatory.

### FSD-013 - Preserve battle behavior

Self-consistent replay can still reproduce an incorrect simulation. For changes affecting battle semantics, compare representative mechanics/outcomes with the pinned upstream 13.0.5 recompilation wherever practical, using identical conditions and documenting instrumentation/input differences. Acceptance: named behavioral cases and reference outputs, no unexplained changes in damage/timing/movement/collision outcomes, and explicit limitations for unavailable comparisons. Unresolved unexplained changes block qualification. This does not assert equivalence to console hardware; upstream bugs remain separately identifiable.

### FSD-014 - Backend ownership and forced replay diagnostics

Map the inherited after-pass ring numbering to before-input checkpoint numbering; define save/load/free/log/step/event ownership, immutable buffer lifetime, coordinator-thread/reentrancy rules and fixed deterministic input encoding. Acceptance: boundary/ownership tests cover initial state, retained buffer aliases, allocation failure, oldest checkpoint and session cleanup; actual battle forced restore/replay uses the same stepping interface. On GGPO adoption, run its synctest backend and verify failed synchronization/prediction does not advance simulation or resubmit fresh input during replay. GGPO adoption is optional under ADR-0007; forced replay and ownership checks apply to the existing backend now. Record exact backend/dependency revision; synthetic callbacks do not certify battle correctness.

### FSD-015 - Confirmation-safe lifecycle

Speculative last-stock KO, simultaneous lethal outcomes and timeout/last-hit changes must remain correctable. Defer teardown/results/save/module unload until causal inputs have been corrected and the outcome is committed, or prove all transition state rewindable. Acceptance: offline late-input tests reverse apparent terminal outcomes, preserve required state/resources and commit exactly once; networking subsequently tests disconnect and immediate rematch/old epoch. A fabricated offline confirmation schedule tests the barrier but does not prove the network confirmation signal.

### FSD-016 - Private pair ownership and observable routing

A battle binds exactly two explicit participant identities independently of lobby ownership, discovery service and controller slots. Preserve source identity through receive dispatch and reject nonparticipants before handshake, liveness or queue mutation. Use fresh full-width session/match identity and reset peer/timing/input ownership coherently. Acceptance: production-connected tests prove selected pair isolation against a third sender and old-pair traffic, including malformed packets and reset races. Reuse existing transport code where justified; no generic framework is required.

Qualify private host/join without a public matchmaking/relay dependency. Same-network operation must not require external address-discovery services. Display actual rollback packet route and end-to-end timing, not merely ordinary online direct status. Direct-only failure is explicit; optional relay requires deliberate selection. Two-machine evidence covers both host assignments, Wi-Fi, declared NAT/manual-forwarding paths, reachability failure, disconnect/rematch, packet route and FSD-009 impairments. Choose latency/window settings from measured correction/catch-up behavior. A route test does not close battle-state gates.

Controlled versus admission: both peers apply and verify one supported configuration (timer, rule kind/stocks, stage/form, hazards/items, fighter/costume and per-player controls) before the first speculative tick. Exactly two human-controlled slots bind to the agreed participants; a CPU placeholder is not an active fighter or a required user setup step. Deliberately different saved rules/profiles must converge to the agreed supported settings or refuse with a visible reason. Qualify rematch and role reversal. Expose actual rollback/fallback mode and resource refusal; fallback is a separate unqualified mode until proven.

### FSD-017 - Persistent four-member private lobby

Support up to four members in one persistent code-based lobby. Any two activate controllers/select fighters; the others stay connected as spectators. No automatic rotation schedule, manual rehosting or new shared code is required when changing the active pair. Role changes take effect between matches, after committed end or explicit abort/cleanup; controller loss during a match invokes a defined active-player failure policy, not immediate spectator reassignment. Assign slots independently of lobby ownership. Fresh pair identity/readiness rejects queued prior-pair traffic. Direct guest-to-guest battles cannot silently forward through the waiting owner.

The lobby controller owns membership, codes, active-pair selection/readiness and spectator assignment, never frame approval or input confirmation. It may initially run on the creator's PC; no separately hosted server is required. Initial owner departure may close the lobby clearly; automatic host migration is deferred. Normal hosting, code entry, character selection and role changes are accessible in-game through the versus-based flow. The current F1 host/join overlay is reusable; router/firewall failures require clear guidance rather than a promise of universal automatic reachability. Do not integrate Local Wireless's battle synchronization in this scope.

Acceptance: source tests and four-machine trials exercise all six unordered active pairs, admission conflicts when more than two select, role changes, old packets, unequal match histories and owner/spectator/active-player departure. No spectator affects battle confirmation. This lobby and FSD-018 spectating are required for the later four-member product. Initial delivery is the controlled two-person versus flow under FSD-016/019; all applicable 1v1 correctness gates remain mandatory.

### FSD-018 - Mandatory delayed spectating without gameplay backpressure

Up to two spectators watch a delayed stream of corrected, committed battle inputs with validated initial state/configuration and match identity. Received inputs alone are not sufficient publication authority. Spectators replay using the same battle semantics and verify covered state; they never supply battle inputs, frame acknowledgments required by fighters, or confirmation votes. Spectator stalls, disconnects, corruption and catch-up failure cannot stall or change active battle state. Their delay may increase or playback may stop/rejoin rather than affecting fighters.

Specify compatible-build admission, stream ownership, ordering/deduplication, bounded history, initial-state bootstrap and resynchronization. First-version playback may start at the next match for members joining mid-match; communicate that state in-game. No arbitrary live native-pointer snapshot transfer is assumed. Bound sender CPU, memory, locks, queues and bandwidth; prioritize gameplay and shed spectator work when limits are reached. Define committed stream retention independently of rollback history so a slow viewer cannot pin checkpoints. Session teardown releases viewer resources without waiting for their acknowledgment.

Acceptance: source failure/load tests plus zero/one/two-viewer comparisons on actual four-PC battles, including slow/paused/disconnected viewers, queue overflow, loss/reorder, wrong epochs, incompatible builds, and resynchronization. Record active-pair RTT, delay, stalls, p95/p99 replay cost, bandwidth and memory against the no-viewer baseline under a declared budget. Fighter correctness is unchanged and no spectator-induced input-delay increase, confirmation dependency or blocking send is allowed. If measured resource contention violates the budget, degrade/disconnect spectators rather than weakening battle requirements. Lowest practical fighter latency is the priority within correctness and stability; neither zero overhead nor unlimited network tolerance is promised.

## Non-goals and decision gates

Initial exclusions: full source recovery, Nintendo online interoperability, ranked/public services, anti-cheat, simultaneous 3-4-player battles, items, arbitrary versions, Linux rollback and game-content distribution. Preserve inherited features without expanding acceptance scope.

If FSD-002 through FSD-006 cannot pass, broaden targeted decompilation or restructure continuations through an ADR. Profile before revising performance scope; never weaken correctness criteria merely to close milestones.

### FSD-019 - Paired rollback test diagnostics

A Windows tester can launch an identified test session and collect a ZIP through a double-click script or terminal command independent of the game UI, including while the game is frozen or after it exits. Collection is bounded and read-only with respect to the game; it neither kills/suspends the game nor waits indefinitely on it. Locked, rotating, missing, truncated and incomplete files produce explicit collection results. Retain initialization identity and recent gameplay/failure context within declared limits. Legacy builds can export available logs but missing session IDs/telemetry stay unknown.

A versioned machine-readable manifest binds package/source and actual executable identities, session/match/peer/slot, timestamps and frame/epoch correlation where available, declared/applied rules and controls, route, active rollback/fallback mode, resource admission/refusal, input/prediction/correction/replay events, checksum comparison counts/coverage and desync/fatal/watchdog reports. Zero comparisons and incomplete output are not agreement. Export safe hardware/memory summaries and omission/truncation reasons. Capture streams with bounded cost and asynchronous I/O; preserve critical initialization/failure records without blocking gameplay. Available hashes must survive sanitization through explicitly typed fields. Exclude secrets, user paths, game assets/code, saves, memory dumps and full environment inventories; use allowlists and tested redaction. No automatic upload or diagnostic network service is required.

Acceptance: collector tests cover live writer/hung process, rotation/locks, missing/large files, redaction and size/time bounds; launcher captures startup failures and effective mode; offline pair inspection rejects incompatible/wrong-match/incomplete evidence and reports earliest comparable discrepancy with coverage limits. A receiving agent gets a concise summary, manifest and sanitized logs from both peers, not an unsupported causality claim. Test clean Windows usability and preserve setup-log export.
