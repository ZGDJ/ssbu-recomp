# Synthetic bootstrap recovery tests; downloads and Python processes are replaced with fixtures.
$ErrorActionPreference = 'Stop'
# Load the native utility module before mocking one of its exported commands.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1')
$source = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\bootstrap.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$functions = $ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $false)
foreach ($function in $functions) { . ([scriptblock]::Create($function.Extent.Text)) }
$repo = Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts\local') ('opensmash-bootstrap-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $repo -Force | Out-Null
$dl = Join-Path $repo 'build\downloads'
$depsPy = Join-Path $repo 'deps\python'
$pyExe = Join-Path $depsPy 'python.exe'
New-Item -ItemType Directory -Path $dl -Force | Out-Null
$NonInteractive = $true
try {
    try { Say 'synthetic failure'; throw 'Expected noninteractive failure' } catch {
        if ($_.Exception.Message -ne 'synthetic failure') { throw }
    }
    try { Assert-PrivatePath (Join-Path $repo '..\outside'); throw 'Expected bounds failure' } catch {
        if ($_.Exception.Message -notlike 'Unsafe private Python path:*') { throw }
    }
    $script:attempts = 0
    function Start-Sleep { param($Seconds) }
    function Invoke-WebRequest {
        param($Uri, $OutFile, [switch]$UseBasicParsing, $TimeoutSec)
        if ($TimeoutSec -ne 120) { throw 'Missing bounded download timeout' }
        $script:attempts++
        [IO.File]::WriteAllText($OutFile, 'incomplete')
        if ($script:attempts -lt 3) { throw 'synthetic connection reset' }
        [IO.File]::WriteAllText($OutFile, 'verified')
    }
    $expected = Join-Path $dl 'expected'
    [IO.File]::WriteAllText($expected, 'verified')
    $sha = (Get-FileHash $expected).Hash
    $download = Join-Path $dl 'runtime.zip'
    Get-Verified 'https://fixture.invalid' $download $sha
    if ($script:attempts -ne 3 -or (Get-Content $download) -ne 'verified') { throw 'Retry publication failed' }
    Get-Verified 'https://fixture.invalid' $download $sha
    if ($script:attempts -ne 3) { throw 'Verified download was downloaded again' }
    $script:attempts = 0
    try { Get-Verified 'https://fixture.invalid' $download ('0' * 64); throw 'Expected hash failure' } catch {
        if ($_.Exception.Message -notlike 'Could not download or verify*after 3 attempts*') { throw }
    }
    if ($script:attempts -ne 3 -or (Get-Content $download) -ne 'verified') { throw 'Failure replaced existing cached file' }
    # Simulate an interrupted extraction, plus native pip calls, without network or installed dependencies.
    New-Item -ItemType Directory -Path $depsPy -Force | Out-Null
    Set-Content (Join-Path $depsPy 'preserve.txt') 'original interrupted runtime'
    $pyVersion = 'fixture'; $pipName = 'fixture.whl'
    function Get-Verified { param($url, $file, $sha) Set-Content $file 'fixture archive' }
    $script:failExtraction = $true
    function Expand-Archive {
        param($LiteralPath, $DestinationPath, [switch]$Force)
        if ($script:failExtraction) { throw 'synthetic interrupted extraction' }
        if ($DestinationPath -like '*python-stage-*' -and $DestinationPath -notlike '*site-packages') {
            Set-Content (Join-Path $DestinationPath 'python313._pth') '#import site'
            $exe = Join-Path $DestinationPath 'python.exe'
            Set-Item -Path "Function:global:$exe" -Value { $global:LASTEXITCODE = 0 }
        }
    }
    function Test-Private { param($exe) return $true }
    try { Install-Private; throw 'Expected interrupted extraction' } catch {
        if ($_.Exception.Message -ne 'synthetic interrupted extraction') { throw }
    }
    if ((Get-Content (Join-Path $depsPy 'preserve.txt')) -ne 'original interrupted runtime') { throw 'Failed staging changed current runtime' }
    $script:failExtraction = $false
    Install-Private
    if (-not (Test-Path (Join-Path $depsPy 'python313._pth'))) { throw 'Fresh runtime was not published' }
    $backups = @(Get-ChildItem (Join-Path $repo 'deps') -Directory -Filter 'python-backup-*')
    if ($backups.Count -ne 1 -or (Get-Content (Join-Path $backups[0].FullName 'preserve.txt')) -ne 'original interrupted runtime') { throw 'Original runtime not preserved' }
    Write-Host 'PASS: parser, noninteractive errors, bounds, retries, verified cache, hash failures, staged recovery and backup preservation'
} finally {
    # Disposable fixture only. Resolve and validate the exact target before recursive cleanup.
    $full = [IO.Path]::GetFullPath($repo)
    $temp = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts\local')).TrimEnd('\')
    if ((Split-Path -Parent $full) -eq $temp -and (Split-Path -Leaf $full) -like 'opensmash-bootstrap-test-*') {
        Remove-Item -LiteralPath $full -Recurse -Force
    }
}

