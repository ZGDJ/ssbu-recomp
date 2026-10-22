# Native Windows setup UI. Python and build tools are bootstrapped by the worker.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

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

function Start-SetupWorker([string]$Repo, [string]$Archive, [string]$Worker) {
    $logs = Join-Path $Repo 'build\logs'
    New-Item -ItemType Directory -Force $logs | Out-Null
    $stamp = [Guid]::NewGuid().ToString('N')
    $stdout = Join-Path $logs "wizard-$stamp.log"
    $stderr = Join-Path $logs "wizard-$stamp-errors.log"
    # EncodedCommand avoids command-line quoting ambiguity for spaces, quotes and Unicode.
    $workerLiteral = "'" + $Worker.Replace("'", "''") + "'"
    $archiveLiteral = "'" + $Archive.Replace("'", "''") + "'"
    $command = "`$ProgressPreference = 'SilentlyContinue'; & $workerLiteral -Archive $archiveLiteral -NonInteractive; exit `$LASTEXITCODE"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
    $process = Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -PassThru `
        -WorkingDirectory $Repo -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-STA', '-OutputFormat', 'Text', '-EncodedCommand', $encoded)
    # Retain a process handle now so ExitCode remains available after a fast exit.
    [void]$process.Handle
    return @{ Process = $process; Stdout = $stdout; Stderr = $stderr }
}

function New-SetupWizard([string]$Repo, [string]$Worker = (Join-Path $Repo 'scripts\family_setup.ps1')) {
    $form = New-Object Windows.Forms.Form
    $form.Text = 'OpenSmash Setup'
    $form.ClientSize = New-Object Drawing.Size(760, 650)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $form.Font = New-Object Drawing.Font('Segoe UI', 10)
    $form.AutoScaleMode = 'Dpi'

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

    $status = New-Object Windows.Forms.Label
    $status.Text = '3. Click Install when ready. Keep this window open until setup finishes.'
    $status.SetBounds(24, 340, 710, 50)
    $form.Controls.Add($status)
    $progress = New-Object Windows.Forms.ProgressBar
    $progress.SetBounds(24, 396, 710, 20)
    $progress.MarqueeAnimationSpeed = 30
    $form.Controls.Add($progress)
    $details = New-Object Windows.Forms.TextBox
    $details.Multiline = $true
    $details.ReadOnly = $true
    $details.ScrollBars = 'Vertical'
    $details.SetBounds(24, 426, 710, 120)
    $details.Text = 'During data.arc extraction, one large file can take several minutes. The activity bar means setup is running; it is not an estimate of time remaining. File percentages appear below as data is copied.'
    $form.Controls.Add($details)
    $hint = New-Object Windows.Forms.Label
    $hint.Text = 'After success, use OpenSmash Play on your desktop. Keep the installed folder in place.'
    $hint.SetBounds(24, 556, 710, 30)
    $form.Controls.Add($hint)
    $start = New-Object Windows.Forms.Button
    $start.Text = 'Install'
    $start.Enabled = $false
    $start.SetBounds(494, 604, 115, 32)
    $form.Controls.Add($start)
    $close = New-Object Windows.Forms.Button
    $close.Text = 'Close'
    $close.SetBounds(619, 604, 115, 32)
    $form.Controls.Add($close)

    $state = @{ Job = $null; Running = $false; Started = $null; Result = $null }
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
    $start.Add_Click({
        try {
            if (-not (Test-Path -LiteralPath $archiveBox.Text -PathType Leaf)) { throw 'Choose an existing game ZIP first.' }
            $state.Job = Start-SetupWorker $Repo $archiveBox.Text $Worker
            $state.Running = $true
            $state.Started = [DateTime]::UtcNow
            $state.Result = $null
            $start.Enabled = $false
            $browse.Enabled = $false
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
            $output = Read-SetupTail $job.Stdout
            $errors = Read-SetupTail $job.Stderr
            $text = ($output + "`r`n" + $errors).Trim()
            if ($text -and $details.Text -ne $text) {
                $details.Text = $text
                $details.SelectionStart = $details.TextLength
                $details.ScrollToCaret()
            }
            $elapsed = [DateTime]::UtcNow - $state.Started
            $status.Text = "Setup is running ($([int]$elapsed.TotalMinutes) min elapsed). Large files and the first build take time."
            if ($job.Process.HasExited) {
                $job.Process.WaitForExit()
                $details.Text = ((Read-SetupTail $job.Stdout) + "`r`n" + (Read-SetupTail $job.Stderr)).Trim()
                $details.SelectionStart = $details.TextLength
                $details.ScrollToCaret()
                $state.Result = $job.Process.ExitCode
                $state.Running = $false
                $timer.Stop()
                $progress.Style = 'Blocks'
                $close.Enabled = $true
                if ($state.Result -eq 0) {
                    $progress.Value = 100
                    $status.Text = 'Setup finished. Use OpenSmash Play on your desktop. First launch may take several minutes.'
                    $hint.Text = 'If the log asks you to finish a pending update, run Update OpenSmash before playing.'
                } else {
                    $progress.Value = 0
                    $status.Text = 'Setup stopped. Read the error below, correct it, then click Retry with the same ZIP.'
                    $hint.Text = 'Logs: build\logs. Completed files are reused; an interrupted file restarts from the beginning.'
                    $start.Text = 'Retry'
                    $start.Enabled = $true
                    $browse.Enabled = $true
                }
                $job.Process.Dispose()
            }
        } catch {
            # A temporary log sharing error must not stop monitoring the worker.
            $status.Text = 'Setup is running; waiting for the next log update...'
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
    $form.Add_FormClosed({ $timer.Dispose() }.GetNewClosure())
    return @{ Form = $form; State = $state; Archive = $archiveBox; Start = $start;
              Status = $status; Details = $details; Progress = $progress; Timer = $timer }
}

if ($MyInvocation.InvocationName -ne '.') {
    [Windows.Forms.Application]::EnableVisualStyles()
    $wizard = New-SetupWizard (Split-Path -Parent $PSScriptRoot)
    [void]$wizard.Form.ShowDialog()
    $wizard.Form.Dispose()
}
