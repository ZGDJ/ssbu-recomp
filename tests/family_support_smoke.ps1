param([string]$Repo, [string]$Fixture)
$ErrorActionPreference = 'Stop'
. (Join-Path $Repo 'scripts\family_support.ps1')
$logs = Join-Path $Fixture 'build\logs'
$active = [IO.File]::Open((Join-Path $logs 'family-setup.log'), 'Open', 'ReadWrite', 'ReadWrite')
$locked = [IO.File]::Open((Join-Path $logs 'family-save.log'), 'Open', 'ReadWrite', 'None')
try {
    $result = Export-SetupSupport -Repo $Fixture -Destination (Join-Path $Fixture 'support.zip') -Status ('Failure in ' + $Fixture)
    if (-not (Test-Path -LiteralPath $result)) { throw 'Report missing' }
    $refused = $false
    try { Export-SetupSupport -Repo $Fixture -Destination $result | Out-Null } catch { $refused = $true }
    if (-not $refused) { throw 'Existing destination was overwritten' }
} finally { $locked.Dispose(); $active.Dispose() }
# A junction at build/logs must not expose a directory outside the install root.
$linked = Join-Path $Fixture 'linked'
New-Item -ItemType Directory -Path (Join-Path $linked 'build') | Out-Null
New-Item -ItemType Junction -Path (Join-Path $linked 'build\logs') -Target $logs | Out-Null
Export-SetupSupport -Repo $linked -Destination (Join-Path $Fixture 'linked.zip') | Out-Null
