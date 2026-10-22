param([string]$Repo, [string]$Fixture, [string]$Screenshot)
$ErrorActionPreference = 'Stop'
. (Join-Path $Repo 'scripts\family_wizard.ps1')
[Windows.Forms.Application]::EnableVisualStyles()
$worker = Join-Path $Fixture 'worker.ps1'
@'
param([string]$Archive, [switch]$NonInteractive)
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
if (-not $NonInteractive) { exit 3 }
if (-not (Test-Path -LiteralPath $Archive)) { exit 4 }
Write-Output ('Importing ' + [char]0x3010 + 'Bonus' + [char]0x3011)
Start-Sleep -Milliseconds 800
$marker = Join-Path $PSScriptRoot 'retried'
if (-not (Test-Path $marker)) {
    [IO.File]::WriteAllText($marker, 'fixture')
    Write-Output 'SETUP STOPPED: synthetic failure; retry'
    exit 1
}
Write-Output '100% (8 / 8 MiB)'
exit 0
'@ | Set-Content -LiteralPath $worker -Encoding UTF8
$game = Join-Path $Fixture "game ' special.zip"
[IO.File]::WriteAllText($game, 'fixture')
$ui = New-SetupWizard $Fixture $worker
function Assert($Condition, $Message) { if (-not $Condition) { throw $Message } }
function Wait-ForSetup {
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    while ($ui.State.Running -and [DateTime]::UtcNow -lt $deadline) {
        [Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 50
    }
    Assert (-not $ui.State.Running) 'Wizard failed to observe worker completion.'
}
try {
    $ui.Form.StartPosition = 'Manual'
    $ui.Form.Location = New-Object Drawing.Point(-3000, -3000)
    $ui.Form.Show()
    [Windows.Forms.Application]::DoEvents()
    if ($Screenshot) {
        $bitmap = New-Object Drawing.Bitmap($ui.Form.Width, $ui.Form.Height)
        $ui.Form.DrawToBitmap($bitmap, (New-Object Drawing.Rectangle(0, 0, $ui.Form.Width, $ui.Form.Height)))
        $bitmap.Save($Screenshot)
        $bitmap.Dispose()
    }
    Assert (-not $ui.Start.Enabled) 'Install enabled before ZIP selection.'
    $ui.Archive.Text = $game
    $ui.Start.Enabled = $true
    $ui.Start.PerformClick()
    Assert $ui.State.Running ('Worker did not start: ' + $ui.Details.Text)
    Assert ($ui.Progress.Style -eq 'Marquee') 'Missing busy indicator.'
    $ui.Form.Close()
    Assert (-not $ui.Form.IsDisposed) 'Closing abandoned a running worker.'
    Wait-ForSetup
    Assert ($ui.State.Result -eq 1) ('Failure exit code lost: ' + $ui.Details.Text)
    Assert ($ui.Start.Enabled -and $ui.Start.Text -eq 'Retry') 'Retry unavailable.'
    Assert ($ui.Details.Text.Contains([string][char]0x3010)) 'Unicode worker output corrupted.'
    $ui.Start.PerformClick()
    Wait-ForSetup
    Assert ($ui.State.Result -eq 0) ('Retry failed: ' + $ui.Details.Text)
    Assert ($ui.Progress.Value -eq 100) 'Success indicator missing.'
    Assert ($ui.Status.Text.Contains('Setup finished')) 'Success instructions missing.'
    # A persistent log read failure must not prevent process completion or Retry.
    $reader = ${function:Read-SetupTail}
    try {
        function Read-SetupTail { throw 'injected sharing failure' }
        $ui.Start.Enabled = $true
        $ui.Start.PerformClick()
        Wait-ForSetup
        Assert ($ui.State.Result -eq 0) 'Log read failure hid process completion.'
    } finally { Set-Item Function:Read-SetupTail $reader }
    # Small viewport and enlarged controls remain reachable through scrolling.
    $ui.Form.ClientSize = New-Object Drawing.Size(560, 400)
    $ui.Form.Scale((New-Object Drawing.SizeF(1.5, 1.5)))
    $ui.Form.ClientSize = New-Object Drawing.Size(560, 400)
    $ui.Form.ScrollControlIntoView($ui.Export)
    [Windows.Forms.Application]::DoEvents()
    Assert ($ui.Form.AutoScroll -and $ui.Form.VerticalScroll.Visible) 'Small display has no scrollbar.'
    Assert ($ui.Export.Bottom -le $ui.Form.ClientSize.Height) 'Support control unreachable at enlarged scale.'
    Write-Output 'Wizard smoke test passed: Unicode, busy, close guard, failure, retry, success.'
} finally {
    $ui.Timer.Stop()
    $ui.State.Running = $false
    $ui.Form.Close()
    $ui.Form.Dispose()
}
