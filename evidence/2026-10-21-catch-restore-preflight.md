# Catch restore preparation and checked insertion

2026-10-21. M7.8 remains in progress. Follow-up to [fiber payload observations](2026-10-21-fiber-payload-refusal-audit.md). Root owns ring integration and isolated trials; separate agents own checked insertion and source fixtures. Independent frozen-source review found no blocker for this partial hardening packet.

## Change and remaining boundary

Catch configuration is initialized before capture can hold guest threads. After fiber preparation, ring restore tries the catch-table exclusive lock and, when dead-stack filtering is enabled, the backing-stack shared lock. Contention refuses before mutation. Preparation validates table identity/size/writability, guarded current-table reads, backing ranges and bounded fiber inventory. Both locks remain owned through commit or refusal cleanup and audit comparison, then release before unpark.

The live-stack inventory predicts post-restore bases: suspended saved fibers use their prepared saved block; other fibers use guarded current block reads. Moving the old enumeration earlier without this distinction would change filtering semantics. Commit no longer acquires these locks or enumerates fibers.

Checked reinsertion shares production slot-selection policy and returns failure without table writes when its probe window is exhausted. Ring restore treats this unexpected post-mutation failure as fatal. Ordinary catch entry retains legacy overwrite behavior. **Final merged-table capacity is not reserved yet.** The next packet must construct a detached prospective table from the actual restored table image and planned stack actions, validate every insertion before destructive work, then commit the prepared result. Current source checks and lock ownership do not prove coherent inventories or complete native writer quiescence.

## Source checks

Both exact-source suites pass at O1 and O3: `python -m unittest discover -s tests -p 'test_catch*source.py' -v`. Root artifacts are `artifacts/local/catch-source/run-5hzbe1cz` and `artifacts/local/catch-preflight-source/run-651719yb`. CI runs both suites. Coverage includes full/restricted/wrapped probe windows, tombstones and matching entries; lock refusal and ownership cleanup; invalid or unreadable inventories; capacity bounds; predicted saved stack bases; nested preparation; disabled settings; and fatal unprepared/failed commit. OS and inventory boundaries are controlled fixtures, not full process tests. All eighteen refusal-parser regressions also pass.

## Isolated runtime

Manifest: `artifacts/local/runtime-catch-preflight/package/manifest.json`. Normalized tree digest: `746ff4ce2fb0bbc0f865df6081ad7df1e41b793ff4f04aa11219ba6a64028117`. Distinct executable `build/work/ssbu_catch_preflight_probe.exe`, SHA-256 `0c05c3ad2d1edf8af94fb1e7ce8e6748f88a52d9b84f05e8b53e5fa7d35b8ad3`. Local package SHA-256: `8d531e3c556b8f2c7eafd747177a234d369d6ebc4fd7ca52e4ee604700da3d62`. No package is published. The sequential matrix is retained in `artifacts/local/save-import-20261021/catch-preflight-trials-a.json`.

## Next implementation contract

Use `RestorePlan.pages` destination/source pairs to overlay the prospective catch bytes onto a detached copy of the locked current table, respecting the exact commit rules for null sources, the decommitted sentinel and skipped decommitted destinations. Do not assume the table is one aligned page or always fully captured. Derive restored stack ranges from prepared suspended actions before `fibers_commit` consumes that plan. Parameterize the production slot selector over the target table so staging and legacy entry share policy. Test partial-page overlays, skipped pages, capacity exhaustion leaving the live table unchanged, and successful staged/legacy repair equivalence before adding the new commit path.

## Integrated results

All three fresh-userdata controls passed 500 real frames and two one-frame replay cycles against the sealed fighter baseline. Default `catch-preflight-default-a` completed in 65.562 seconds; forced late refusal `catch-preflight-late-a` in 56.235 seconds; forced CB refusal `catch-preflight-cb-a` in 55.500 seconds. Each launcher and required comparator exited zero.

The late refusal occurred at frame 118 after catch preparation. Ring coverage: 66 metadata spans, 5,260 destination pages and 5,292 OS observations. CB coverage: 711 objects/726 spans. Native coverage: 31 threads, 21 fibers, 22 contexts/411 spans. Suspended payload coverage: 15/15 targets, six exclusions, 15 stacks/28,536 bytes and 45 spans. All four observations were complete, revalidation passed, and every changed/unread counter was zero.

The CB refusal occurred at frame 118 before catch preparation. Ring coverage: 66 metadata spans, 5,247 destination pages and 5,279 OS observations. CB coverage: 691 objects/706 spans. Native coverage matched the late control. Suspended payload coverage: 15/15 targets, six exclusions, 15 stacks/25,624 bytes and 45 spans. All four observations again passed unchanged/readable. Neither battle had saved FLS payload; that branch remains source-tested only. Game tests did not force catch lock contention or table exhaustion; those branches are covered by the source fixtures.

Final normalized runtime source hashes matched the build manifest. The normal playable executable retained SHA-256 `ec39391dab2a03d43201becd82bb806264701b9150b96462ea2d4d149152d5b9`; the game DLL retained `30094b7db70a40856b6e2fbd1ed0b07343ef91e2cd504887871941ee1ed059e5`. All 24 installed save files matched the extracted fixture. Documentation and whitespace checks passed. The earlier unexplained page-plan refusal did not recur and remains unresolved. Raw-state replay divergence remains visible; these results do not qualify gameplay or online compatibility.
