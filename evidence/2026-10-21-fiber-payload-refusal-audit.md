# Suspended fiber payload refusal observations

2026-10-21. Follow-up to [native bookkeeping observations](2026-10-21-native-bookkeeping-refusal-audit.md). M7.8 remains in progress. Root owns ring integration, parser and runtime validation; a separate agent owns the payload selector and source fixture; an independent reviewer checked the candidate.

## Scope and safety checks

The first eligible `SSBU_RB_REFUSAL_AUDIT=1` attempt now observes payload destinations of fibers marked suspended in the target snapshot. It captures the target host-stack range, Windows fiber block, guest context and optional saved FLS block before page/CB/fiber preparation. Running and never-run snapshot fibers are excluded and counted separately; a zero-length stack contributes no stack span. A saved-null FLS pointer contributes no FLS span. This extends the observer, not the restored state representation or restore ordering.

The selector requires a valid raw thread inventory and complete live inventory, validates stack arithmetic, rejects duplicate fiber/key/context identities and overlapping target stack ranges, matches current fiber/context/FLS ownership, and rejects targets observed running or on a live stack. The TEB fiber-pointer read in `live_rsps` is now guarded; read failure marks that inventory incomplete. Raw ownership access avoids the stale-FLS accessor's counter mutation. Existing diagnostic/cache activity in `live_rsps` remains outside the preserved-state claim.

Before abort comparison, the selector repeats eligibility checks with an allocation-free callback that matches every captured address and extent in order. The ring compares only after all identities, ranges, counts and callbacks match. If revalidation fails, it reports an incomplete audit without reading the captured payload ranges. Successful commit discards the observer before mutation and reports unchecked. A separate 64 MiB storage budget limits allocation, not elapsed time. Captures/read failures, partial reservations and omitted targets cannot pass.

These checks exclude stacks observed active during validation; they do not establish a coherent native process snapshot. Potentially unheld writers and the interval between checking and reading remain limitations. Private Windows fiber-layout offsets are inherited from the runtime. Logs retain `holds=unproven authoritative=0`; equality is a bounded observation, not proof of full rollback correctness.

`FIBER_PAYLOAD_REFUSAL_AUDIT` records requested/observed suspended targets, excluded targets, nonempty stack count/bytes, FLS count, revalidation, spans and changed/unread counts. `tools/analyze_restore_refusal.py --require-cb --require-native --require-payload` requires all four observations to match one refused frame. Payload schema v1 requires every requested target observed, successful revalidation and exactly `2*observed + stacks + fls` spans. Present payload records are validated even without the requirement flag.

## Source validation

`python -m unittest discover -s tests -p test_fiber_payload_source.py -v` passed at O1 and O3, retaining generated source and logs in `artifacts/local/fiber-payload-source/run-6u46lpp_`. The fixture extracts the actual selector, `Fib`, ring payload-audit type and all four ring observer functions. It uses the real byte observer with controlled OS/inventory boundaries. Tests cover payload mutation, allocation/read/budget failures, unsafe identities/ranges/inventories, duplicates/overlap, zero stacks, address/extent revalidation, changed eligibility skipping comparison reads, commit without comparison and partial-allocation cleanup. CI now runs this fixture.

All eighteen refusal-parser tests passed, including missing/mismatched/duplicate/unchecked payload records, incomplete targets, missing revalidation and impossible span/byte counts. Independent review found no runtime blocker and required the explicit check-to-read race limitation above.

The isolated runtime built from 55 sources. Manifest: `artifacts/local/runtime-fiber-payload/package/manifest.json`; tree `7fbab935cc2faa8484d7f4ddff187262a737cd68dcf24a37842e6bd1befb1bbf`; local package SHA-256 `4c938b57237db171bfe8a8bcfe741b4358a2d4b898eb37a128c65dd894ea8f42`. No package is published.

## Isolated battle controls

The sequential matrix is retained in `artifacts/local/save-import-20261021/fiber-payload-trials-a.json`; every run uses fresh disposable userdata and `ssbu_fiber_payload_probe.exe`, SHA-256 `05537c6bf5b8e62aae32bbaa42b20d3c04231742b1f2aa74697997230a990a12`. Default control `fiber-payload-default-a` passed 500 real frames and two one-frame replay cycles in 64.875 seconds.

`fiber-payload-late-a` passed the same sealed trace requirement in 57.422 seconds after a forced late refusal at frame 118. All four observers passed. The payload audit observed all 15 suspended targets, excluded six running/never-run targets, revalidated all ranges and compared 15 stacks totaling 23,112 bytes plus 15 fiber blocks and 15 guest contexts (45 spans). No saved FLS payload was present in this scene; FLS preservation is source-tested, not covered by this battle observation. Ring coverage was 66 metadata spans, 5,255 readable destinations and 5,287 OS observations; CB coverage was 710 objects/725 spans; native bookkeeping coverage was 31 threads, 21 fibers, 22 held contexts/411 spans. Every observation was complete with zero changed/unread spans.

`fiber-payload-cb-a` also passed 500 real frames and two one-frame replays in 55.281 seconds, after a forced CB-preparation refusal at frame 118. All four observers passed. Payload coverage was 15/15 suspended targets, six exclusions, 15 stacks/24,760 bytes, 45 total spans, no FLS payload and successful revalidation. Ring coverage was 66 metadata spans, 5,274 readable destinations and 5,306 OS observations; CB coverage was 706 objects/721 spans; native coverage was again 31 threads, 21 fibers, 22 held contexts/411 spans. All comparisons were complete and unchanged/readable.

Every required launcher, sealed fighter comparator and combined audit exited zero. Final normalized runtime hashes matched the manifest. The normal playable executable and game DLL retained their prior hashes, all 24 installed save files matched the extracted fixture, and documentation/whitespace checks passed. No shared executable or save was replaced. The earlier unexplained page-plan failure did not recur here and remains unresolved.

## Remaining scope

Actual host CPU contexts, complete ownership/quiescence, catch-table semantics, fresh-fiber recovery, tracking completeness and replay-state divergence remain open. The earlier unexplained page-plan refusal and incomplete observations remain preserved. Payload preservation on refusal does not prove successful restore equivalence or online compatibility.
