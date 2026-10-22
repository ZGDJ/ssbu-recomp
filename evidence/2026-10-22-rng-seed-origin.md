# M3.5 seed-origin source candidate

Question: does the owner seed already differ at the construction input, change during selection, or remain the same while the later reset differs? This packet supplies a bounded optional observation for the parent's serialized experiment. It does not explain the historical failure or qualify rollback. Root owns ledger/handoff integration, review, builds, package identity and every game trial. No game launch, runtime build, commit or shared API change was performed here.

The incoming dirty M1.3/reset packet is preserved. `artifacts/local/rng-seed-origin/freeze.py` reconstructs the incoming fighter host by removing only this packet's five additions and verifies its raw SHA-256 against `artifacts/local/rollback-seed-coverage-20261022/incoming.json`. Reset header, fixtures and analyzer remain unchanged. Root separately owns preservation of the rest of the concurrently edited checkout.

## Source attribution

Read the exact `void f_7101344cf0(Ctx *c)` definition in private `build/work/gen_eh_o2/c_019b.c`, and the exact `f_71014d8620` definition in `c_01bc.c`. Definition/brace boundaries precede label extraction; other functions sharing a label cannot supply an excerpt. New negative fixtures reject duplicate/missing definitions and ambiguous/missing/out-of-order label boundaries. Private excerpts and source hashes remain under `artifacts/local/rng-seed-origin/attribution-*/`, never in Git.

The construction path resolves the owner through actual global `0x71052c3760`, then the second pointer. After optional allocation/publication, `x21` holds the owner. The call at `0x71013452c4`, returning to `0x71013452c8`, invokes `0x71014d8620` with:

- `x0 = 0x71052c51b0`, the input block;
- `x1 = 0x71052c5730`, the associated player block;
- `x2 = owner + 8`, the context block.

Later, `0x7101345314..0x7101345324` copies `0x410` bytes from `0x71052c51b0` into `owner + 0x60`. The callee `0x71039c00e0` is generated import 1743, `memcpy`, verified against the generated symbol table as well as the import listing. Consequently owner `+0xf8` comes from input `+0x98`, actual address **`0x71052c5248`**. At `0x71013454b0/54b4` construction reads owner `+0xf8` and writes owner `+0x50` before the direct generator reset. This explains the seed transfer; it is not a new assertion about which dynamic branch the historical run took.

Inside `0x71014d8620`, saved `x26` is the input block. There are two explicit 32-bit stores to its `+152` (`+0x98`) field:

1. At `0x71014d88ec`, a selected-record path copies the word from **`0x710530e380`**. Its preceding path tests a selected record and its byte `+8`, and clears input `+156` (`+0x9c`).
2. At `0x71014d8ef4`, a later path tests input `+156`. When nonzero it clears that flag, advances the four-word state at **`0x71052391c0`**, and stores the resulting fourth word into input `+152` at `0x71014d8f2c`. For old words `(a,b,c,d)`, `t = a XOR (a << 11)` and `new = t XOR (t >> 8) XOR d XOR (d >> 19)`, all modulo 32 bits; state becomes `(b,c,d,new)`.

Paths can bypass these stores and retain the input seed. Entry flag alone is not a branch oracle: selection and nested work occur inside the observed call. Input mode, flag, both possible source values and the four-word RNG are therefore recorded on both sides. This packet does not identify every upstream writer of those sources, equate the global RNG with the nine fighter generators, or classify their ownership for restoration.

Identity: private `main.elf` SHA-256 `c81f5bb377783ec32468f9ee97c4c01bdf2c3dd84bb7fd8d94c9756360989045`. Selector window `0x71014d8620`, length `0xa30`, FNV64 `e0380a4e253df8ba`, SHA-256 `b08397bc433d4270b7201dff1021a0e8488ff33b87e858f9dec2747e388c7265`. The verifier resolves the ELF PT_LOAD segment with guest base `0x7100000000`; it does not assume a flat file offset. Exact generated selection-body normalized SHA-256 is `61eda7950866291213ed2daaaf7087cc228f319a3704ded0faf050f12b96c935`. These establish local source/window provenance, not loaded object execution or exhaustive caller coverage.

## Optional observer and interface

`fighter_sdk/rng_seed_origin_probe.h` is included after the unchanged reset header. `SSBU_RNG_SEED_ORIGIN_PROBE=1` requires successful reset installation, early observation, dedicated valid trace/hash configuration and 13.0.5. It requires exactly one nonnull selector entry and validates every byte in the `0xa30` window before attaching. Read/identity/attachment/null-original failures terminate through the trace-failure gate. Other setting values install nothing and emit nothing.

The wrapper admits entries with fighter-slot-zero frame 0..3, including construction before fighter registration, at most 32 pairs. It records original LR, input/player/context addresses, host thread and frame, readable input mode/seed/selection flag, four source RNG words and alternate seed. Counters and twelve early checkpoints expose missing/unsampled/open calls; exceeding the sample budget emits an explicit truncation record. Original behavior is called exactly once even if observation reads fail, with original guest context and original returned context intact. The wrapper preserves Windows LastError around observation. There is no reseeding, guest write, scheduling policy change, state restoration change or new shared interface.

Reads reuse the existing checked `ReadProcessMemory` helper, including null/range/overflow/size guards and temporary-buffer publication only after a full successful read. Invalid samples report explicit validity bits and zero unpublished fields. Each input snapshot reads 160 bytes, each RNG snapshot 16 bytes, each alternate snapshot four bytes. Sampling and logging are non-atomic and can perturb scheduling. The existing reset records supply the owner/vector outcome; duplicating their fields here is unnecessary.

Root must include the new header in isolated build/package inputs. The host wiring consists only of the include, environment setting/early-return exception, startup after reset installation, and early checkpoint call. No changes are required in shared hook/runtime interfaces. Independent review of this finite candidate remains root-owned.

## Source validation

Command: `deps/python/Scripts/python.exe -m unittest discover -s tests -p 'test_rng_seed_origin*.py' -v`.

Seven tests pass in the final validation run. The exact observer and verbatim shared read helper compile at O1/O3; fourteen native modes per optimization cover success/emitted records, wrong version, missing reset/early/trace/hash prerequisites, failed trace state, fingerprint mismatch, missing/duplicate function entry, attach failure, null original and code-read failure. The success fixture covers null/overflow input, partial and failed reads of each data source, real PAGE_NOACCESS, unchanged destination on failed read, disabled silence, out-of-window original forwarding, budget truncation, counter closure, exact guest-context preservation and LastError. Compiler output, generated translation units, commands and source manifests are isolated under `artifacts/local/rng-seed-origin/source-*/`.

Actual source-emitted complete records are consumed by the analyzer at both optimization levels. Negative fixtures reject malformed/duplicate/missing/reordered records, invalid validity bits/widths, partial publication, incomplete pairs, checkpoint count disagreements, out-of-range admission and truncation. Separate exact-definition tests verify source seams and recompute the ELF fingerprint; these are lexical/provenance checks, not execution of the entire private selector. The native fixture scripts the original function and OS/hook boundaries; it does not prove live hook attachment, concurrent stability or game behavior.

`artifacts/local/rng-seed-origin/run_regressions.py` reads the existing reset source/analyzer and initializer seed test modules, changing only their output-directory strings in memory. Eight unchanged affected tests pass, with O1/O3 native reset and seed cases. Old result folders and tests are untouched. `validate.py` captures final source, affected-regression and project-doc command exit codes/logs into a fresh `validation-*/results.json`. `frozen-source.json` records final raw hashes; `owned-fighter-host.diff` excludes all incoming edits.

Final validation: `artifacts/local/rng-seed-origin/validation-ziregrew/results.json`, all three commands exit 0. Final native fixture folder: `source-g8whbebl`; final exact-definition/ELF provenance: `attribution-y3du3nsn`. Source candidate is frozen for root's independent review. No further instrumentation is part of this packet.

## Exact parent experiment and interpretation

Freeze/review this source, build a fresh identified candidate with both headers, and retain the parent's full pre/post inventory, fatal checker, strict original reference and mandatory replay. Use the same tape, seed 1, rules, copied initial userdata and fixed candidate in serialized **disabled, enabled, disabled-repeat** controls. Give each trial a new directory. Retain the existing 500-real-frame/two-replay requirement and launcher allowance sufficient for the identified fixture. Stop the batch on disabled failure; preserve every failed attempt. Do not regenerate the reference or override the seed.

Disabled: `SSBU_RNG_SEED_ORIGIN_PROBE=0`, `SSBU_RNG_RESET_PROBE=0`, `SSBU_RNG_EARLY_PROBE=0`, `SSBU_RNG_SEED_PROBE=0`. Enabled: origin/reset/early all `1`, initializer seed probe `0`. Preserve the established other settings, including `SSBU_TRACE_FRAMES=500`, dedicated `SSBU_FIGHT_HASH`, replay settings, `SSBU_RB_RESTORE_VERIFY=0` and `SSBU_VK_LOAD_AT_START=0`.

For each stopped parent trial run the fatal gate first, then the new analyzer (substitute only new output/trial paths):

```powershell
deps/python/Scripts/python.exe tools/check_runtime_trial.py TRIAL --output NEW_FATAL.json
deps/python/Scripts/python.exe tests/rng_seed_origin_analysis.py TRIAL/game.log --trace TRIAL/fight.txt --reference artifacts/local/save-import-20261021/bounded-forward-500-a/fight.txt --output NEW_ORIGIN.json
```

Add `--disabled` for both disabled trials. This calls the unchanged reset analyzer/strict trace comparator, retaining 500 real frames, mandatory replay, all 24 reset checkpoints, all twelve raw observations/folds and complete reset call pairs. It additionally requires one origin installation, twelve ordered origin checkpoints, contiguous closed sample pairs matching all checkpoint counts, no truncation/unsampled entries, and a selector pair inside a construction window with the expected LR/input/player block. Disabled requires all four observer families silent. Record coverage is separate from readable samples and causal interpretation; no successful analyzer result overrides a fatal/reference failure.

For the enabled control, inspect the selector pair nested inside `0x7101344cf0`, matching thread, context `owner+8`, input address and returned owner seed. Require readable samples and manually inspect overlapping/nested calls before attributing a value. The JSON correlation flags expose context and seed agreement; they are not claims of atomicity or store execution.

- Different input seed at selector entry localizes a difference to before this call. It does not identify its writer or prove a save/config cause.
- Equal entry seeds but differing returned seeds localize the observed change to the selection window, including nested/concurrent work. Compare the recorded global RNG states, alternate seed, mode and selection flags. Matching returned fourth RNG word or alternate value supports that source hypothesis, but value equality alone does not prove the branch.
- Matching returned input and owner seed, followed by the existing matching later reset recurrence, links seed selection to the known reset association. A later differing owner with the same returned input narrows the missing observation to the copy/later-write interval.
- If all input/source/owner/reset observations agree while strict trace differs, seed input is not the observed differentiator; retain timing/fixture and other-state hypotheses. Missing/unreadable/overlapping records are inconclusive, not exclusions.

The historical `f28f3988` remains algebraically reconstructed; only `b77b0413` has prior direct owner observation. A new passing reference-seed control does not diagnose the old failed SDK traces. If no differing seed is observed, stop this packet at the enabled finite experiment and retain that uncertainty; do not add seed overrides or expand probe coverage without a new question. No full-state, authoritative-boundary, full-roster or formal rollback qualification follows.
