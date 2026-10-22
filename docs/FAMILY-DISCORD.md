# OpenSmash setup

Use the **new OpenSmash-Family installer ZIP**, **Smash-Ultimate-13.0.5-OpenSmash.zip**, and optionally **Smash-Ultimate-Completion-Save.zip**. You'll need Windows 64-bit, internet and about **30 GB free beyond the ZIPs**. Allow an hour or more; keep the PC plugged in and awake.

**1. Extract ONLY the installer ZIP**
Right-click **OpenSmash-Family-...zip** → **Extract All**. Leave the game/save ZIPs zipped in Downloads.

**2. Move the inner OpenSmash folder**
Find the folder containing **Install OpenSmash.bat**. Move that **OpenSmash** folder into **This PC → Local Disk (C:)**.
You should now have **C:\OpenSmash\Install OpenSmash.bat**, without an extra OpenSmash-Family folder in the path. Windows may hide `.bat`. Avoid Desktop/OneDrive and Program Files; ask me if C: isn't writable.

**3. Choose your files in the wizard**
Double-click **Install OpenSmash.bat** → **Choose ZIP...** → select the **game ZIP**.
Want the provided save? Click **Save ZIP...**, select the **save ZIP**, and check the optional save box. It replaces progress and keeps a backup. Leave it unchecked to keep your progress.
Click **Install**. The save is applied after the game installs successfully.

**4. Wait, then play**
The moving bar means setup is running, not time remaining. **data.arc is huge and can take much longer than other files.** Watch copied bytes and the last-log-activity time. After success, use **OpenSmash Play** on your Desktop. First launch may take several minutes. **Z** confirms; **F1** opens settings. Keep **C:\OpenSmash** in place.

---

# If you need help

Click **Save support ZIP...**, choose where to save it, then send me that ZIP with a screenshot of the error. If the wizard won't open, run **Collect Logs.bat** from **C:\OpenSmash**. The report contains diagnostic text, not your game or saves. Review it before sending; nothing uploads automatically.

To stop installation, click **Cancel setup**, confirm and wait for it to stop. After fixing an error, click **Retry** with the same ZIPs. Completed files are reused; an unfinished file restarts. Don't delete the install folder or disable security software.

To import the save later, close the game and run **Import Save.bat**. Select the save ZIP and confirm replacement. Existing progress is backed up. If setup reports an unfinished save transaction, send me a support ZIP before changing files.

For an announced update, close the game and use **Update OpenSmash**. Updates preserve progress. Never extract another installer ZIP over your existing installation. If your current install is running normally, let it finish.

This is experimental; online rollback is still being worked on.
