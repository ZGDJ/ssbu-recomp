# Bounded post-restore writer observation

- Date / author / reviewer: 2026-10-21 / root with writer_probe / independent writer_review; instrumentation boundary and buffer-status findings resolved before game tests.
- Task / requirements: M1.9; FSD-004, FSD-005, FSD-012. Investigation only, not state or gameplay qualification.
- Revision: dirty base `46a8f6cc56587939c1ce93fd6a1293c8475ab1e1`; runtime tree digest `a89b9a4e25b5440e80d84a6c1f35a21bf80cae3828ded1d4319a98a706b13104`.
- Build: configured Windows x64, bundled Clang 9 and existing MSVC/SDK; all 55 runtime sources built successfully. Local package SHA-256 `54d3c9bd1ce100dbbf084bdc123be63e1b5e2fd6a69188f97bc4b27ca0112593`; executable `f1625f9d96486299741323e62465214f60ac27d557acd6ba9842adbe5092cdee`. Nothing published.

## Method and coverage

`SSBU_RB_WRITER_PROBE=1` installs four 4-byte hardware watches after the first successful load's continuation checkpoint and before unpark. It requires 13.0.5, offline SIM with explicit `N,1,warm` and an actual verifier target exactly one pass ahead. Actual 13.0.5 main offsets are `529b844`, `529b848`, `6dd52e8`, `593b470` (mask bits 1, 2, 4, 8 respectively). They must not pass through GA's 13.0.4 address translation.

The independent exception handler records only fixed-buffer thread, phase, mask and post-store instruction address. It performs no target reads, allocation, logging or unwinding. Deferred output supplies allocation base, offset and approximate guest-function candidate. Existing debug registers are not replaced. Bounds are 128 events, 256 enumerated threads and a two-second enumeration deadline; individual Windows APIs cannot be preempted safely. Timeout does not kill a helper that may hold a thread suspended. Collection ends before the replay capture; fight-off reports abort. Saturation, pending handlers, skipped threads and failures prevent an unqualified collected status. These are observation limits, not a gameplay timeout fix.

Fixtures use the same configured machine, 13.0.5 game DLL, fixed-seed launcher, controlled tape, Mario/Mario Final Destination no-items/no-hazards setup and isolated imported-save copies as the restore-localization evidence. The tape SHA-256 is `2fd61c62b48cd52c909eb44b08b51832a9294b25bf1bd26b0a629652089f8760`. The game DLL hash is `30094b7db70a40856b6e2fbd1ed0b07343ef91e2cd504887871941ee1ed059e5`. This is one machine and one fighter fixture, with neutral P2; no latency/performance qualification.

## Results

Local `run_source_trial.py` trials `writer-enabled-a` and `writer-disabled-a` exited 0 in 61.688 and 60.750 seconds. Both used `SSBU_TRACE_FRAMES=500`, restore verification enabled and early Vulkan loading disabled; only writer-probe enablement differed. `tests/bounded_trace_cmp.py ... bounded-forward-500-a/fight.txt --require-replay` exited 0 for both: 500 real diagnostic passes and two one-frame replays matched. Disabled output contains zero WRITER records.

The enabled probe installed on 92 threads without skips or reported failures. Interval 118→119 recorded eight replay events, zero arming events and zero pending/inflight/dropped events. Cleanup changed 90 thread contexts with zero reported failures; these counts do not establish that the same thread set survived. No all-thread or future-thread coverage claim follows.

- Three producer-counter writes and two consumer-counter writes were observed. Their post-store native offset in the game DLL is `20397332`. Disassembly at `20397330` shows a small `movl` store helper followed by return. The approximate guest candidate `7103984090` does not identify the calling queue function.
- One write to the clock-sample location was observed at game-DLL post-store offset `1f4eeca3`. Disassembly at `1f4eeca0` shows a small `movq` store helper followed by return. Candidate `7103747750` is not reliable caller attribution.
- Two writes to `6dd52e8` were observed at offsets `ee405` and `ee40c` in another allocation/module. Its identity and callers remain unresolved; no ownership classification is assigned.

The earlier static mapping remains useful, but the runtime events prove only that these addresses were written after the restore checkpoint. The actual callers require additional attribution at the helper boundary. Do not use nearest-function candidates or matching nearby offsets as proof.

Across the two observed enabled-trial loads, both immediate phases compared 10,792 readable page observations with zero differences, unreadable pages, decommitted exclusions or omissions. Subsequent replay verification still reported 272 window-1, 13 window-2 and 4 extra page differences across 1,880 comparisons. The first 118→119 cycle reported 155/7/2 differences. Touched-page coverage still cannot reveal learned-set omissions; zero watchdog/continuation diagnostics do not prove quiescence.

## Validation, retention and next action

`tools/analyze_writer_probe.py` found no record integrity errors and intentionally exited 1 (`research_only`). Six parser regression tests passed, covering missing/duplicate/out-of-order events, malformed attribution, wrong scope, incomplete counters and saturated buffers. The source CI invokes them; hosted CI was not run. The full runtime build and both game controls exercise production instrumentation; injected OS installation/cleanup failure tests were not added.

Raw commands, hashes, traces, screenshots, JSON analyses and native disassembly are retained under ignored `artifacts/local/save-import-20261021/writer-enabled-a/` and `writer-disabled-a/`. Build manifest/log remain under ignored runtime-writer-probe paths. All 24 installed save files and the normal playable executable retain their original hashes.

M1.9 completes this bounded investigation with partial attribution. Next, capture a guarded caller observation at the identified leaf stores or instrument uniquely validated queue/clock boundaries, retaining module identity and a disabled control. Investigate the unresolved writer and snapshot resource handling; do not exclude these pages or change clock behavior on this evidence. ADR-0007 remains provisional and M2/M3/M4 capability gates remain open.
