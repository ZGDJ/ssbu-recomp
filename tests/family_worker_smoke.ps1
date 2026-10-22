# Execute the actual worker with only desktop COM and process discovery replaced.
param([Parameter(Mandatory=$true)][string]$Repo,
      [switch]$WithSave, [switch]$Consent, [switch]$Update, [switch]$ImportSave)
$ErrorActionPreference = 'Stop'
$env:OPENSMASH_WORKER_TEST_ROOT = $Repo
function Get-CimInstance { param([string]$ClassName) return @() }
function New-Object {
    param([Parameter(Position=0)][string]$TypeName,
          [Parameter(Position=1)][object[]]$ArgumentList,
          [string]$ComObject)
    if ($ComObject) {
        if ($ComObject -ne 'WScript.Shell') { throw "Unexpected COM request: $ComObject" }
        $shell = [pscustomobject]@{}
        $shell | Add-Member ScriptMethod CreateShortcut {
            param($path)
            $link = [pscustomobject]@{ TargetPath=''; Arguments=''; WorkingDirectory=''; Description=''; RequestedPath=$path }
            $link | Add-Member ScriptMethod Save {
                # Never create the requested desktop link; record the observable request in the fixture.
                Add-Content -LiteralPath (Join-Path $env:OPENSMASH_WORKER_TEST_ROOT 'shortcut-requests.txt') -Value $this.RequestedPath
            }
            return $link
        }
        return $shell
    }
    Microsoft.PowerShell.Utility\New-Object @PSBoundParameters
}
$workerArgs = @{ Archive = (Join-Path $Repo 'game.zip'); NonInteractive = $true }
if ($WithSave) { $workerArgs.SaveArchive = Join-Path $Repo 'save.zip' }
if ($Consent) { $workerArgs.SaveConsent = $true }
if ($Update) { $workerArgs.Update = $true }
if ($ImportSave) { $workerArgs.ImportSave = $true }
$global:LASTEXITCODE = 0
& (Join-Path $Repo 'scripts\family_setup.ps1') @workerArgs
exit $LASTEXITCODE
