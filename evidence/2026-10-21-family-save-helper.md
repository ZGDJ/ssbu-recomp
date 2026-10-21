# Optional family save helper

M0.11 implements the installer integration; it does not certify 100% progression or game compatibility. Isolated worktree based on family revision 46a8f6c preserves concurrent rollback work in the main checkout.

- Supplied 7z inspected with installed 7-Zip: only save_data directories and 24 binary save files, 13,393,136 expanded bytes. Converted privately to a ZIP without changing contents. Every converted file matched the original extraction after import into an isolated fixture (SHA-256 comparison, 24/24).
- Import accepts the expected save layout and system-file size, rejects unsafe names, duplicates and unexpected files, decompresses/checks ZIP CRC before replacement, renames the existing save into a unique backup, and restores it on replacement failure. Interrupted imports keep Play blocked until recovered.
- Optional prompt defaults to No and runs after installation, never on Update. Separate Import Save.bat permits later import under the shared game/setup mutex. No save is bundled into source packages or pushed to GitHub.
- 26 family regression tests passed on Windows/Python 3.12, including six save-specific cases for old-save preservation, layout rejection, case collisions, rename-failure restoration and crash recovery. Windows sandbox required escalation for atomic-renaming disposable fixtures. PowerShell parser accepted the integration.
- Actual 7z extraction/conversion/import ran against ignored fixtures only. Existing user saves were not changed. Full GUI/game qualification remains M0.9; this report does not claim a fresh-PC pass.
- Added Discord-ready, click-by-click Desktop/Smash Ultimate instructions covering all three archives and the save popup.
