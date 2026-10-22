# Family installer and branch updater

Scope: M0.8 source implementation; M0.9 owns clean-PC end-to-end qualification. No gameplay/rollback gate closes here.

- Added Windows double-click installation, prepared 13.0.5 ZIP import, desktop Play and Update shortcuts, pinned private-Python bootstrap without system fallback, and source-only packaging with per-file ownership hashes.
- Update channel is `ZGDJ/ssbu-recomp`, branch `family`; a local channel setting can select another branch on that fork. Updates resolve a commit before download, refuse local source edits, preserve input/config/save directories, back up previous source and resume the exact pending revision after failure. Launch and setup share a Windows mutex. Pending rebuilds block Play.
- Runtime compatibility remains enforced. The channel maintainer must supply compatible pinned runtime assets when changing runtime sources. A source backup does not promise executable rollback after an incomplete rebuild.
- `python -m unittest discover -s tests -p 'test_family_*.py' -v`: 20 synthetic tests passed on Windows/Python 3.12. Includes unsafe ZIP paths, symlinks, duplicate names, reserved temporary paths, corruption, space failure/retry, version and archive mismatch, local-source collision, interrupted update/rebuild recovery and preserved save fixture. Update subprocesses/network are mocked; these are not fresh-PC install evidence.
- Initial sandbox run denied Windows atomic rename in temporary fixture directories. The same synthetic suite passed outside the sandbox after correcting a test fixture whose backslashes were normalized by Windows ZipFile.
- PowerShell parser accepted family_setup.ps1 and bootstrap.ps1. Real supplied ZIP metadata was read without extracting again: 131 selected data/metadata files, 17,669,191,261 bytes, expected format accepted. Data hashes for the original manual installation were verified in the separate local setup report.
- Independent review identified BOM handling, temporary-file collision and misleading update retry guidance; all corrected. Interrupted embedded-Python extraction before python.exe exists requires a fresh installer folder and is documented.
- Source-only package built from `dd9b13c`: 6,762,916 bytes, 635 managed source files, accepted by the updater's source validator. Extracted into an isolated ignored smoke-test folder. Its real Windows PowerShell bootstrap downloaded hash-verified Python 3.13.16 and pip, installed all seven pinned requirements, passed package imports and exited 0. No system Python installation, game extraction or game build was performed by this smoke test. Final documentation revisions produce a newly versioned package through the same packager.

The working developer installation and running game were not rebuilt or replaced for these tests. Release publication remains separate from source pushes and local packaging. Clean-PC setup, two-version live updates and actual shortcut launch remain M0.9.
# Follow-up validation

The [UTF-8, path preflight and import progress follow-up](2026-10-21-installer-encoding-paths.md) records fixes from the first family installation reports and 24 passing synthetic installer/updater tests. Clean-PC qualification remains M0.9.

The [native setup wizard](2026-10-21-family-wizard.md) adds instructions, live loading status and retry, validated with disposable workers before source packaging.

The [combined hardening](2026-10-21-family-hardening.md) adds save opt-in, contained cancellation, support reports, staged recovery and bounded downloads. It retains the separate M0.9 clean-PC gate.
