# 13.0.5 roster and mechanics qualification matrix

Plan revision `roster-v1`, 2026-10-25. [M6.1](../milestones/README.md) owns planning acceptance; M6.2 owns full-roster gameplay qualification. Requirements: [FSD-003 through FSD-010 and FSD-015](FSD.md), with the [Ultimate fixture contract](ROLLBACK_DESIGN.md#ultimate-specific-fixture-obligations). This is an experiment specification, not evidence that any listed fighter or mechanic works under rollback.

## Scope and provenance

Target Ultimate **13.0.5**, two human-controlled players, no items. Nintendo's [update history](https://en-americas-support.nintendo.com/app/answers/detail/a_id/42809) identifies the target version. The [official roster](https://www.smashbros.com/en_US/fighter/index.html) and its [public roster data](https://www.smashbros.com/assets_v2/data/fighter.json), retrieved 2026-10-25, enumerate the fighters. Expand the site's 84 grouped entries into **89 qualification rows**: three Pokemon Trainer forms, three Mii classes, and separate Pyra/Mythra rows. Echo fighters remain distinct. Ice Climbers and Rosalina & Luma each retain one roster row but require multi-entity evidence. Alternate appearances are configuration variants, not additional roster rows. Numbers below are website identifiers, never runtime fighter-kind IDs.

Per-row SmashWiki links supply representative move/mechanic vocabulary, not version-pinned timing, state-layout or compatibility proof. The proposed tests are our engineering selections; bind their actual behavior to the identified 13.0.5 original recompilation before executing. Retained source receipts and the complete enumeration audit are in `artifacts/local/roster-matrix-20261025/`. Public sources establish what to investigate, not that the current launcher can configure it.

## Rules and stage scope

`rules-provisional-v1` inherits FSD's experiment policy: stock, three stocks, seven minutes, two human slots, normal launch rate (1.0), items/spirits/Final Smash meter/stage morph off, hazards off. Pin stage form, costume, control mapping and save/config identity per player. This is the approved **planning baseline**, not a claim that every field is enforced or read back by the runtime. No universal tournament ruleset is adopted.

The frozen Mario replay command is a separate historical diagnostic fixture. It has no explicit `time=` argument and uses `SSBU_DEBUG_END=300`; source `runtime/debug_mode.c` counts presented fight frames for that stop, not a seven-minute battle timer or authoritative tick count. Do not retrofit this plan's timer/settings into `default-attempt2`, its tape or original reference. Preserve its established menu/RNG identity and all native admission gates. Future fixtures need separately frozen commands and verified effective settings; M5.12 owns production setup convergence/readback.

| Stage / form | Planning disposition | Gameplay / rewind / correction / performance |
| --- | --- | --- |
| Final Destination / normal | Existing provisional experiment baseline | U / U / U / U |
| Battlefield / normal | Proposed platform/landing case; owner approval pending | U / U / U / U |
| Small Battlefield / normal | Proposed two-platform case; owner approval pending | U / U / U / U |
| Pokemon Stadium 2 / normal | Proposed geometry case; owner approval pending | U / U / U / U |
| Smashville / normal | Proposed platform case; owner approval pending | U / U / U / U |
| Town and City / normal | Proposed platform lifecycle case; owner approval pending | U / U / U / U |
| Hollow Bastion / normal | Proposed DLC-stage case; owner approval pending | U / U / U / U |
| Kalos Pokemon League / normal | Proposed wall/ledge case; owner approval pending | U / U / U / U |
| Northern Cave / normal | Proposed DLC-stage case; owner approval pending | U / U / U / U |
| Every other stage; all Battlefield/Omega conversions | Outside approved experiment set; no equivalence inferred from shape | U / U / U / U |

Stage names are from Nintendo's [stage catalog](https://www.smashbros.com/en_US/stage/index.html). Geometry and hazard-off behavior must be inspected on the pinned game before choosing exact tapes; no claim that this proposed list is legal at any tournament. Custom stages and stage morph are outside the current competitive scope. Additional approved stages require separately identified fixtures and coverage, not just a menu entry.

Owner choices remain open: final stage allowlist/forms, bans/counterpick procedure and timeout/tie policy; allowed Mii loadouts/cosmetics; final release rules. Do not block this planning packet on those choices or silently promote proposals to product approval. Hardware/window/network budgets remain separate FSD-007/009 decisions.

## Evidence semantics and common run contract

`U` = untested, `F` = failed with retained first divergence/refusal, `V` = verified for a linked, bounded evidence case. The four independent columns are **G** gameplay against original behavior, **R** same-input rewind, **C** wrong-input correction, **P** performance. No row inherits a V from a mirror, Echo, shared family, source regression or historical Mario diagnostic. The ledger alone owns task status; these cells describe qualification evidence. No evidence links exist for these new cases yet.

Every roster row includes common locomotion, jump/landing/ledge, attacks/shield/grab, damage/stock/respawn and a full-match end case, plus its named mechanic. Record missing mechanics as `N/A: reason` only per case and axis; an unbuilt tape, inaccessible loadout or absent state instrumentation is **untested**, not N/A. All fighters still require G/R/C/P. Final Smash and stage-morph cases are N/A for this rules scope because both are disabled; generated articles, fighter items and RNG remain in scope despite items=off.

Before any new native fixture: freeze executable/package/source/content/module identities, original reference, rules readback, player profiles/costumes, initial state/seed, full input tape and observed event tick. Use disposable userdata, integrator serialization and fresh capacity admission. Preload required assets/modules before ready or demonstrate deterministic later loading. UI selections and requested settings alone do not prove applied state. Mii records and switchable forms require explicit inventory. Never assert an authoritative state owner from a public moveset description.

For each case, capture before the relevant input/event and bracket its start, contact/change and cleanup with checkpoints. FSD-005 requires depths **1/2/4/8, at least 100 boundaries per depth**, with the named mechanics covered; report counts by case and depth, including rejected/missing boundaries, rather than hiding holes in an aggregate. Schedule enough boundaries per named early case at each depth to exercise its event and continuation; do not pad counts with idle frames. The same-input run must equal its uninterrupted reference at every compared authoritative boundary. For altered-input arms, deliberately wrong predictions corrected after 1/2/4/8 ticks must equal the separately recorded all-correct arm, including subsequent allocations/RNG and future actions. Define the correction point explicitly; do not require wrong speculative states to equal the oracle before correction.

Apply fatal-log, complete trace/count, original-behavior, fixture comparability and full post-run identity gates. Fighter telemetry alone cannot close complete-state acceptance: inventory authoritative owners/exclusions through M3.1/M3.2. Record semantic events (damage, hit eligibility, stock, object ownership/lifetime, RNG/resources) alongside declared state hashes and first divergence. Verify correction does not replay host input or rewind coordinator receive/ACK history. Repeated/overlapping corrections, oldest retained checkpoint, too-old refusal and bounded resource growth apply across the set. Performance records need representative active scenes, capture/restore/replay timing distributions including p95/p99 and peak commit; no invented hardware budget or FPS-only pass.

The early cases below are selected **before formal M4.1**, not immediately executable tapes. Frame numbers, initial damage/positions, exact input subsamples and safe hooks must be recorded when each fixture is prepared. M2/M3 prerequisites are not waived. Start with the unchanged reviewed default replay after capacity is available, then required integrated restoration/refusal controls; these broader cases follow. A failure stops that batch and selects a causal investigation.

## Named early fixtures

All cases below begin `G/R/C/P = U/U/U/U`. FD means Final Destination, normal form, provisional rules unless the case explicitly specifies a separately labeled terminal setup. Slot reversal is required for player-sensitive behavior. The actions are semantic tape specifications, not executable commands.

| ID / participants | Trigger and changed-input arm | Decisive observation / purpose |
| --- | --- | --- |
| E01 Mario mirror / FD | Press, hold, release and re-press attack/jump; buffer an action during recovery; cross stick thresholds; swap distinct per-player profiles | Consumed input order, prior-input/buffer counters and resulting action agree after restore and correction; host live input changes do not affect replay |
| E02 Mario vs Luigi / FD | Land a multihit attack; change defender stick transitions during hitlag and launch; bracket hitlag exit | DI/SDI-sensitive position/velocity and subsequent hit eligibility match all-correct reference; preserve meaningful input subsamples |
| E03 Mario mirror / FD | Attack shield, release for parry, grab/pummel/throw; change shield release or grab escape input | Shield/parry timing, damage, catch ownership, throw result and buffered next action match; no duplicate hit/throw |
| E04 Mario mirror / FD | Launch into landing/tech, then ledge grab/release/regrab; change tech/recovery input | Hitstun/tech/ledge state and collision history converge; capture landing, invulnerability and cleanup boundaries |
| E05 Link vs Mario / FD | Create remote bomb, have opponent pick up/throw, detonate or destroy, then create another; predicted spawn both prevented and introduced by correction | Article existence/owner, explosion hits and later allocation identity match each arm's oracle; no stale handle or duplicate object |
| E06 Diddy Kong vs Villager / FD | Produce banana; pocket and release it; pick up/discard and produce another; change pocket timing | Held/pocketed/world ownership and later spawn restrictions match; items=off does not suppress fighter-created objects |
| E07 Rosalina & Luma vs Mario / FD | Separate Luma, destroy it, continue through replacement; correction prevents destruction | Companion state, owner link, independent hit history and replacement timing match; two players are more than two state objects |
| E08 Ice Climbers vs Mario / FD | Separate partner, grab/hit one climber, lose partner, then KO leader and respawn; correct partner-loss input | Both entities and leader/partner relationships match before and after respawn; no one-entity-only checkpoint assumption |
| E09 Pokemon Trainer vs Mario / FD | Start each of Squirtle/Ivysaur/Charizard; cycle forms near attack and KO/respawn; correct switch input | Active/inactive form state, shared stock/resource relationships and module lifetime match all-correct arm |
| E10 Hero vs Mario / FD | Open/cancel/reopen Command Selection, choose a pinned outcome; change whether menu opens or spell executes; continue later RNG use | Menu outcomes, resource spending and subsequent RNG-dependent behavior follow original seeded arm; never reseed to force agreement |
| E11 Steve vs Mario / FD | Mine/craft, place/destroy/recreate blocks and crafting table; use minecart/anvil; change resource spending/spawn | Material/tool state, world collisions, object lifetimes and future allocation sequence agree after correction |
| E12 Robin vs Mario / FD | Deplete/recover a tome and Levin Sword; interact with discarded item; correct final use | Resource counters, depletion/recharge and spawned/discarded ownership agree through subsequent reuse |
| E13 Mario mirror / FD | Nonterminal KO/respawn, then separately label a last-stock scenario; predict lethal hit but correct to survival | Stock/respawn matches; speculative last-stock outcome retains restorable state and no premature result/save/unload occurs |
| E14 Mario mirror / FD | Arrange simultaneous lethal outcomes; correct one causal input to change winner or preserve both | Correct winner/continued match; terminal commitment and teardown occur exactly once after corrected confirmation |
| E15 Mario mirror / FD | Record a separately labeled near-timeout fixture with verified timer; change a final hit at expiry | Timer/damage/stock/tie outcome matches oracle; do not use debug process exit as timeout evidence |

E13-E15 provide M4.1 KO/respawn replay coverage and explicit M4.5/FSD-015 terminal-reversal cases; selecting them does not close M4.5 or prove a network confirmation horizon. A controlled offline late-input schedule must be identified. Network disconnect during speculative end and immediate rematch/old epochs belong to M5.2, using the same terminal scenarios. E01-E12 altered-input arms also feed M4.2; ordinary same-input replay cannot stand in for correction evidence. Remaining mechanics are not N/A: they stay untested in the roster and interaction plan.

## Selected Mii experiment configurations

Nine **test selections**, not an approved release allowlist: for each of Brawler, Swordfighter and Gunner, use `1111`, `2222`, `3333` in **neutral / side / up / down** special order. Each digit is the in-game choice 1, 2 or 3. This touches every special choice individually but only 3 of the 81 combinations per class; it does not establish all combinations. Owner may choose other release loadouts, which require added rows/evidence. Read back actual moves and pin the complete Mii/save record, body/appearance/costume and controls; a four-digit label alone is not identity.

| Class / selection | Neutral; side; up; down | G / R / C / P |
| --- | --- | --- |
| Brawler 1111 | Shot Put; Onslaught; Soaring Axe Kick; Head-On Assault | U / U / U / U |
| Brawler 2222 | Flashing Mach Punch; Burning Dropkick; Helicopter Kick; Feint Jump | U / U / U / U |
| Brawler 3333 | Exploding Side Kick; Suplex; Thrust Uppercut; Counter Throw | U / U / U / U |
| Swordfighter 1111 | Gale Strike; Airborne Assault; Stone Scabbard; Blade Counter | U / U / U / U |
| Swordfighter 2222 | Shuriken of Light; Gale Stab; Skyward Slash Dash; Reversal Slash | U / U / U / U |
| Swordfighter 3333 | Blurring Blade; Chakram; Hero's Spin; Power Thrust | U / U / U / U |
| Gunner 1111 | Charge Blast; Flame Pillar; Lunar Launch; Echo Reflector | U / U / U / U |
| Gunner 2222 | Laser Blaze; Stealth Burst; Cannon Jump Kick; Bomb Drop | U / U / U / U |
| Gunner 3333 | Grenade Launch; Gunner Missile; Arm Rocket; Absorbing Vortex | U / U / U / U |

Move lists: [Brawler](https://www.ssbwiki.com/Mii_Brawler_(SSBU)), [Swordfighter](https://www.ssbwiki.com/Mii_Swordfighter_(SSBU)), [Gunner](https://www.ssbwiki.com/Mii_Gunner_(SSBU)). Exercise each chosen special's startup, effect and cleanup; select shield/hit/whiff, airborne/grounded and interruption variants where applicable. Reflection, absorption, projectile lifetime, charge, counter and command-grab cases feed the interaction classes below. Do not transfer results between loadouts or classes.

## Full-roster interaction plan

For every roster row: run its common suite and representative mechanic against Mario in both slot assignments, then a mirror to expose duplicate ownership/resources. Those runs are screening, not proof of every matchup. Cover each selected Mii configuration and each approved stage separately. All costume slots need identified loading/setup coverage; choose and record gameplay variants where behavior/state/asset paths differ. Explicitly include all Koopalings, Alph, Steve/Alex/Zombie/Enderman, Hero appearances, both Trainer appearances and relevant gender variants in configuration inventory; cosmetic similarity does not waive identity or deterministic loading.

The following directed classes start untested. Each needs a matrix of actual source object/move, receiver, supported interaction, stage, slot assignment and result. Populate from pinned original behavior before running; unsupported interactions receive a reason, never fabricated reflection/pocketability. A representative pair validates only that pair. Expand to every applicable roster mechanic within the class before claiming class coverage.

| Class | First named pairs / cases | Required expansion and oracle |
| --- | --- | --- |
| I01 reflection / absorption / pocket | Samus vs Fox; Samus vs Ness; Diddy Kong vs Villager; Link vs Isabelle | Every projectile/object family against each applicable receiver behavior; ownership, damage, stored/released identity and respawn restrictions |
| I02 companion / capture / destruction | Rosalina & Luma vs Ice Climbers; Olimar vs Mario | Multi-entity targets, separation, independent hits, grabs and replacement; distinguish leader/partner/article owners |
| I03 transformations / copied ability | Pokemon Trainer vs Kirby; Pyra/Mythra vs Kirby; Kirby vs each copyable roster ability | Switch with active objects, copy/use/lose/reacquire, active form and module loading; explicitly document noncopyable cases |
| I04 resources / delayed objects / RNG | Hero vs Peach; Steve vs Robin; Snake vs Duck Hunt | Competing object churn, delayed detonations, random outcomes and future draws; original seeded oracle, no arbitrary reseeding |
| I05 command inputs / combat history | Ryu vs Ken; Terry vs Kazuya; Bayonetta vs Mario | Ordered inputs, facing changes, hitlag, cancel windows and meter thresholds; player-specific consumption and effect history |
| I06 stage / collision / recovery | Steve vs Mario; Pikachu vs Mario; Simon vs Mario | Every approved stage/form: blocks/mining, ledges/walls/platforms, tether/recovery interactions; no blanket Omega equivalence |
| I07 terminal / cleanup / rematch | Mario mirror, then each multi-entity/resource family | Last stock, simultaneous KO, timeout and changed winner; corrected confirmation, exactly-once cleanup, no stale objects on next match |
| I08 worst-case concurrent workload | Snake mirror; Steve mirror; Olimar vs Rosalina & Luma | Identified active object-heavy tapes, repeated corrections/oldest checkpoint, bounded allocation and timing tails; measured budgets only |

## Roster rows

The following section is the complete 89-row inventory. `Base` includes Echo fighters; `DLC` requires the relevant licensed content. Each mechanic is an initial test target in addition to the common suite, not an exhaustive moveset or claim about its implementation. Linked descriptions must be confirmed against 13.0.5 original behavior when freezing tapes. G/R/C/P are all untested.

| ID | Fighter | Content | Representative mechanic to qualify | G / R / C / P |
| --- | --- | --- | --- | --- |
| 01 | [Mario](https://www.ssbwiki.com/Mario_(SSBU)) | Base | Fireball spawn; Cape reflection; buffered aerial landing | U / U / U / U |
| 02 | [Donkey Kong](https://www.ssbwiki.com/Donkey_Kong_(SSBU)) | Base | Cargo carry/throw; charged Giant Punch; release on hit | U / U / U / U |
| 03 | [Link](https://www.ssbwiki.com/Link_(SSBU)) | Base | Remote Bomb ownership/detonation; boomerang return | U / U / U / U |
| 04 | [Samus](https://www.ssbwiki.com/Samus_(SSBU)) | Base | Charge Shot storage/cancel; missile and bomb lifetimes | U / U / U / U |
| 04e | [Dark Samus](https://www.ssbwiki.com/Dark_Samus_(SSBU)) | Base | Charge Shot and missile collisions; own timing/geometry evidence | U / U / U / U |
| 05 | [Yoshi](https://www.ssbwiki.com/Yoshi_(SSBU)) | Base | Egg Lay capture/release; Egg Throw trajectory; shield transitions | U / U / U / U |
| 06 | [Kirby](https://www.ssbwiki.com/Kirby_(SSBU)) | Base | Inhale/copy/use/lose ability; copied-object lifecycle | U / U / U / U |
| 07 | [Fox](https://www.ssbwiki.com/Fox_(SSBU)) | Base | Blaster and Reflector ownership; Fire Fox charge/release | U / U / U / U |
| 08 | [Pikachu](https://www.ssbwiki.com/Pikachu_(SSBU)) | Base | Thunder Jolt surface travel; Quick Attack direction changes | U / U / U / U |
| 09 | [Luigi](https://www.ssbwiki.com/Luigi_(SSBU)) | Base | Grab/plunger lifecycle; Green Missile variable outcome | U / U / U / U |
| 10 | [Ness](https://www.ssbwiki.com/Ness_(SSBU)) | Base | PK Thunder control; PSI Magnet absorption; PK Fire persistence | U / U / U / U |
| 11 | [Captain Falcon](https://www.ssbwiki.com/Captain_Falcon_(SSBU)) | Base | Command-grab recovery; Falcon Punch startup/interruption | U / U / U / U |
| 12 | [Jigglypuff](https://www.ssbwiki.com/Jigglypuff_(SSBU)) | Base | Rest hit/whiff and sleep recovery; aerial jump history | U / U / U / U |
| 13 | [Peach](https://www.ssbwiki.com/Peach_(SSBU)) | Base | Float start/end; Vegetable RNG and held-object ownership | U / U / U / U |
| 13e | [Daisy](https://www.ssbwiki.com/Daisy_(SSBU)) | Base | Float and Vegetable RNG; separate Echo evidence | U / U / U / U |
| 14 | [Bowser](https://www.ssbwiki.com/Bowser_(SSBU)) | Base | Flying Slam capture/release; Fire Breath duration | U / U / U / U |
| 15 | [Ice Climbers](https://www.ssbwiki.com/Ice_Climbers_(SSBU)) | Base | Leader/partner separation; independent hits; partner loss | U / U / U / U |
| 16 | [Sheik](https://www.ssbwiki.com/Sheik_(SSBU)) | Base | Needle storage/release; Bouncing Fish follow-up input | U / U / U / U |
| 17 | [Zelda](https://www.ssbwiki.com/Zelda_(SSBU)) | Base | Phantom build/release/interruption; teleport reappearance | U / U / U / U |
| 18 | [Dr. Mario](https://www.ssbwiki.com/Dr._Mario_(SSBU)) | Base | Capsule projectile; Super Sheet reflection; landing transitions | U / U / U / U |
| 19 | [Pichu](https://www.ssbwiki.com/Pichu_(SSBU)) | Base | Electric self-damage; Thunder projectile; recovery transitions | U / U / U / U |
| 20 | [Falco](https://www.ssbwiki.com/Falco_(SSBU)) | Base | Blaster hitstun; Reflector interaction; Phantasm transition | U / U / U / U |
| 21 | [Marth](https://www.ssbwiki.com/Marth_(SSBU)) | Base | Tipper/sourspot collision; Dancing Blade input branches | U / U / U / U |
| 21e | [Lucina](https://www.ssbwiki.com/Lucina_(SSBU)) | Base | Blade collision and Dancing Blade; no Marth result inheritance | U / U / U / U |
| 22 | [Young Link](https://www.ssbwiki.com/Young_Link_(SSBU)) | Base | Bomb pickup/fuse; bow/boomerang active together | U / U / U / U |
| 23 | [Ganondorf](https://www.ssbwiki.com/Ganondorf_(SSBU)) | Base | Flame Choke capture/tech; aerial command-grab outcome | U / U / U / U |
| 24 | [Mewtwo](https://www.ssbwiki.com/Mewtwo_(SSBU)) | Base | Shadow Ball charge; Confusion reflection; Disable state | U / U / U / U |
| 25 | [Roy](https://www.ssbwiki.com/Roy_(SSBU)) | Base | Blade hit regions; Double-Edge Dance branch history | U / U / U / U |
| 25e | [Chrom](https://www.ssbwiki.com/Chrom_(SSBU)) | Base | Soaring Slash capture of hits/landing; own sword regions | U / U / U / U |
| 26 | [Mr. Game & Watch](https://www.ssbwiki.com/Mr._Game_%26_Watch_(SSBU)) | Base | Judge RNG; Oil Panic absorption/storage/release | U / U / U / U |
| 27 | [Meta Knight](https://www.ssbwiki.com/Meta_Knight_(SSBU)) | Base | Repeated jumps; Drill Rush direction; Dimensional Cape reappearance | U / U / U / U |
| 28 | [Pit](https://www.ssbwiki.com/Pit_(SSBU)) | Base | Arrow steering; Guardian Orbitars interaction/break | U / U / U / U |
| 28e | [Dark Pit](https://www.ssbwiki.com/Dark_Pit_(SSBU)) | Base | Arrow and Electroshock Arm hits; separate Echo evidence | U / U / U / U |
| 29 | [Zero Suit Samus](https://www.ssbwiki.com/Zero_Suit_Samus_(SSBU)) | Base | Paralyzer stun; tether/Flip Jump landing and follow-up | U / U / U / U |
| 30 | [Wario](https://www.ssbwiki.com/Wario_(SSBU)) | Base | Waft charge consumption; bike spawn/ride/destruction | U / U / U / U |
| 31 | [Snake](https://www.ssbwiki.com/Snake_(SSBU)) | Base | Grenade fuse/ownership; C4 attach/detonation; delayed explosions | U / U / U / U |
| 32 | [Ike](https://www.ssbwiki.com/Ike_(SSBU)) | Base | Eruption charge/interruption; Quick Draw release | U / U / U / U |
| 33 | [Squirtle](https://www.ssbwiki.com/Squirtle_(SSBU)) | Base | Water Gun charge; Withdraw collision; Pokemon Change | U / U / U / U |
| 34 | [Ivysaur](https://www.ssbwiki.com/Ivysaur_(SSBU)) | Base | Razor Leaf spawn; Vine Whip tether; Pokemon Change | U / U / U / U |
| 35 | [Charizard](https://www.ssbwiki.com/Charizard_(SSBU)) | Base | Flare Blitz recoil/collision; Fly multihits; Pokemon Change | U / U / U / U |
| 36 | [Diddy Kong](https://www.ssbwiki.com/Diddy_Kong_(SSBU)) | Base | Banana spawn/pickup/throw limits; Monkey Flip command grab | U / U / U / U |
| 37 | [Lucas](https://www.ssbwiki.com/Lucas_(SSBU)) | Base | PK Thunder control; Rope Snake tether; absorption | U / U / U / U |
| 38 | [Sonic](https://www.ssbwiki.com/Sonic_(SSBU)) | Base | Spin Dash charge/cancel; spring spawn and opponent contact | U / U / U / U |
| 39 | [King Dedede](https://www.ssbwiki.com/King_Dedede_(SSBU)) | Base | Gordo reflection/ownership; Inhale and spit | U / U / U / U |
| 40 | [Olimar](https://www.ssbwiki.com/Olimar_(SSBU)) | Base | Pikmin order/pluck/latch/death; independent attack targets | U / U / U / U |
| 41 | [Lucario](https://www.ssbwiki.com/Lucario_(SSBU)) | Base | Aura-dependent outputs; Aura Sphere charge; Force Palm grab | U / U / U / U |
| 42 | [R.O.B.](https://www.ssbwiki.com/R.O.B._(SSBU)) | Base | Gyro charge/spawn/pickup; fuel use/recovery | U / U / U / U |
| 43 | [Toon Link](https://www.ssbwiki.com/Toon_Link_(SSBU)) | Base | Bomb fuse/ownership; returning boomerang and tether | U / U / U / U |
| 44 | [Wolf](https://www.ssbwiki.com/Wolf_(SSBU)) | Base | Blaster projectile; Reflector ownership; Wolf Flash collision | U / U / U / U |
| 45 | [Villager](https://www.ssbwiki.com/Villager_(SSBU)) | Base | Pocket/store/release; sapling/tree growth and destruction | U / U / U / U |
| 46 | [Mega Man](https://www.ssbwiki.com/Mega_Man_(SSBU)) | Base | Metal Blade pickup; Crash Bomber attachment; Leaf Shield lifecycle | U / U / U / U |
| 47 | [Wii Fit Trainer](https://www.ssbwiki.com/Wii_Fit_Trainer_(SSBU)) | Base | Deep Breathing timing/buff; Header ball ownership/collision | U / U / U / U |
| 48 | [Rosalina & Luma](https://www.ssbwiki.com/Rosalina_%26_Luma_(SSBU)) | Base | Luma separation/death/replacement; independent hit history | U / U / U / U |
| 49 | [Little Mac](https://www.ssbwiki.com/Little_Mac_(SSBU)) | Base | KO meter gain/spend; armor and counter interactions | U / U / U / U |
| 50 | [Greninja](https://www.ssbwiki.com/Greninja_(SSBU)) | Base | Water Shuriken charge; Substitute counter; Shadow Sneak delay | U / U / U / U |
| 51 | [Mii Brawler](https://www.ssbwiki.com/Mii_Brawler_(SSBU)) | Base | Selected Brawler loadouts; projectile/grab/counter/air transitions | U / U / U / U |
| 52 | [Mii Swordfighter](https://www.ssbwiki.com/Mii_Swordfighter_(SSBU)) | Base | Selected Swordfighter loadouts; projectile/reflection/counter | U / U / U / U |
| 53 | [Mii Gunner](https://www.ssbwiki.com/Mii_Gunner_(SSBU)) | Base | Selected Gunner loadouts; charge/projectile/absorption | U / U / U / U |
| 54 | [Palutena](https://www.ssbwiki.com/Palutena_(SSBU)) | Base | Reflect Barrier/Counter selection; Explosive Flame timing | U / U / U / U |
| 55 | [Pac-Man](https://www.ssbwiki.com/Pac-Man_(SSBU)) | Base | Bonus Fruit charge/cycle/catch; Hydrant collision and water | U / U / U / U |
| 56 | [Robin](https://www.ssbwiki.com/Robin_(SSBU)) | Base | Tome/Levin depletion/recharge; discarded item ownership | U / U / U / U |
| 57 | [Shulk](https://www.ssbwiki.com/Shulk_(SSBU)) | Base | Monado Art selection/timer/cooldown; changed launch outcomes | U / U / U / U |
| 58 | [Bowser Jr.](https://www.ssbwiki.com/Bowser_Jr._(SSBU)) | Base | Clown Car exit/re-entry; Mechakoopa spawn/pickup/destruction | U / U / U / U |
| 59 | [Duck Hunt](https://www.ssbwiki.com/Duck_Hunt_(SSBU)) | Base | Can hit history/detonation; clay pigeon and gunman lifetimes | U / U / U / U |
| 60 | [Ryu](https://www.ssbwiki.com/Ryu_(SSBU)) | Base | Command vs normal specials; facing and cancel/input history | U / U / U / U |
| 60e | [Ken](https://www.ssbwiki.com/Ken_(SSBU)) | Base | Command branches and cancels; independent Ken evidence | U / U / U / U |
| 61 | [Cloud](https://www.ssbwiki.com/Cloud_(SSBU)) | Base | Limit charge/expiry/spend; projectile and recovery changes | U / U / U / U |
| 62 | [Corrin](https://www.ssbwiki.com/Corrin_(SSBU)) | Base | Dragon Fang Shot charge; Dragon Lunge pin/release | U / U / U / U |
| 63 | [Bayonetta](https://www.ssbwiki.com/Bayonetta_(SSBU)) | Base | Witch Time counter/slowdown; multihit/recovery resource history | U / U / U / U |
| 64 | [Inkling](https://www.ssbwiki.com/Inkling_(SSBU)) | Base | Ink consumption/refill; painted targets; Splat Bomb lifecycle | U / U / U / U |
| 65 | [Ridley](https://www.ssbwiki.com/Ridley_(SSBU)) | Base | Space Pirate Rush capture/drag/release; Plasma Breath charge | U / U / U / U |
| 66 | [Simon](https://www.ssbwiki.com/Simon_(SSBU)) | Base | Whip/tether; Cross return; Holy Water object lifetime | U / U / U / U |
| 66e | [Richter](https://www.ssbwiki.com/Richter_(SSBU)) | Base | Own Holy Water interactions; whip/tether and returning Cross | U / U / U / U |
| 67 | [King K. Rool](https://www.ssbwiki.com/King_K._Rool_(SSBU)) | Base | Crown throw/pickup/return; belly armor damage/break | U / U / U / U |
| 68 | [Isabelle](https://www.ssbwiki.com/Isabelle_(SSBU)) | Base | Pocket/release; Fishing Rod capture; Lloid Trap placement | U / U / U / U |
| 69 | [Incineroar](https://www.ssbwiki.com/Incineroar_(SSBU)) | Base | Revenge stack/use; Alolan Whip follow-up timing | U / U / U / U |
| 70 | [Piranha Plant](https://www.ssbwiki.com/Piranha_Plant_(SSBU)) | DLC | Ptooie control; Poison Breath charge/cloud lifetime | U / U / U / U |
| 71 | [Joker](https://www.ssbwiki.com/Joker_(SSBU)) | DLC | Rebellion Gauge and Arsene transitions; changed specials | U / U / U / U |
| 72 | [Hero](https://www.ssbwiki.com/Hero_(SSBU)) | DLC | Command Selection RNG; MP spend/recovery; later random draws | U / U / U / U |
| 73 | [Banjo & Kazooie](https://www.ssbwiki.com/Banjo_%26_Kazooie_(SSBU)) | DLC | Wonderwing stock resource; grenade pickup/fuse; eggs | U / U / U / U |
| 74 | [Terry](https://www.ssbwiki.com/Terry_(SSBU)) | DLC | Command inputs/cancels; GO threshold and special branches | U / U / U / U |
| 75 | [Byleth](https://www.ssbwiki.com/Byleth_(SSBU)) | DLC | Weapon-specific attacks; bow charge; tether recovery | U / U / U / U |
| 76 | [Min Min](https://www.ssbwiki.com/Min_Min_(SSBU)) | DLC | Independent arm inputs/switch; Dragon-powered state | U / U / U / U |
| 77 | [Steve / Alex / Zombie / Enderman](https://www.ssbwiki.com/Steve_(SSBU)) | DLC | Mining/materials/tools; blocks/table; minecart and anvil | U / U / U / U |
| 78 | [Sephiroth](https://www.ssbwiki.com/Sephiroth_(SSBU)) | DLC | Wing activation/loss; Shadow Flare delayed detonation | U / U / U / U |
| 79 | [Pyra](https://www.ssbwiki.com/Pyra_(SSBU)) | DLC | Blazing End sword lifecycle; swap with Mythra | U / U / U / U |
| 80 | [Mythra](https://www.ssbwiki.com/Mythra_(SSBU)) | DLC | Foresight activation; swap with Pyra; active projectiles | U / U / U / U |
| 81 | [Kazuya](https://www.ssbwiki.com/Kazuya_(SSBU)) | DLC | Command input/facing; Rage state and command grabs | U / U / U / U |
| 82 | [Sora](https://www.ssbwiki.com/Sora_(SSBU)) | DLC | Magic cycle; Sonic Blade follow-ups; aerial multihit history | U / U / U / U |
