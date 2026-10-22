# Install OpenSmash

This is the OpenSmash fork at [ZGDJ/ssbu-recomp](https://github.com/ZGDJ/ssbu-recomp), replacing our earlier WindowSmash project. It is experimental; online rollback is still being hardened.

## What you need

- A Windows x64 PC with a compatible Vulkan graphics driver, internet, and roughly **30 GB of free space in addition to your game ZIP**. More space may be needed as the project grows.
- Your prepared **Smash Ultimate 13.0.5 game ZIP**, including ExeFS, RomFS, DLC, fonts and SHA256SUMS.json. A save-file ZIP alone is not enough. You do not need to extract the game ZIP first.
- Time: the first build took about 45 minutes on the developer's PC; allow an hour or longer on other PCs. First launch also prepares shaders and can take several minutes.

## Install

1. **Extract the installer ZIP.** Right-click **OpenSmash-Family** and choose **Extract All**. Inside the extracted folders, find **OpenSmash**: it contains **Install OpenSmash.bat**.
2. **Put the game folder in its permanent home.** Move that inner **OpenSmash** folder directly into **Local Disk (C:)**. Open it and check that the installer is now at **`C:\OpenSmash\Install OpenSmash.bat`**. The outer folder named `OpenSmash-Family-...` does not need to move with it.
3. **Start setup.** Double-click **Install OpenSmash.bat** to open the setup wizard. Check the folder shown, click **Choose ZIP...** to select your prepared game ZIP, then click **Install**. The wizard includes these instructions, an animated activity bar and a live log. Leave it open while it downloads tools, checks files and builds the game. No Git or compiler setup is required.
4. **Play.** When setup reports success, use **OpenSmash Play** on your desktop. The first launch needs time to prepare shaders. **Z** confirms prompts; **F1** opens settings.

Why `C:\OpenSmash`? Some game filenames are long. A short folder location gives Windows enough room for them. If you cannot write there, use another short, writable location such as `D:\OpenSmash`. Avoid Desktop/OneDrive, Program Files and extra nested folders. Run setup from the extracted folder, not from inside the ZIP.

Keep the extracted OpenSmash folder in its original location: the game reads its data there. Setup starts a new installation with online play and rollback disabled. It does not import or replace existing saves. Saves created by this installation live in `build/saves` inside that folder.

**Is it stuck on `dump/romfs/data.arc`?** This is the large game-data file, so it can take much longer than the small files before it. The file counter counts files, not time or bytes: reaching file 72 of 83 does not mean the import is nearly finished. Keep the window open. New installers show the amount copied about every five seconds while extraction advances; older installers stay on the same line until the file finishes. On an older installer, you can check Task Manager for Python disk/CPU activity or watch the size of `artifacts/local/family-inputs/dump/romfs/data.arc.install-part` grow. A retry checks completed files but restarts an interrupted file from the beginning.

## If setup stops

Run **Install OpenSmash.bat** again and choose the same game ZIP. Verified files are reused, interrupted extraction is repaired, and the underlying build resumes. If there is a checksum error, obtain an intact copy of your prepared archive. If it reports insufficient space, free space on the installation drive and retry.

If the wizard is still open, correct the reported issue and click **Retry**. The activity bar means the setup process is running, not that a particular amount of time remains. Keep the window open until it reports success or an error. Detailed logs, including tool-download output, are kept under `build/logs`.

If setup says the installation folder is too deep, close setup and move the whole **OpenSmash** folder to `C:\OpenSmash` as described above, then retry. Do not rename files inside the game ZIP. Current installers handle international filenames automatically; no terminal commands or Python settings are needed.

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
