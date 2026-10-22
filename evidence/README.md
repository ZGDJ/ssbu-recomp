# Evidence

[Milestones](../milestones/README.md) own status; reports own observations. Use the [template](TEMPLATE.md) and [validation contract](../docs/VALIDATION.md).

- [OpenSmash baseline](2026-10-21-opensmash-baseline.md): source findings and test limitations.
- [Local OpenSmash setup](2026-10-21-local-setup.md): successful local build/self-tests and startup rendering; no rollback qualification.
- [Family installer and updater](2026-10-21-family-installer.md): source tests, archive compatibility and remaining clean-PC gate.
- [Hosted planning CI](2026-10-21-planning-ci.md): source contract checks on Windows.
- [Planning migration](2026-10-21-migration.md): transferred contract, reopened work and checks.

Reports should state the engineering decision, the inherited path/invariant examined, the decisive observation and the action it supports. Distinguish source-demonstrated defects, hypotheses, integrated correction results and gameplay qualification. Record why additional instrumentation changes the decision, and preserve original references alongside any explicitly justified fixture treatment.

Historical WindowSmash evidence remains in its [pinned repository](https://github.com/ZGDJ/WindowSmash/tree/cb110e7e0638acd126fdbe16da5e4011f8e966cf/evidence). It is not OpenSmash implementation evidence. Keep private traces/checkpoints under ignored `artifacts/local/`; sanitize reports and retain failing seeds.

- [Learned startup and presentation resources](2026-10-22-learned-startup.md): staged ownership, source failures and six frozen controls.
- [Guest arena and diagnostic pad bounds](2026-10-22-arena-pad.md): tested bounds, six passing control types, preserved initial-base refusal and ordering investigation.
