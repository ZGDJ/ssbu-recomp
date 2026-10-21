# Family installer and branch updater

Scope: M0.8 source implementation; M0.9 owns clean-PC end-to-end qualification. No gameplay/rollback gate closes here.

- Added Windows double-click installation, prepared 13.0.5 ZIP import, desktop Play and Update shortcuts, pinned private-Python bootstrap without system fallback, and source-only packaging with per-file ownership hashes.
- Update channel is `ZGDJ/ssbu-recomp`, branch `family`; a local channel setting can select another branch on that fork. Updates resolve a commit before download, refuse local source edits, preserve input/config/save directories, back up previous source and resume the exact pending revision after failure. Launch and setup share a Windows mutex. Pending rebuilds block Play.
- Runtime compatibility remains enforced. The channel maintainer must supply compatible pinned runtime assets when changing runtime sources. A source backup does not promise executable rollback after an incomplete rebuild.
- `python -m unittest discover -s tests -p 'test_family_*.py' -v`: 20 synthetic tests passed on Windows/Python 3.12. Includes unsafe ZIP paths, symlinks, duplicate names, reserved temporary paths, corruption, space failure/retry, version and archive mismatch, local-source collision, interrupted update/rebuild recovery and preserved save fixture. Update subprocesses/network are mocked; these are not fresh-PC install evidence.
- Initial sandbox run denied Windows atomic rename in temporary fixture directories. The same synthetic suite passed outside the sandbox after correcting a test fixture whose backslashes were normalized by Windows ZipFile.
- PowerShell parser accepted family_setup.ps1 and bootstrap.ps1. Real supplied ZIP metadata was read without extracting again: 131 selected data/metadata files, 17,669,191,261 bytes, expected format accepted. Data hashes for the original manual installation were verified in the separate local setup report.
- Independent review identified BOM handling, temporary-file collision and misleading update retry guidance; all corrected. Interrupted embedded-Python extraction before python.exe exists requires a fresh installer folder and is documented.

The working developer installation and running game were not rebuilt or replaced for these tests. Release publication remains separate from source pushes and local packaging. Clean-PC setup, two-version live updates and actual shortcut launch remain M0.9.
