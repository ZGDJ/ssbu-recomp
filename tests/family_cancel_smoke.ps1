param([string]$Repo, [string]$Fixture)
$ErrorActionPreference = 'Stop'
. (Join-Path $Repo 'scripts\family_wizard.ps1')
$worker = Join-Path $Fixture 'worker.ps1'
$childFile = Join-Path $Fixture 'child.ps1'
@'
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'child.pid'), [string]$PID)
while ($true) {
    [IO.File]::AppendAllText((Join-Path $PSScriptRoot 'heartbeat'), 'x')
    Start-Sleep -Milliseconds 50
}
'@ | Set-Content -LiteralPath $childFile -Encoding UTF8
@'
param([string]$Archive, [switch]$NonInteractive)
$child = Join-Path $PSScriptRoot 'child.ps1'
$command = "& '" + $child.Replace("'", "''") + "'"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
$p = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',$encoded)
$p.WaitForExit()
'@ | Set-Content -LiteralPath $worker -Encoding UTF8
foreach ($mode in @('cancel', 'dispose')) {
    $job = Start-SetupWorker $Fixture '' $worker
    try {
        $pidFile = Join-Path $Fixture 'child.pid'
        $deadline = [DateTime]::UtcNow.AddSeconds(15)
        while (-not (Test-Path $pidFile)) {
            if ([DateTime]::UtcNow -gt $deadline) { throw 'Child did not start' }
            Start-Sleep -Milliseconds 50
        }
        $child = Get-Process -Id ([int][IO.File]::ReadAllText($pidFile))
        [void]$child.Handle
        if ($mode -eq 'cancel') { Stop-SetupWorker $job } else { $job.Job.Dispose() }
        if (-not $job.Process.WaitForExit(10000)) { throw 'Parent survived cancellation' }
        if (-not $child.WaitForExit(10000)) { throw 'Child survived cancellation' }
        if ($mode -eq 'cancel' -and -not $job.Job.IsEmpty) { throw 'Job still has active descendants' }
        $beat = Join-Path $Fixture 'heartbeat'
        $length = (Get-Item $beat).Length
        Start-Sleep -Milliseconds 200
        if ((Get-Item $beat).Length -ne $length) { throw 'Child kept writing after cancellation' }
        Remove-Item -LiteralPath $pidFile
        $child.Dispose()
    } finally { $job.Job.Dispose(); $job.Process.Dispose() }
}
Write-Output 'Cancellation and job disposal terminate parent and child; no writes continue.'
