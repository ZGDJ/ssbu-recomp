# Full-roster qualification planning

M6.1 / FSD-010, Astra integrator, 2026-10-25. Starting HEAD `4e879173edb7199a170f64e7ae378ec3b9327d28` on feat/rollback-validation-audit. Planning/source inspection only; no private inputs, builds, native launches, system settings or runtime edits. [Ledger](../milestones/README.md) owns status.

## Decision and deliverable

Use the capacity wait to define the fixtures required for formal M4.1 and later full-roster qualification. [ROSTER_MATRIX.md](../docs/ROSTER_MATRIX.md) enumerates 89 fighter/form rows, including Echo fighters, 13 DLC form rows (12 DLC fighter purchases, with Pyra/Mythra split), three Mii classes and nine explicit Mii test loadouts. Every gameplay/rewind/correction/performance field starts untested. Fifteen named early fixtures cover input history, combat, spawned-object ownership and future allocations, companions, transformations, RNG/resources, KO/respawn and terminal reversal. Eight directed interaction classes define expansion beyond one opponent or mirror per fighter.

The official site's 84 grouped entries expand by two Pokemon forms, two Mii classes and one Pyra/Mythra form to 89. Nintendo roster/stage/update pages and per-fighter SmashWiki descriptions are linked in the matrix; public pages describe test candidates, not verified runtime implementation. Raw public source receipts, hashes and checks are retained under `artifacts/local/roster-matrix-20261025/`. No public tier ranking or frame data is adopted as qualification evidence.

FSD's provisional Final Destination rules are retained. Additional named stages and final release rules/Mii choices await owner decisions. Nine Mii selections exercise each special option but do not cover all combinations or establish a product allowlist. Exact initial states, tapes, event ticks, move/settings readback and authoritative inventories remain execution prerequisites. Plan completion is not FSD-010 gameplay completion; M6.2 and formal M4.1 remain open.

## Inherited execution boundary

`runtime/debug_mode.c` parses requested fighter/stage/rules and uses `SSBU_DEBUG_END` as a presented-fight-frame process-stop limit. The accepted `default-attempt2` command omits an explicit `time=` setting. Therefore the new seven-minute planning baseline must not be silently applied to that frozen diagnostic fixture or treated as its observed timer. No launcher or reference changes are made. M5.12 retains effective setup convergence/readback. Future fixtures require their own frozen controls and original/all-correct oracles.

The unchanged native replay remains capacity-blocked as recorded in [readiness evidence](2026-10-25-replay-readiness.md). Its exact plan, runtime, reference, reserves and independent reviews remain intact; user availability for Windows consent is still required before reopening UAC. No capacity sample or native attempt was performed during M6.1 planning.

## Validation and review

Candidate and two complementary read-only briefs were frozen before parallel shared-checkout Astra reviews, using live-discovered Codex `gpt-6-astra`, medium reasoning and default service tier. Both accepted planning scope with no blocking findings. Each verified 103/103 frozen candidate hashes and the unchanged replay's 35/35 raw plus 296/296 normalized runtime hashes. Source consistency also verified all 89 source-receipt hashes and the Mii move ordering. Full reviews are retained as `invariants-review-r1.json` and `consistency-review-r1.json`; the review freeze is `freeze-r1.json` and original reviewed documentation is preserved under `reviewed-r1/`.

The sole nonblocking wording suggestion was applied: Bowser Jr.'s vehicle exit/re-entry case says Clown Car, avoiding confusion with Clown Kart Dash. This is an editorial clarification, not a fixture or acceptance change. Closing ledger/handoff/review disposition updates follow the accepted candidate.

Enumeration audit compared all 89 unique ordered row identifiers with the official JSON expansion, confirmed 13 DLC form rows, nine Mii configurations, 15 early cases and eight interaction classes, and checked every roster qualification field remained untested. `candidate-checks.json` retains counts and replay preservation. `deps/python/Scripts/python.exe -I tools/check_project_docs.py` and `git diff --check` pass. No runtime tests were rerun because runtime, adapter, executable, reference and frozen plan are unchanged. Production extraction is not applicable to documentation-only work.

M6.1 planning acceptance is complete: its M0.1 dependency is already done. This closes neither M6.2/FSD-010 gameplay nor formal M4.1. Final stage/Mii release choices and every native qualification case remain open. The immediate battle path is still capacity -> accepted default replay -> integrated restoration/refusal controls -> broader named fixtures.

Retrospective: defining semantic events and explicit execution prerequisites avoids mistaking a roster list for runnable or qualified battle tests. No new runtime tooling is needed for this planning packet.
