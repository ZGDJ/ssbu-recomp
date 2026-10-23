# Architecture decisions

ADRs own decisions; [FSD](../docs/FSD.md) owns requirements; [milestones](../milestones/README.md) own status.

- [0001 Hybrid recompilation](0001-hybrid-recompilation.md): hybrid direction retained; implementation assumption updated by 0007.
- [0002 Safe battle boundaries](0002-safe-battle-boundaries.md): safe-boundary constraint retained; representation updated by 0007.
- [0003 Version and scope](0003-version-and-scope.md): accepted 13.0.5/full-roster target.
- [0004 Input netplay](0004-input-netplay.md): historical proposal; existing custom implementation adopted provisionally by 0007.
- [0005 Evidence and autonomy](0005-evidence-and-autonomy.md): accepted workflow/authorization.
- [0006 GGPO contract and Slippi methods](0006-ggpo-contract-and-slippi-methods.md): ownership/research retained; GGPO-first assumption superseded by 0007.
- [0007 OpenSmash adoption and hardening](0007-opensmash-adoption-and-hardening.md): adopted baseline/custom backend; qualification remains open.
- [0008 Private pair sessions](0008-private-pair-sessions.md): direct private 1v1 on the versus simulation first; lobby membership separated from battle participation; four-member persistent lobby and mandatory delayed spectating follow baseline 1v1 proof.

New ADRs need status/date, context, decision, alternatives, consequences and reconsideration trigger. Preserve superseded records with replacement links. Proposed does not mean implemented. Library/checkpoint choices require evidence.
