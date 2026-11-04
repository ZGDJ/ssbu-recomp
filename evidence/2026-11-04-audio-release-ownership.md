# Host audio release ownership across restore

2026-11-04 UTC. Astra integration, base f04228f8356f27c678ad5207600679de0e8dddbb. [Ledger](../milestones/README.md) owns status. M1.13, M4.1 and integrated controls remain open.

## Decisive observation

Original BEGIN contains three released and two playing host audio occurrences. Held LOAD_READY contains five released occurrences, all born from APPENDs during original execution. Two releases were resident at original END; the independent native audio collector published three more after LOAD_BEGIN and before LOAD_READY. No getter published a release in this observation. Replay's five positive getters consumed this already-published inventory.

The first aligned positive/null split is poll4: original returns null while replay pops release11776/play11770, published in the load gap from an original APPEND. Every observed publication is by native audio_thread actor4420, using the actually sampled prepared/WHDR_DONE predicate. This establishes publication order relative to cuts, not the device's completion instant. No fallback-clock predicate was used. Equal numeric buffer pointers represent different occurrence identities.

The source owns these rings in runtime/nnaudio.c; current restore wiring does not rewind that static host inventory/device state. The native journal witnesses original occurrences feeding restored guest getters. This answers the pending-inventory versus getter/native-collection question for this run. It does not retroactively attribute the older poll3 split.

## Implementation and validation

The bounded observer records existing locked getter/collector/lifecycle operations and all writers. Held boundaries use one try-lock; busy/missing cuts fail attribution. No clock/device/event/queue/hold policy correction was made. A separate analyzer validates conservation, exact AP/QP joins, source ordering, shared mint lifetimes, boundaries and missing records. Failed candidate checks and corrections remain retained, including the erroneous AP/H2 actor equality. Final ownership and completeness R4 reviews accept bounded source/build readiness. Compiled52 and84 cases per O1/O3, targeted mutations and final970 API/256 CLI/44 census checks are scoped synthetic evidence, not gameplay proof.

New host SHA2569c3d330cffaa36d6218dd5cfa7b26deb697613ee011238627728126cac3f55a3; source302 digest52040768837b8536bd26d7fe7994207b57a68162db019c872c0fcf5b759d1441. Accepted diagnostic DLL431dd5bdd7e985c20959479739e9d7b391cd2e99b13f99d40def6928fc7e5b80 reused under unchanged interface evidence. Build/audits and independent integrated recipe review pass.

Own disabled500R/0S completed before enabled500R/exactly two depth-one replays. Original reference/save/tape, separate fatal/menu-RNG/full identity gates and fresh admission/lease requirements were retained. Enabled configuration SIM120,1,60 LS1 verify2 restore1 skip/lite0 Skyline0; disabled uses SIM/LS/restore0. Common controls pass; enabled aggregate fails and batch stops with no retry. All original failed gates remain unchanged, resolved=false, authoritative=0, mutation coverage unknown.

## Current run and limits

Independent decoding reconciles2560 release records, five successful cuts,134 AP records,15 postload records and131 QP records. Ten positive getters consume pending inventory; three return null. All thirteen getter collections publish zero. Source receipt completeness is true, separate from aggregate semantic qualification.

Both arms make ten submissions in five regions with equal sample-index sequences and all ten comparable x10-x12 triples equal. Full contexts differ. Original accepts6/rejects4 with6 confirmed dequeues; replay accepts4/rejects6 with4 dequeues. Decisions first differ at ordinal8. Different consumer progress and null-path ordering are observed; their whole causal relationship is not isolated. Ten actual postloads are512 and select source x11 definition-before-use, without a post-definition completion or output-convergence claim.

Frozen eleven-attempt-per-arm requirements fail for this10/10 run; queue agreement and semantic provenance also fail. No gate normalization or replacement was performed. Historical8/11 and scratch-inequality trials remain separate. Generic synthetic-only wording in the retained analyzer limits is a prose limitation, not a reinterpretation of these native receipts.

## Evidence and next proof

Private roots: artifacts/local/audio-release-control-20261104/ (native controls); audio-release-result-20261104/ (independent decoder, FINDINGS.txt, receipt-analysis.json and freeze); audio-release-build-20261104/; audio-release-ownership-review-20261103/; audio-release-completeness-r4-20261103/; audio-release-control-review-20261104/. Source design/candidate and every failed validation round are retained under artifacts/local/audio-release-*.

Next: define the semantic ownership of playing/released occurrences and irreversible audio device effects across restore, then select a correction against uninterrupted reference behavior. No safe device reset, queue copy, event reset, scheduling change or page exclusion follows automatically. Guest consumer progress and queue decisions remain a separate correction obligation. Further receipts are unnecessary to classify this run's thirteen getters; new runtime changes require new package controls and admission. Complementary gpt-6.1-sol/max publication reviews accepted without blockers: artifacts/local/audio-release-publication-source-20261104/REVIEW.md and artifacts/local/audio-release-publication-controls-20261104/FINDINGS.txt. Both verified the frozen text and preserved failed gates; final integration only adds these acceptance references.

Method: exact occurrence IDs and held boundary inventories resolved ambiguity that queue counts and pointer equality could not. Preserve completeness and distinguish publication time from device completion time.
