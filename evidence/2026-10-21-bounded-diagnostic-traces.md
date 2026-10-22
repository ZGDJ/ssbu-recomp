# Bounded diagnostic traces — 2026-10-21

## Scope and decision

Continue ADR-0007's provisional OpenSmash backend. This packet repairs diagnostic evidence collection and tests actual battle replay; it does not qualify rollback, complete-state determinism, native continuation restoration or full-roster support. M1.7 owns bounded evidence; M2/M3/M4 retain authoritative boundary/state/replay requirements.

The prior capture stopped by presented-frame count, allowing variable fighter tails, partial final rows and later rewinds after a periodic R1 summary. A filtered main-thread frame-end callback now seals an opt-in two-fighter diagnostic interval after the complete pass-kind append. It requires both stable internal slots, contiguous counts and no pending replay/verifier. Stream failure, missing rows, active writers, invalid targets and pending work refuse a seal. It does not stop gameplay or disable existing getters, deterministic frame accounting or network hash additions.

Internal slots are explicit because this installation lacks the optional external entry constant header and prints `e -1` for both fighters. This is a fixture identity limitation, not grounds to treat two indistinguishable rows as sufficient coverage. A slot is not a persistent cross-match entity identifier.

## Source and build identity

Base commit `46a8f6cc56587939c1ce93fd6a1293c8475ab1e1`, dirty branch `feat/rollback-validation-audit`. Repository-pinned SDL3, Vulkan headers, glslang, ImGui and reference files were downloaded with the installer's SHA-256 checks. LLVM 9, MSVC Build Tools and Windows SDK 10.0.26100.0 built an isolated runtime through `scripts/make_release.py --build <ignored-scratch> --out <ignored-package> --allow-dirty`. These local packages were not published or installed over the playable runtime. Compiler temporary paths were confined to ignored local artifacts.

Baseline executable SHA-256: `807fa03446c8c7efede48ed6d06ff8bc6e800a9dfb59238f55cc3dd2c0a2beba`.
Tested bounded-v2 executable SHA-256: `2f7cdd159a079a5f270d5e673ac522f491c8cde3056a5a3d21b50155d53499dd`.
V2 runtime source-tree digest: `f25dcb7e0472f027210e3369ea326d46f45b30cad33aff4a515b8ffb04d3e1e1`.
V2 package SHA-256: `96466756160610c6f6ce028c91c2c1c77a7c41f3b22969f25761449e3aeb368f`.

Private commands, logs, manifests, saves and detailed word differences remain under `artifacts/local/`. Build v1 was compiled but not game-tested; review found and fixed a shutdown writer/close race before v2 testing. A misplaced producer counter was also corrected before compilation. Independent source review accepted the corrected diagnostic locking/boundary design; it did not certify gameplay.

## Fixture and first trials

Each launch uses a fresh copy of the supplied completion save, normal game DLL, Mario mirror, human neutral P2, fixed seed 1, `end` stage, three stocks, items/hazards off, online off, deterministic mode, movie skip and the same controlled input tape. Shader preload is disabled to leave commit headroom for the snapshot ring. Rewind mode uses `SSBU_RB_SIM=120,1,60`, `SSBU_RB_SIM_VERIFY=2`, skip/lite masks zero. Only P1 has scripted input; this is not an independent two-lane or network test.

- Source baseline, trace disabled: exit 0, about 60 seconds, 512 fighter frames. This is startup/battle smoke, not complete interval comparison.
- First bounded forward trial: exit 0, about 58 seconds, sealed exactly 300 real passes, 600 fighter rows.
- First bounded rewind trial: exit 0, about 59 seconds, same complete 300-pass stream. Its rewinds happened later, at fighter frames 336 and 456. The mandatory replay comparison failed with `replay required but no replay frames captured`. The trial is retained as insufficient replay evidence, not retried into an unexplained pass.

This establishes that fighter logging begins before ready-go/ring capture. The next planned target was 500 real passes, with presentation termination extended separately so the stream could seal after actual rewinds. Presented frames, fighter passes and ring pass indices must not be interchanged.

## Completed 500-pass comparison

Forward reference `bounded-forward-500-a`: exit 0 in about 63 seconds; exactly 500 real passes and 1,000 rows. Rewind `bounded-rewind-500-a`: exit 0 in about 65 seconds; exactly 500 real passes plus two replay passes, 1,004 rows, and a complete footer with no pending replay. Both use the v2 executable hash above.

`tests/bounded_trace_cmp.py <rewind>/fight.txt <forward>/fight.txt --require-replay` exited 0: 500 real frames identical, two one-frame replay runs identical to their historical frames. This establishes matching recorded fighter telemetry for this fixture and interval only. No truncated tails or intersections were substituted for the requested coverage.

Independent forward control `bounded-forward-500-b` exited 0 in about 63 seconds and sealed exactly 500 passes. Its complete comparison against forward A also exited 0, all recorded fighter fields identical. Both forward files contain zero replay passes, explicitly reported as forward-only controls.

The separate raw R1 trace continued after the fighter stream sealed: five executed/verified cycles, 6,035 pages compared, differences of 2,562 in window 1, 33 in window 2 and 14 extras. The analyzer reported no malformed/correlation errors, 495 detailed pages, and completion unknown. In the two cycles inside the bounded fighter interval, 2,278 pages were compared with 819 window-1 differences, 13 window-2 differences and four extras. The remaining three cycles are explicitly outside the sealed fighter interval. Byte-state equality therefore does **not** pass despite equal fighter telemetry.

Diagnostic sealing resolves M1.7's stream-coverage problem. The earlier phrase “authoritative interval” in that packet is clarified to mean a requested diagnostic real-pass interval; authoritative tick/quiescence and state completeness remain unclosed in M2/M3. None of their acceptance requirements or FSD trial counts are reduced.

## Verification tooling

`tests/bounded_trace_cmp.py` requires explicit pass records and a single complete footer, checks every slot/count, rejects trailing data and compares both real and historical replay rows. It excludes running hashes and human-readable float rendering, and includes the logged integer/bit-pattern fields and optional work field. A successful comparison only covers those fields.

`tools/analyze_rollback_trace.py` correlates SIM, detailed page differences and VERIFY records; periodic reports are checked against their prefix rather than mistaken for completion. It intentionally returns nonzero because raw R1 logs lack a terminal protocol. Missing verification cannot be inferred as success. A trace footer's `pending=0` is not proof that verification succeeded; failed verifier capture can clear its pending target.

Detailed earlier probe `rewind-details` executed two one-frame rewinds: 2,526 pages compared, 312 window-1 differences, 15 window-2 differences and four extra-region differences; 313 detailed pages were emitted. Addresses near display/audio state and stack/TLS counters are leads, not ownership proof. Do not blanket-exclude them. The next state investigation must separate incorrect immediate restoration from divergence introduced during reexecution.

Source tests: 18 trace/analyzer unittest methods and 10 existing comparator methods pass. The compiled production trace helper passes sealing, row/kind coverage, pending work, producer/shutdown, invalid target and write-refusal cases. The inherited toy simulation passes 211 rollbacks/512 replayed frames/depth six. The actual input regression still reproduces M7.4's future-frame overwrite in 32 trials; this is a known defect, not a correctness pass.

Installed save recheck: all 24 files still match the import manifest. Testing uses disposable copies only.

Final identity check: original playable executable, game DLL, supplied ELF and input tape retain their earlier hashes. All 273 recorded build-source files match the v2 manifest using the build system's CRLF-to-LF hash normalization. An initial raw-byte comparison differed only because it did not apply that documented normalization; both checks remain local. Project-document validation and its 16 regression methods pass, as does `git diff --check`. CI configuration includes the new source/helper and parser regressions; no remote CI result is claimed.
