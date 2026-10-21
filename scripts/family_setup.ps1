# The extracted source package is the permanent installation folder. No administrator rights required.
param([string]$Archive, [switch]$Update, [switch]$ImportSave)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$repo = Split-Path -Parent $PSScriptRoot
$mutex = $null
$ownsMutex = $false
try {
    if ($Update -and $ImportSave) { throw 'Choose update or save import, not both.' }
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'OpenSmash requires 64-bit Windows.' }
    $hash = [Security.Cryptography.SHA256]::Create()
    $id = [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($repo.ToLowerInvariant()))).Replace('-', '')
    $hash.Dispose()
    $mutex = New-Object Threading.Mutex($false, "Local\OpenSmashSetup$id")
    try { $ownsMutex = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $ownsMutex = $true }
    if (-not $ownsMutex) { throw 'Setup is already running for this folder. Return to the existing setup window.' }
    if ((Test-Path -LiteralPath (Join-Path $repo 'build_location.txt')) -or
        ((Test-Path -LiteralPath (Join-Path $repo 'build\state.json')) -and
         -not (Test-Path -LiteralPath (Join-Path $repo 'artifacts\local\family-inputs\import.json')))) {
        throw 'This folder already has a different installation. Extract the family installer into a new permanent folder.'
    }
    $runningGame = Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and $_.ExecutablePath.StartsWith((Join-Path $repo 'build\'), [StringComparison]::OrdinalIgnoreCase) -and
        $_.Name -like 'ssbu*.exe'
    }
    if ($runningGame) { throw 'Close OpenSmash before installing or updating, then try again.' }
    if (-not $Update -and -not $ImportSave -and -not $Archive) {
        $picker = New-Object System.Windows.Forms.OpenFileDialog
        $picker.Title = 'Choose your prepared Smash Ultimate 13.0.5 game ZIP (not a save ZIP)'
        $picker.Filter = 'Prepared game ZIP (*.zip)|*.zip'
        if ($picker.ShowDialog() -ne 'OK') { exit 0 }
        $Archive = $picker.FileName
    }
    if (-not $Update -and -not $ImportSave -and -not (Test-Path -LiteralPath $Archive -PathType Leaf)) { throw 'The selected ZIP could not be found.' }
    Write-Host "Installing into $repo"
    Write-Host 'Keep this folder permanently. Setup needs internet, about 30 GB free, and may take an hour or longer.'
    # Recognize the development venv too; upstream bootstrap assumes an embedded distribution.
    $py = Join-Path $repo 'deps\python\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $py)) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File (Join-Path $PSScriptRoot 'bootstrap.ps1') -NoLaunch -PrivateOnly
        if ($LASTEXITCODE -ne 0) { throw 'Private Python setup failed. Check the network and retry.' }
        $py = Join-Path $repo 'deps\python\python.exe'
    }
    New-Item -ItemType Directory -Force (Join-Path $repo 'build\logs') | Out-Null
    [IO.File]::WriteAllText((Join-Path $repo 'build\python_path.txt'), $py, (New-Object Text.UTF8Encoding($false)))
    function Import-OptionalSave {
        $answer = [System.Windows.Forms.MessageBox]::Show('Import a completion save ZIP? This replaces your current game progress. The current save will be backed up. Choose No to keep your progress.', 'Optional save import', 'YesNo', 'Question', 'Button2')
        if ($answer -ne 'Yes') { return }
        $savePicker = New-Object System.Windows.Forms.OpenFileDialog
        $savePicker.Title = 'Choose the completion save ZIP (not the game ZIP)'
        $savePicker.Filter = 'Prepared save ZIP (*.zip)|*.zip'
        if ($savePicker.ShowDialog() -ne 'OK') { return }
        $ErrorActionPreference = 'Continue'
        & $py -u (Join-Path $PSScriptRoot 'family_save.py') $savePicker.FileName 2>&1 |
            Tee-Object -FilePath (Join-Path $repo 'build\logs\family-save.log')
        $saveResult = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($saveResult -ne 0) { throw 'Save import stopped. See build\logs\family-save.log and retry Import Save.bat with a valid save ZIP.' }
        [System.Windows.Forms.MessageBox]::Show('Save imported. Any previous save is kept in artifacts\local\save-backups. Normal updates will preserve your progress.', 'OpenSmash save import') | Out-Null
    }
    if ($ImportSave) { Import-OptionalSave; exit 0 }
    # Native stderr is a log stream, not a PowerShell terminating error; exit code is authoritative.
    $ErrorActionPreference = 'Continue'
    $script = Join-Path $PSScriptRoot 'family_setup.py'
    $scriptArgs = @($Archive)
    if ($Update) { $script = Join-Path $PSScriptRoot 'family_update.py'; $scriptArgs = @() }
    & $py -u $script @scriptArgs 2>&1 |
        Tee-Object -FilePath (Join-Path $repo 'build\logs\family-setup.log')
    $result = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    $retry = 'Install OpenSmash.bat'
    if ($Update) { $retry = 'Update OpenSmash.bat' }
    if ($result -ne 0) { throw "Setup stopped (code $result). Details: build\logs\family-setup.log. Run $retry again to resume." }
    if (-not $Update) { Import-OptionalSave }
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'OpenSmash Play.lnk'))
    $link.TargetPath = $py
    $link.Arguments = '"' + (Join-Path $PSScriptRoot 'family_play.py') + '"'
    $link.WorkingDirectory = $repo
    $link.Description = 'Play this installed OpenSmash fork'
    $link.Save()
    $updateLink = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Update OpenSmash.lnk'))
    $updateLink.TargetPath = Join-Path $repo 'Update OpenSmash.bat'
    $updateLink.WorkingDirectory = $repo
    $updateLink.Description = 'Update OpenSmash from the family branch of our fork'
    $updateLink.Save()
    $message = 'Setup complete! Use OpenSmash Play on your desktop. First launch prepares shaders and can take several minutes. Z confirms; F1 opens settings.'
    if (Test-Path -LiteralPath (Join-Path $repo 'artifacts\local\family-update\pending.json')) {
        $message = 'Game files repaired. Now run Update OpenSmash to finish the pending update before playing.'
    }
    [System.Windows.Forms.MessageBox]::Show($message, 'OpenSmash') | Out-Null
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'OpenSmash setup stopped', 'OK', 'Error') | Out-Null
    exit 1
} finally {
    if ($ownsMutex) { $mutex.ReleaseMutex() }
    if ($mutex) { $mutex.Dispose() }
}
