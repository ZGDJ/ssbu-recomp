# Install OpenSmash

This is the OpenSmash fork at [ZGDJ/ssbu-recomp](https://github.com/ZGDJ/ssbu-recomp), replacing our earlier WindowSmash project. It is experimental; online rollback is still being hardened.

For click-by-click instructions using a **Smash Ultimate** folder on the Desktop, see the [Discord setup instructions](docs/FAMILY-DISCORD.md).

## What you need

- A Windows x64 PC with a compatible Vulkan graphics driver, internet, and roughly **30 GB of free space in addition to your game ZIP**. More space may be needed as the project grows.
- Your prepared **Smash Ultimate 13.0.5 game ZIP**, including ExeFS, RomFS, DLC, fonts and SHA256SUMS.json. A save-file ZIP alone is not enough. You do not need to extract the game ZIP first.
- Time: the first build took about 45 minutes on the developer's PC; allow an hour or longer on other PCs. First launch also prepares shaders and can take several minutes.

## Three steps

1. On your Desktop, right-click an empty space, choose **New → Folder**, and name it **Smash Ultimate**. Extract the **OpenSmash-Family** installer ZIP into that folder, then open its extracted `OpenSmash` folder. Do not run it from inside the ZIP.
2. Double-click **Install OpenSmash.bat**, then select your prepared game ZIP. Leave the setup window open while it downloads tools, checks files and builds the game. No Git, compiler setup or administrator account is required.
3. When setup reports success, use **OpenSmash Play** on your desktop. The first launch needs time to prepare shaders. **Z** confirms prompts; **F1** opens settings.

Setup also offers an optional completion-save import. Choose Yes and select the separate **Smash-Ultimate-Completion-Save.zip** supplied by the maintainer, or choose No to keep your own progress. The installer expects a ZIP containing `save_data/system_data.bin`; it does not read 7z archives. The maintainer has converted the supplied 7z to ZIP without changing its save files.

To import later, close the game and double-click **Import Save.bat**. Import replaces the game's `save_data` folder and keeps the previous folder under `artifacts/local/save-backups/<unique-id>`. Other user data is untouched. If import is interrupted, run Import Save again with the same ZIP; Play blocks until recovery completes. For manual restoration with the game closed, preserve the current `build/saves/save/save_data` elsewhere and copy the chosen backup directory back to that location as `save_data`.

Keep the extracted OpenSmash folder in its original location: the game reads its data there. Setup starts a new installation with online play and rollback disabled. Save replacement happens only when you explicitly choose the optional import. Saves created by this installation live in `build/saves` inside that folder. Updates never import the completion save again.

## If setup stops

Run **Install OpenSmash.bat** again and choose the same game ZIP. Verified files are reused, interrupted extraction is repaired, and the underlying build resumes. If there is a checksum error, obtain an intact copy of your prepared archive. If it reports insufficient space, free space on the installation drive and retry.

For help, send the error message and `build/logs/family-setup.log` to the person maintaining your installation. Review logs for personal folder names before sharing. Do not send game data or keys to GitHub. For an incomplete Python download that cannot resume, extract the installer package to a fresh folder; keep any existing game installation and saves.

Use a fresh install folder for a different archive/version. Use **Install OpenSmash.bat** for installation and **Update OpenSmash.bat** for updates. Installation itself stays on the bundled source version.

## Get fixes with one click

Close the game and double-click **Update OpenSmash** on your desktop (or **Update OpenSmash.bat** in its folder). It checks the `family` branch of our fork, downloads an exact revision and rebuilds as needed. It leaves your game data, settings and saves in place. You do not need the original game ZIP for ordinary updates. If interrupted, click Update again; Play stays blocked until the update finishes.

Updates are checked when you click, not silently while playing. The maintainer can point a particular installation at another branch by changing `branch` in FAMILY-UPDATE.json; the repository remains fixed to our fork. Local source edits are protected: the updater stops instead of overwriting them.

## For the maintainer

Run `python tools/package_family_installer.py` from a clean committed revision. It creates `dist/OpenSmash-Family-<revision>.zip` and a SHA-256 sidecar from Git-tracked source, with license/notices and an INSTALLER-VERSION.json. It does not bundle game data, keys, generated game code, saves or this machine's tools/build. Inspect the package before sharing.

The package can be attached to a Release on [our fork](https://github.com/ZGDJ/ssbu-recomp/releases), giving family one stable download page. Publication is a separate owner-authorized step. The helper uses the bundled fork source and the upstream installer's pinned/hash-checked tool and compatible runtime downloads; it never fetches latest branch source or bypasses the runtime compatibility check. Packaging does not publish anything.

The separate Update helper resolves the configured branch to a commit before downloading source. Publish tested commits to `family` for the default channel; this must retain the family helper files. Update the pinned runtime URL/hash in scripts/install.py whenever runtime sources change, and publish a matching compatible runtime asset before advancing the channel. Without a matching runtime, setup intentionally stops. Updates execute code from the maintainer-controlled fork, so protect that GitHub account and branch.

Each update backs up the prior managed source in `artifacts/local/family-update/previous-source.zip`. This is a source backup, not an executable rollback: an interrupted rebuild must finish before playing. Do not overlay a new installer ZIP onto an existing installation. The update tests use synthetic source/data and mocked builds; a two-version clean-PC update remains a qualification gate.

The archive tests and local build evidence are separate from fresh-PC qualification. See the [milestone ledger](milestones/README.md) for that gate before distributing this broadly. No installer can supply a missing Vulkan driver or guarantee performance on an untested PC.
