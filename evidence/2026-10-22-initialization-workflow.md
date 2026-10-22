# Initialization decision workflow alignment

2026-10-22, owner-requested documentation audit on feat/rollback-validation-audit at 38550dda6b0a926366cc37eec0f5c26e4776d043. This updates work selection and agent guidance; it changes neither runtime source nor acceptance requirements or task completion statuses.

## Finding and adopted direction

The existing AGENTS/workflow/README already promoted falsifiable outcomes and reuse. The active M3.5 next action and handoff nevertheless made the prepared timing pair the immediate continuation, without establishing how its outcomes would change the synchronization decision. The owner asked to prioritize a bounded audit of inherited battle initialization and a supported correction, using positive, actionable instructions.

The revised sequence is: inspect inherited ownership and requirements; demonstrate a path-specific violation or bounded uncertainty; select a minimal correction; run the smallest test capable of rejecting that correction; return to actual save/restore/correction against an uninterrupted battle as applicable prerequisites hold. Before expanding instrumentation, state how likely results change the correction, validation or next gameplay action. Existing instruments remain available, with use selected by the decision they resolve.

For M3.5, audit fixed/agreed seed availability, earlier gameplay-relevant random decisions, construction/selection/owner/reset ordering, rematches and restoration. A later overwrite establishes loss of control by the earlier write; its classification as a defect still depends on the intended contract. Offline evidence motivates inspection of network initialization; runtime network claims require their own evidence. Test supported corrections with different pre-match histories, multiple seeds and repeated uninstrumented runs, plus the relevant network path at readiness. Preserve the original reference and justify fixture changes through gameplay semantics.

## Audited scope

- AGENTS.md: added inherited-path inspection, decision-linked diagnostics and return to gameplay validation; retained concise entry-point role.
- docs/AGENT_WORKFLOW.md: added the general decision rule, bounded initialization example and complementary agent roles; packet template now names the decision and result-dependent actions.
- README.md: aligned the contributor summary with source ownership, minimal correction and actual restore/replay testing.
- milestones/README.md: aligned proof-first ordering and M3.5 next action; source audit is actionable while game admission remains a separate prerequisite. Statuses/dependencies/acceptance remain unchanged.
- docs/ROLLBACK_HANDOFF.md: source audit now leads; reviewed timing protocol remains available with its existing gates. Candidate identities and failures retained.
- evidence/README.md: reports now explicitly connect observations to decisions and distinguish source/path verdicts from gameplay qualification.
- adr/README.md: reviewed; existing decision/proposal distinction already fits, so unchanged.
- tests/drafts/thread_startup/README.md: reviewed; archived proposal guidance correctly points to active evidence/handoff, so unchanged.
- README-UPSTREAM.md and runtime/fonts_open/README.md: inspected purpose; inherited product documentation and font provenance are outside active agent workflow, so unchanged.

Repository inventory found one AGENTS.md and no additional active .mdc rules outside generated/private/dependency trees. No duplicate rule system was added. docs/VALIDATION.md and historical evidence remain unchanged; existing fatal, reference, replay, identity, resource and dependency gates retain their meanings. The former broad diagnostics priority was changed prospectively, not rewritten as a different historical result.

## Preservation and verification

All six edited files were copied byte-for-byte to artifacts/local/initialization-workflow-20261022/before/ with incoming hashes. Two are in the prior 433-entry preservation inventory: AGENTS.md and docs/AGENT_WORKFLOW.md. Their old bytes remain at those archived paths; the remaining 431 entries remain verified at original paths. The original inventory and prior passing/failed reports are unchanged. New instruction hashes are separate from runtime identities. The frozen runtime source digest must remain ad7389863a11b2158c97c7640fac3c4b46e9690d0ffbecc9c8c4a01d0930fa76.

The revised next-thread instructions are in docs/ROLLBACK_NEXT_PROMPT.md, a launch brief pointing to the ledger rather than another status authority. No new thread, game, build or subagent was launched for this documentation-only task. Existing runtime work remains uncommitted and untouched.

Retrospective: an available diagnostic had become the default next milestone. Requiring a decision plus likely-result actions in the existing packet template makes that cost visible before another observer or trial. Validation checks guidance consistency, preserved gates and historical bytes; it supplies no new gameplay result. Commands/results and final hashes are retained in the local audit packet.
