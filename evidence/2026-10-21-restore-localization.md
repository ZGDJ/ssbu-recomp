# Restore localization investigation — 2026-10-21

## Question and scope

M1.8 investigates whether previously observed tracked-page differences are visible immediately after the byte-copy batch, after native continuation/catch/command-buffer restoration, or only after replay. ADR-0007 remains provisional. These observations do not establish complete checkpoint coverage, quiescence, authoritative equality or native continuation correctness.

The production restore path's undo logs first select the requested snapshot in `g_rg_idx`. The first diagnostic then compares live destinations in `g_rg_tl` against `rg_src` after `cp_run`. The second repeats that comparison after `restore_thread_regs`, `fibers_restore_all`, `rgc_after` and `rg_cb_load`, before the normal `unpark`. It uses a shared 100 ms/100,000-page scan budget, explicit unreadable/decommitted/omitted counts, phase-paired sequence/frame identity and existing watchdog/continuation diagnostics. No restoration policy is changed. All runs use disposable copies of the supplied completion save.

The selected pages are not the whole state: pages missed by the learned set remain invisible. Source-decommitted pages are deliberately skipped by the existing restore implementation. Reads are not atomic snapshots. The observer may change timing or some TLS/stack state, and continuation reconstruction may intentionally change bytes. Unchanged watchdog and zero reported continuation deficits do not prove coherent holds or complete restoration.

## First implementation and preserved incomplete result

The first reader validated every memory region and used `ReadProcessMemory` into fixed page buffers. Source-built v1 executable SHA-256: `486484508edbc5295cf3856845ac20ccba12cdf7af68e660318d1ae914513249`. Runtime tree digest: `4748889da1d010310c384d7eb8363f468e4df44e9dd28e16266912a148ad6afd`. Local package SHA-256: `d3014a99cfc207ed859872e831c8397060a5aec898c40c1193ed73446e3a999d`. Base commit remains `46a8f6cc56587939c1ce93fd6a1293c8475ab1e1`, dirty feature branch. Isolated build/package artifacts were not published or installed over the playable runtime.

`restore-diagnostic-a` exited 0 in about 68 seconds and retained a sealed 500-real-pass interval with two one-frame replays. Fighter telemetry compared identically to the earlier uninterrupted reference. Five total raw restore/replay cycles occurred, including three beyond the sealed fighter interval.

The diagnostic could compare only 4,913 pages in copy phases before exhausting each load's shared budget. Those sampled pages matched, but 24,791 were omitted. Continuation phases compared zero pages and omitted all 29,704. There were no parser errors, observed watchdog changes or reported continuation deficits. This result is explicitly **inconclusive**, not restoration equality. The next revision improves reader efficiency rather than extending the hold budget.

`restore-disabled-a`, the same v1 executable without the new environment flag, exited 0 in about 65 seconds, emitted no new restore-probe records, and still matched all 500 fighter passes plus both historical replay frames. This is a disabled-path fixture control, not broad semantic equivalence.

Private commands, complete raw logs, JSON analyses, executable/package manifests and saves remain under `artifacts/local/`. The analyzer always reports authoritative state, quiescence and raw stream completion as unknown and returns research-only exit 1, even if every observed page matches. It rejects missing/duplicate/malformed phases, incorrect accounting and source-pass correlations, and preserves unreadable/excluded/omitted counts separately.

## Reader regression and second incomplete trial

The first guarded-reader native test failed with access violation before any game trial used it. Disassembly showed Clang 9 removed the SEH handler around a direct intrinsic `memcpy`. Calling it through an opaque volatile function pointer retained the handler. Native protection, decommit and guard faults then passed at O1 and O3; unrelated exception filters remain excluded. R1's crash observer bypass is limited to that thread's active source-read fault, passing it onward to the local SEH handler rather than misreporting it as a game crash.

A four-region cache reduced a contiguous 12,008-read microbenchmark from approximately 363 ms to 2–7 ms. However, source-built `restore-fast-a` still exhausted the 100 ms budget in the actual game: 5,007 copy-phase pages compared with zero differences, 25,832 omitted; all 30,839 continuation-phase pages omitted. Five pairs correlated without parser errors or observed watchdog changes. Fighter telemetry still matched the 500-pass reference plus two historical replay frames. This second result is also inconclusive; the microbenchmark did not establish game performance.

V2-build executable SHA-256: `0a52a95d8fc634c456c6d34f9795043677bd79d3d3cbf1cf4aeed472c6d2a459`; tree digest `b464286110bdac46087294ad74e8045c35fb938cf0c59f1ed1429a289c59b046`; package SHA-256 `45a91d0175a682113eadc1932da76f041661b26b96ab7d7b48a65e6090419924`.

The final reader removes the expensive region queries and cache. It uses scoped SEH reads only on pages selected by restoration and their snapshot buffers, with null/overflow checks and explicit unreadable results. Decommitted snapshot sentinels are still never dereferenced. Its version-2 observation records declare `reader=seh_direct observer=guard_consuming`; a guard fault is refused but consumes the guard bit. Native tests measure this observer effect, verify real inaccessible/decommitted faults and TLS scope cleanup, and reject unrelated/write faults. The shared scan budget remains unchanged. Independent source review accepted this as an opt-in diagnostic, not a transparent observer or correctness oracle.

## Completed observations and decision

Final v3-build executable SHA-256: `0648b3b000d9019cdb0d4b00615eeaa1e70a0c548869db4e9670c4275333e747`; runtime tree digest `9106250f2e70ef408d623172976558720ac444bd39397f09ecb4031200c07da5`; local package SHA-256 `07c4c81cb018fe1cf9cf98e7d49bb9241acdd1f9a3df9e8609126ab117b9b6b8`.

`restore-direct-a` exited 0 in about 69 seconds. Five restore pairs correlated with five SIM/VERIFY cycles without parser errors. Each phase accumulated 28,813 readable-page observations, all equal, with zero unreadable or budget-omitted pages. Each phase separately counted 3,232 source-decommitted exclusions. These are observations over five loads, not distinct-page counts. Phase scans took 4.320–4.866 ms each, within the shared budget; these diagnostic timings are not rollback performance qualification. No watchdog counter change or existing thread/fiber deficit was reported.

The subsequent replay verifier still observed differences: 5,178 pages compared, 1,606 window-1 differences, 35 window-2 differences and 14 extras. The first two cycles inside the sealed fighter interval compared 2,394 pages after replay with 1,082 window-1 differences, 15 window-2 differences and four extras. In contrast, immediate observations in those two cycles matched all 10,859 readable selected pages in each phase, with 704 decommitted exclusions per phase. The other three raw cycles occurred after the fighter stream sealed.

The strict fighter comparator exited 0 for all 500 real passes plus both historical one-frame replays, matching the earlier uninterrupted reference. This remains limited telemetry evidence, separate from differing memory.

The observed readable selected-page differences therefore appear after the second restore observation, during the path that resumes execution and replays. This supports investigating resumed writers/host services and excluded state before changing the byte-copy implementation. It does not identify the exact writer, prove that every authoritative page was selected, or rule out problems in native state, allocator identity, decommitted-page treatment, or unobserved post-check steps. Do not automatically decommit or exclude pages based on these counts. M1.8 finishes this bounded localization experiment only; M2/M3/M4 and M7 hardening remain open.

Validation includes the production helper, actual Windows reader faults at O1/O3, twelve phase/parser regression methods, inherited source regressions and project-document checks. The expected M7.4 input-overwrite reproduction remains a known defect, not a correctness pass. CI is wired for the new tests; no remote CI run is claimed.

Final-build disabled control `restore-direct-disabled-a` exited 0 in about 66 seconds, emitted zero restore-probe records, and matched all 500 real fighter passes plus both historical replay frames. The original playable executable, game DLL, supplied ELF and tape hashes remain unchanged. All 24 installed save files match the import manifest, and all 275 runtime source files match the final build manifest using its recorded newline normalization. All trial processes finished. Final documentation validation and diff whitespace checks pass.
