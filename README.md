# SmashRollback — OpenSmash hardening fork

Native Windows x64 **Ultimate 13.0.5**, full roster, competitive 1v1 rollback with no items. Exact stage/rules and hardware qualification remain explicit decisions. Retain OpenSmash's recompiled battle logic and harden its existing custom rollback.

Fork: [ZGDJ/ssbu-recomp](https://github.com/ZGDJ/ssbu-recomp). Upstream: [Denkishi/ssbu-recomp](https://github.com/Denkishi/ssbu-recomp), audited at `c7c874977ea7510c291ec8c278a58883a2f4e368`. Our WindowSmash planning contract has moved here; its implementation results do not transfer automatically.

**Experimental, not competitive-ready.** Prediction, input history, snapshots, native continuation restoration and resimulation exist. The [source audit](docs/ROLLBACK_AUDIT.md) identified correctness gaps. Identified offline baseline matches are recorded; rollback gameplay and full-roster qualification remain open. Current implementation and validation results are recorded in the ledger and evidence; historical migration results are not current branch status.

## Start here

- [Family installation helper](START-HERE.md): prepared game ZIP import, resumable build and desktop Play shortcut.
- [Milestone checklist and work ledger](milestones/README.md): sole task-status authority, dependencies, next actions and evidence.
- [FSD](docs/FSD.md): measurable requirements; [ADRs](adr/README.md): decisions.
- [Agent instructions](AGENTS.md) and [work packets](docs/AGENT_WORKFLOW.md): ownership, autonomy and relative effort.
- [Rollback contract](docs/ROLLBACK_DESIGN.md): GGPO responsibilities and Smash/Slippi methods; no GGPO library integration claimed.
- [Validation](docs/VALIDATION.md), [evidence](evidence/README.md), [source map/provenance](docs/UPSTREAM.md).

Development starts with the inherited code: establish the relevant state owner and violated invariant, make the smallest supported correction, and test actual restore/replay against an uninterrupted battle. Select diagnostics by how their outcomes change that engineering decision; reuse accepted tools and bound investigations to the next gameplay verdict.

Development advances through observable outcomes: reproducible battles, correct restore/replay and prediction correction, confirmation-safe match endings, two-PC agreement, and measured performance. Each work packet contributes a verified fix, a causal finding, a narrowed divergence, or an experiment that advances one of these proofs. The ledger defines their dependencies and acceptance.

Run `python tools/check_project_docs.py` for ready tasks and effort. Select the next dependency-ready task from the ledger proof-first queue; reuse completed harness and baseline tooling. Source fixes can proceed without private game inputs; battle acceptance cannot.

## Build and inherited documentation

Use [BUILDING.md](BUILDING.md) with owner-provided 13.0.5 inputs. No game data, keys, generated game code or saves in Git. Private experiments belong under ignored `artifacts/local/`. Inherited Linux/macOS work does not expand our Windows qualification scope.

The [preserved upstream README](README-UPSTREAM.md), [online guide](docs/ONLINE.md) and upstream `plan/` are reference material and inherited claims, not this fork's status or certification. Local Wireless is separate delay-based networking; custom rollback drives local versus battles. The fork FSD and ledger govern our work.

Preserve upstream [GPL-3.0 license](LICENSE), credits and [contribution rules](CONTRIBUTING.md). Agents may implement, test, commit, push fork feature branches and open draft PRs. Merges, releases, paid resources and destructive history changes require separate authorization.
