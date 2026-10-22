# Native Windows setup UI. Python and build tools are bootstrapped by the worker.
param([switch]$ImportSave)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
. (Join-Path $PSScriptRoot 'family_process.ps1')

function Read-SetupTail([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return '' }
    $stream = [IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
    try {
        $offset = [Math]::Max(0, $stream.Length - 65536)
        [void]$stream.Seek($offset, 'Begin')
        $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::UTF8, $true)
        try {
            if ($offset -gt 0) { [void]$reader.ReadLine() }
            return $reader.ReadToEnd()
        } finally { $reader.Dispose() }
    } finally { $stream.Dispose() }
}

function Start-SetupWorker([string]$Repo, [string]$Archive, [string]$Worker, [string]$SaveArchive = '', [switch]$ImportSave) {
    Test-SetupFolder $Repo
    $logs = Join-Path $Repo 'build\logs'
    New-Item -ItemType Directory -Force $logs | Out-Null
    $stamp = [Guid]::NewGuid().ToString('N')
    $stdout = Join-Path $logs "wizard-$stamp.log"
    $stderr = Join-Path $logs "wizard-$stamp-errors.log"
    $gate = Join-Path $logs "wizard-$stamp.gate"
    # EncodedCommand avoids command-line quoting ambiguity for spaces, quotes and Unicode.
    $workerLiteral = "'" + $Worker.Replace("'", "''") + "'"
    $archiveLiteral = "'" + $Archive.Replace("'", "''") + "'"
    $gateLiteral = "'" + $gate.Replace("'", "''") + "'"
    $extra = ''
    if ($SaveArchive) { $extra += " -SaveArchive '" + $SaveArchive.Replace("'", "''") + "' -SaveConsent" }
    if ($ImportSave) { $extra += ' -ImportSave' }
    $command = "`$ProgressPreference = 'SilentlyContinue'; `$limit = [DateTime]::UtcNow.AddSeconds(20); while (-not [IO.File]::Exists($gateLiteral)) { if ([DateTime]::UtcNow -gt `$limit) { exit 125 }; Start-Sleep -Milliseconds 50 }; & $workerLiteral -Archive $archiveLiteral -NonInteractive$extra; exit `$LASTEXITCODE"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
    $job = New-Object OpenSmash.SetupJob
    $process = $null
    try {
      $process = Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -PassThru `
        -WorkingDirectory $Repo -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-STA', '-OutputFormat', 'Text', '-EncodedCommand', $encoded)
    # Retain a process handle now so ExitCode remains available after a fast exit.
      $job.Attach($process.Handle)
      [IO.File]::WriteAllText($gate, 'start')
    } catch {
      if ($process -and -not $process.HasExited) { $process.Kill() }
      $job.Dispose()
      throw
    }
    return @{ Process = $process; Stdout = $stdout; Stderr = $stderr; Job = $job; Gate = $gate; Cancelled = $false; Draining = $false }
}

function Stop-SetupWorker($Job) {
    $Job.Job.Cancel()
    $Job.Cancelled = $true
}

function New-SetupWizard([string]$Repo, [string]$Worker = (Join-Path $Repo 'scripts\family_setup.ps1'), [switch]$SaveOnly) {
    $form = New-Object Windows.Forms.Form
    $form.Text = 'OpenSmash Setup'
    $form.ClientSize = New-Object Drawing.Size(760, 810)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'Sizable'
    $form.MinimumSize = New-Object Drawing.Size(540, 400)
    $form.AutoScroll = $true
    $form.AutoScrollMinSize = New-Object Drawing.Size(752, 810)
    $form.Font = New-Object Drawing.Font('Segoe UI', 10)
    $form.AutoScaleMode = 'Dpi'
    $screen = [Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $form.Size = New-Object Drawing.Size([Math]::Min($form.Width, $screen.Width), [Math]::Min($form.Height, $screen.Height))

    $title = New-Object Windows.Forms.Label
    $title.Text = 'Set up OpenSmash'
    $title.Font = New-Object Drawing.Font('Segoe UI', 18, [Drawing.FontStyle]::Bold)
    $title.SetBounds(24, 16, 710, 40)
    $form.Controls.Add($title)

    $instructions = New-Object Windows.Forms.Label
    $instructions.Text = "1. Choose the game's permanent home`r`nRecommended: C:\OpenSmash. The folder containing Install OpenSmash.bat is the installation folder. If it is nested inside OpenSmash-Family-..., close this window and move the inner OpenSmash folder directly into C:. Then reopen setup there."
    $instructions.SetBounds(24, 66, 710, 100)
    $form.Controls.Add($instructions)
    $location = New-Object Windows.Forms.TextBox
    $location.Text = $Repo
    $location.ReadOnly = $true
    $location.SetBounds(24, 170, 710, 28)
    $form.Controls.Add($location)

    $requirements = New-Object Windows.Forms.Label
    $requirements.Text = "2. Choose your prepared Smash Ultimate 13.0.5 game ZIP`r`nUse the game ZIP, not the installer ZIP or a save ZIP. Leave it zipped. You'll need internet, about 30 GB free beyond the ZIP, and an hour or more for the first setup."
    $requirements.SetBounds(24, 212, 710, 76)
    $form.Controls.Add($requirements)
    $archiveBox = New-Object Windows.Forms.TextBox
    $archiveBox.ReadOnly = $true
    $archiveBox.SetBounds(24, 294, 590, 28)
    $form.Controls.Add($archiveBox)
    $browse = New-Object Windows.Forms.Button
    $browse.Text = 'Choose ZIP...'
    $browse.SetBounds(624, 292, 110, 32)
    $form.Controls.Add($browse)

    $saveConsent = New-Object Windows.Forms.CheckBox
    $saveConsent.Text = 'Optional: apply a save ZIP after installation (replaces progress; keeps a backup)'
    $saveConsent.SetBounds(24, 334, 710, 30)
    $form.Controls.Add($saveConsent)
    $saveBox = New-Object Windows.Forms.TextBox
    $saveBox.ReadOnly = $true
    $saveBox.SetBounds(24, 372, 590, 28)
    $form.Controls.Add($saveBox)
    $saveBrowse = New-Object Windows.Forms.Button
    $saveBrowse.Text = 'Save ZIP...'
    $saveBrowse.SetBounds(624, 370, 110, 32)
    $form.Controls.Add($saveBrowse)
    $saveHint = New-Object Windows.Forms.Label
    $saveHint.Text = 'Leave the box unchecked to keep existing progress. Game data and saves stay separate.'
    $saveHint.SetBounds(24, 408, 710, 32)
    $form.Controls.Add($saveHint)

    $status = New-Object Windows.Forms.Label
    $status.Text = '3. Click Install when ready. Keep this window open until setup finishes.'
    $status.SetBounds(24, 448, 710, 55)
    $form.Controls.Add($status)
    $progress = New-Object Windows.Forms.ProgressBar
    $progress.SetBounds(24, 510, 710, 20)
    $progress.MarqueeAnimationSpeed = 30
    $form.Controls.Add($progress)
    $details = New-Object Windows.Forms.TextBox
    $details.Multiline = $true
    $details.ReadOnly = $true
    $details.ScrollBars = 'Vertical'
    $details.SetBounds(24, 540, 710, 120)
    $details.Text = 'During data.arc extraction, one large file can take several minutes. The activity bar means setup is running; it is not an estimate of time remaining. File percentages appear below as data is copied.'
    $form.Controls.Add($details)
    $hint = New-Object Windows.Forms.Label
    $hint.Text = 'After success, use OpenSmash Play on your desktop. Keep the installed folder in place.'
    $hint.SetBounds(24, 670, 710, 50)
    $form.Controls.Add($hint)
    $start = New-Object Windows.Forms.Button
    $start.Text = 'Install'
    $start.Enabled = $false
    $start.SetBounds(494, 758, 115, 32)
    $form.Controls.Add($start)
    $close = New-Object Windows.Forms.Button
    $close.Text = 'Close'
    $close.SetBounds(619, 758, 115, 32)
    $form.Controls.Add($close)
    $cancel = New-Object Windows.Forms.Button
    $cancel.Text = 'Cancel setup'
    $cancel.Enabled = $false
    $cancel.SetBounds(359, 758, 125, 32)
    $form.Controls.Add($cancel)
    $export = New-Object Windows.Forms.Button
    $export.Text = 'Save support ZIP...'
    $export.SetBounds(24, 758, 160, 32)
    $form.Controls.Add($export)
    if ($SaveOnly) {
        $title.Text = 'Import an OpenSmash save'
        $requirements.Text = 'Import into an existing installation. Close the game first. Choose the separate save ZIP below and check the consent box. Current progress will be backed up before replacement.'
        $archiveBox.Enabled = $false
        $browse.Enabled = $false
        $saveConsent.Text = 'I want to replace current progress with this save ZIP (a backup will be kept)'
        $start.Text = 'Import save'
    }

    $state = @{ Job = $null; Running = $false; Started = $null; Result = $null; LastOutput = [DateTime]::UtcNow }
    $timer = New-Object Windows.Forms.Timer
    $timer.Interval = 500
    $browse.Add_Click({
        $picker = New-Object Windows.Forms.OpenFileDialog
        $picker.Title = 'Choose the prepared 13.0.5 game ZIP'
        $picker.Filter = 'Game ZIP (*.zip)|*.zip'
        if ($picker.ShowDialog($form) -eq 'OK') {
            $archiveBox.Text = $picker.FileName
            $start.Enabled = $true
        }
        $picker.Dispose()
    }.GetNewClosure())
    $saveBrowse.Add_Click({
        $picker = New-Object Windows.Forms.OpenFileDialog
        $picker.Title = 'Choose the separate save ZIP'
        $picker.Filter = 'Save ZIP (*.zip)|*.zip'
        if ($picker.ShowDialog($form) -eq 'OK') { $saveBox.Text = $picker.FileName }
        if ($SaveOnly) { $start.Enabled = $saveConsent.Checked -and [bool]$saveBox.Text }
        $picker.Dispose()
    }.GetNewClosure())
    $saveConsent.Add_CheckedChanged({
        if ($SaveOnly) { $start.Enabled = $saveConsent.Checked -and [bool]$saveBox.Text }
    }.GetNewClosure())
    $export.Add_Click({
        $picker = New-Object Windows.Forms.SaveFileDialog
        $picker.Filter = 'Support ZIP (*.zip)|*.zip'
        $picker.FileName = 'OpenSmash-support-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.zip'
        if ($picker.ShowDialog($form) -eq 'OK') {
            try {
                . (Join-Path $Repo 'scripts\family_support.ps1')
                $null = Export-SetupSupport -Repo $Repo -Destination $picker.FileName -Status $status.Text
                [void][Windows.Forms.MessageBox]::Show($form, 'Support ZIP saved. Review its text files, then send the ZIP to the person helping you. Nothing was uploaded.', 'Support ZIP')
            } catch { [void][Windows.Forms.MessageBox]::Show($form, $_.Exception.Message, 'Could not save support ZIP') }
        }
        $picker.Dispose()
    }.GetNewClosure())
    $cancelAction = {
        if ($state.Running -and [Windows.Forms.MessageBox]::Show($form, 'Stop setup and its downloads/build tools? Completed files remain. The unfinished file or build step will restart on Retry.', 'Cancel setup?', 'YesNo', 'Question', 'Button2') -eq 'Yes') {
            if (-not $state.Running) { return }
            try {
                Stop-SetupWorker $state.Job
                $cancel.Enabled = $false
                $status.Text = 'Stopping setup and its child processes...'
            } catch { $status.Text = 'Could not cancel: ' + $_.Exception.Message }
        }
    }.GetNewClosure()
    $cancel.Add_Click($cancelAction)
    $start.Add_Click({
        try {
            if (-not $SaveOnly -and -not (Test-Path -LiteralPath $archiveBox.Text -PathType Leaf)) { throw 'Choose an existing game ZIP first.' }
            if ($SaveOnly -and -not $saveConsent.Checked) { throw 'Check the save replacement consent box to continue.' }
            $savePath = ''
            if ($saveConsent.Checked) {
                if (-not (Test-Path -LiteralPath $saveBox.Text -PathType Leaf)) { throw 'Choose the save ZIP or uncheck optional save import.' }
                $savePath = $saveBox.Text
            }
            $state.Job = Start-SetupWorker $Repo $archiveBox.Text $Worker $savePath -ImportSave:$SaveOnly
            $state.Running = $true
            $state.Started = [DateTime]::UtcNow
            $state.LastOutput = $state.Started
            $state.Result = $null
            $start.Enabled = $false
            $browse.Enabled = $false
            $saveBrowse.Enabled = $false
            $saveConsent.Enabled = $false
            $cancel.Enabled = $true
            $close.Enabled = $false
            $progress.Style = 'Marquee'
            $status.Text = 'Setup is running. Preparing tools and checking game files...'
            $details.Text = 'Starting setup...'
            $timer.Start()
        } catch {
            $status.Text = 'Could not start setup. Correct the issue below, then try again.'
            $details.Text = $_.Exception.Message
        }
    }.GetNewClosure())
    $timer.Add_Tick({
        try {
            $job = $state.Job
            $logError = ''
            try {
                $output = Read-SetupTail $job.Stdout
                $errors = Read-SetupTail $job.Stderr
            } catch {
                $output = $details.Text
                $errors = ''
                $logError = ' Log temporarily unavailable; process status is still monitored.'
            }
            $text = ($output + "`r`n" + $errors).Trim()
            if ($text -and $details.Text -ne $text) {
                $state.LastOutput = [DateTime]::UtcNow
                $details.Text = $text
                $details.SelectionStart = $details.TextLength
                $details.ScrollToCaret()
            }
            $elapsed = [DateTime]::UtcNow - $state.Started
            $quiet = [int]([DateTime]::UtcNow - $state.LastOutput).TotalSeconds
            $status.Text = "Setup running ($([int]$elapsed.TotalMinutes) min). Last log activity $quiet seconds ago."
            if ($quiet -ge 120) { $status.Text += ' No recent output: a build can be quiet. If it stays this way, save a support ZIP or cancel and retry.' }
            $status.Text += $logError
            if ($job.Process.HasExited) {
                if (-not $job.Job.IsEmpty) {
                    if (-not $job.Draining) { $job.Job.Cancel(); $job.Draining = $true }
                    $status.Text = 'Waiting for setup child processes to stop before allowing Retry...'
                    return
                }
                $job.Process.WaitForExit()
                try { $details.Text = ((Read-SetupTail $job.Stdout) + "`r`n" + (Read-SetupTail $job.Stderr)).Trim() }
                catch { $details.AppendText("`r`nFinal log could not be read. Save a support ZIP for details.") }
                $details.SelectionStart = $details.TextLength
                $details.ScrollToCaret()
                $state.Result = $job.Process.ExitCode
                $state.Running = $false
                $timer.Stop()
                $progress.Style = 'Blocks'
                $close.Enabled = $true
                $cancel.Enabled = $false
                if ($state.Result -eq 0) {
                    $progress.Value = 100
                    $status.Text = 'Setup finished. Use OpenSmash Play on your desktop. First launch may take several minutes.'
                    $hint.Text = 'If the log asks you to finish a pending update, run Update OpenSmash before playing.'
                    if ($SaveOnly) { $status.Text = 'Save import finished. Previous progress, if present, was backed up. You can play now.' }
                } else {
                    $progress.Value = 0
                    $status.Text = 'Setup stopped. Read the error below, correct it, then click Retry with the same ZIP.'
                    $hint.Text = 'Logs: build\logs. Completed files are reused; an interrupted file restarts from the beginning.'
                    $start.Text = 'Retry'
                    $start.Enabled = $true
                    $browse.Enabled = $true
                    if ($SaveOnly) { $browse.Enabled = $false }
                    $saveBrowse.Enabled = $true
                    $saveConsent.Enabled = $true
                    if ($job.Cancelled) { $status.Text = 'Setup cancelled. Completed files remain. Click Retry when ready; an unfinished file restarts.' }
                }
                $job.Job.Dispose()
                if (Test-Path -LiteralPath $job.Gate) { Remove-Item -LiteralPath $job.Gate -Force }
                $job.Process.Dispose()
            }
        } catch {
            # A temporary log sharing error must not stop monitoring the worker.
            $status.Text = 'Cannot read setup status: ' + $_.Exception.Message + '. Save a support ZIP; Cancel is available.'
        }
    }.GetNewClosure())
    $close.Add_Click({ $form.Close() }.GetNewClosure())
    $form.Add_FormClosing({
        param($sender, $eventArgs)
        if ($state.Running) {
            $eventArgs.Cancel = $true
            $status.Text = 'Setup is still running. Keep this window open until it finishes.'
        }
    }.GetNewClosure())
    $form.Add_FormClosed({ $timer.Dispose(); if ($state.Job) { $state.Job.Job.Dispose() } }.GetNewClosure())
    return @{ Form = $form; State = $state; Archive = $archiveBox; Start = $start;
              Status = $status; Details = $details; Progress = $progress; Timer = $timer;
              SaveArchive = $saveBox; SaveConsent = $saveConsent; Cancel = $cancel; Export = $export }
}

if ($MyInvocation.InvocationName -ne '.') {
    [Windows.Forms.Application]::EnableVisualStyles()
    $wizard = New-SetupWizard (Split-Path -Parent $PSScriptRoot) -SaveOnly:$ImportSave
    [void]$wizard.Form.ShowDialog()
    $wizard.Form.Dispose()
}
