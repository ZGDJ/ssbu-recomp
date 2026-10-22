# Install SSBU.bat runs this. It puts a private Python 3.13 into <repo>\deps\python (the python.org "embeddable" package,
# checked against its SHA-256), installs pip and requirements.txt there, then opens the installer window
# (scripts\installer_window.ps1). Nothing is installed system-wide, PATH and the registry are not touched; deleting the
# deps folder removes everything. Only if that private install fails it falls back to a Python already on the PC
# (or the per-user python.org installer) and the older tkinter window (scripts\installer_gui.py).
# Structure of the download/verify/install steps adapted from WindowSmash's tools\install_windowsmash.ps1 (SNO2207).
param([switch]$NoLaunch, [switch]$PrivateOnly, [switch]$NonInteractive)
$ErrorActionPreference = 'Stop'
if (-not $NonInteractive) { Add-Type -AssemblyName System.Windows.Forms }
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$repo = Split-Path -Parent $PSScriptRoot
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'

# --- pinned downloads (hashes taken from files fetched on 2026-10-19) ---
$pyVersion = '3.13.16'
$embedUrl = "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-embed-amd64.zip"
$embedSha = '97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297'
$pipName = 'pip-26.2.1-py3-none-any.whl'
$pipUrl = 'https://files.pythonhosted.org/packages/f3/6e/1736e5b4ae2b778ef2f81c47d797de9f891d4d8acb047a24ca37a60294dd/pip-26.2.1-py3-none-any.whl'
$pipSha = '71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e'
# the older fallback: the per-user python.org installer
$fullVersion = '3.13.16'
$fullUrl = "https://www.python.org/ftp/python/$fullVersion/python-$fullVersion-amd64.exe"
$fullSha = 'fb4f9f5d438b2396da0086dc70b935c530cb578e37adc6d354f7ad2037fee83b'

$dl = Join-Path $repo 'build\downloads'
$depsPy = Join-Path $repo 'deps\python'
$pyExe = Join-Path $depsPy 'python.exe'

function Say([string]$text, [string]$buttons = 'OK', [string]$icon = 'Information') {
    if ($NonInteractive) { throw $text }
    return [System.Windows.Forms.MessageBox]::Show($text, 'SSBU installer', $buttons, $icon)
}

function Get-Verified([string]$url, [string]$file, [string]$sha) {
    if ((Test-Path -LiteralPath $file) -and (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -eq $sha.ToUpper()) { return }
    # Publish only a complete, verified download. An interrupted .download-part is safe to overwrite on Retry.
    $part = "$file.download-part"
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Write-Host "Downloading $(Split-Path -Leaf $file) (attempt $attempt/3; timeout 120 seconds) ..."
            Invoke-WebRequest -Uri $url -OutFile $part -UseBasicParsing -TimeoutSec 120
            $h = (Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash
            if ($h -ne $sha.ToUpper()) { throw "SHA-256 mismatch: got $h" }
            Move-Item -LiteralPath $part -Destination $file -Force
            return
        } catch {
            Write-Host "Download attempt $attempt failed: $($_.Exception.Message)"
            if ($attempt -eq 3) {
                throw "Could not download or verify $(Split-Path -Leaf $file) after 3 attempts. Check your connection, free disk space, and folder permissions, then choose Retry. Details: $($_.Exception.Message)"
            }
            Start-Sleep -Seconds 2
        }
    }
}

# Only move direct children of this install's real deps directory; reject junctions/symlinks.
function Assert-PrivatePath([string]$path) {
    $parent = [IO.Path]::GetFullPath((Join-Path $repo 'deps')).TrimEnd('\')
    $full = [IO.Path]::GetFullPath($path)
    if ((Split-Path -Parent $full) -ne $parent) { throw "Unsafe private Python path: $path" }
    foreach ($candidate in @($repo, $parent, $full)) {
        if (Test-Path -LiteralPath $candidate) {
            if ((Get-Item -LiteralPath $candidate -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Private Python recovery cannot use a linked folder: $candidate. Use a regular installation folder."
            }
        }
    }
}

# Files from a downloaded ZIP carry the Mark-of-the-Web; clear it so Windows does not block the scripts and tools.
function Unblock-Tree {
    try {
        Get-ChildItem -LiteralPath $repo -Recurse -File -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notlike "$repo\deps\*" -and $_.FullName -notlike "$repo\build\*" -and $_.FullName -notlike "$repo\.git\*" } |
            Unblock-File -ErrorAction SilentlyContinue
    } catch {}
}

function Test-Private([string]$exe = $pyExe) {
    if (-not (Test-Path -LiteralPath $exe)) { return $false }
    try {
        & $exe -c "import numpy, lz4, zstandard, PIL, unicorn, capstone, Crypto" 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

function Install-Private {
    New-Item -ItemType Directory -Force $dl | Out-Null
    # Build a fresh runtime beside the active one. Interrupted attempts never poison the next Retry.
    $stage = Join-Path $repo ("deps\python-stage-" + [Guid]::NewGuid().ToString('N'))
    Assert-PrivatePath $depsPy
    Assert-PrivatePath $stage
    $zip = Join-Path $dl "python-$pyVersion-embed-amd64.zip"
    Get-Verified $embedUrl $zip $embedSha
    New-Item -ItemType Directory -Force $stage | Out-Null
    Write-Host 'Preparing a fresh private Python runtime ...'
    Expand-Archive -LiteralPath $zip -DestinationPath $stage -Force
    $installExe = Join-Path $stage 'python.exe'
    # enable site-packages: pythonXY._pth has "#import site"
    $pth = Get-ChildItem $stage -Filter 'python*._pth' | Select-Object -First 1
    if (-not $pth) { throw 'python._pth not found in the embeddable package' }
    $txt = (Get-Content $pth.FullName) -replace '^\s*#\s*import site', 'import site'
    Set-Content -Path $pth.FullName -Value $txt -Encoding ASCII
    # pip, from its pinned wheel: a wheel is a zip Python can run directly
    $whl = Join-Path $dl $pipName
    Get-Verified $pipUrl $whl $pipSha
    Write-Host 'Installing pip and the Python packages (about 100 MB) ...'
    $site = Join-Path $stage 'Lib\site-packages'
    New-Item -ItemType Directory -Force $site | Out-Null
    $zipCopy = Join-Path $dl 'pip-wheel.zip'
    Copy-Item $whl $zipCopy -Force
    Expand-Archive -LiteralPath $zipCopy -DestinationPath $site -Force     # a wheel is a zip: unpacking it is installing pip
    Remove-Item $zipCopy -Force
    # The embeddable Python ignores the script's folder in sys.path (its ._pth file makes it isolated), but our scripts
    # import their neighbours. A .pth line puts the running script's folder first, as a normal Python does.
    Set-Content -Path (Join-Path $site 'ssbu_scriptdir.pth') -Encoding ASCII -Value `
        "import sys, os; a = sys.argv[0] if sys.argv else ''; (a and os.path.isfile(a) and sys.path.insert(0, os.path.dirname(os.path.abspath(a))))"
    $ErrorActionPreference = 'Continue' # Native stderr is diagnostic; test the exit code.
    & $installExe -m pip --version
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) { throw "pip could not be installed (code $LASTEXITCODE)" }
    $ErrorActionPreference = 'Continue'
    & $installExe -m pip install --timeout 60 --retries 3 --only-binary=:all: --no-warn-script-location --disable-pip-version-check -r (Join-Path $repo 'requirements.txt')
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed (code $LASTEXITCODE)" }
    if (-not (Test-Private $installExe)) { throw 'the private Python does not import its packages' }
    $ErrorActionPreference = 'Stop'
    # Retain the previous runtime for recovery; no recursive deletion or overwrite of user data.
    Assert-PrivatePath $depsPy
    Assert-PrivatePath $stage
    if (Test-Path -LiteralPath $depsPy) {
        $backup = Join-Path $repo ("deps\python-backup-" + [Guid]::NewGuid().ToString('N'))
        Assert-PrivatePath $backup
        Move-Item -LiteralPath $depsPy -Destination $backup
        Write-Host "Previous private Python preserved in $(Split-Path -Leaf $backup)."
    }
    Move-Item -LiteralPath $stage -Destination $depsPy
    Write-Host 'Private Python is ready.'
}

# --- the older way, kept as a fallback ---
function Test-Python([string]$exe) {
    if (-not $exe -or -not (Test-Path $exe)) { return $false }
    if ($exe -like '*\WindowsApps\*') { return $false }          # the Microsoft Store alias, not a Python
    try {
        & $exe -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

function Find-Python {
    $c = @()
    try { $c += (& py -3 -c "import sys; print(sys.executable)" 2>$null) } catch {}
    try { $c += (Get-Command python.exe -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }) } catch {}
    foreach ($root in @("$env:LOCALAPPDATA\Programs\Python", $env:ProgramFiles, 'C:\')) {
        if (Test-Path $root) {
            $c += Get-ChildItem $root -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue |
                  Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'python.exe' }
        }
    }
    foreach ($exe in $c) { if (Test-Python $exe) { return $exe } }
    return $null
}

function Start-Fallback {
    $py = Find-Python
    if (-not $py) {
        $ans = Say ("The private Python could not be set up, so the installer needs Python (free, about 30 MB), which is not on this PC.`n`n" +
                    "Download Python $fullVersion from python.org and install it for your user only?`n" +
                    "(It can be removed later from Settings > Apps.)") 'YesNo' 'Question'
        if ($ans -ne 'Yes') { exit 1 }
        $file = Join-Path $dl "python-$fullVersion-amd64.exe"
        Get-Verified $fullUrl $file $fullSha
        # /passive: a progress bar and no questions; for this user only, no PATH or file-type changes
        $p = Start-Process -FilePath $file -Wait -PassThru -ArgumentList '/passive', 'InstallAllUsers=0', 'Include_launcher=0',
             'Include_test=0', 'Include_doc=0', 'Shortcuts=0', 'AssociateFiles=0', 'PrependPath=0'
        $py = Find-Python
        if ($p.ExitCode -ne 0 -or -not $py) {
            Say "Python could not be installed (code $($p.ExitCode)). Install it from https://www.python.org/downloads/ and run Install SSBU.bat again." 'OK' 'Error' | Out-Null
            exit 1
        }
    }
    Set-Content -Path (Join-Path $repo 'build\python_path.txt') -Value $py -Encoding ASCII
    $pyw = Join-Path (Split-Path -Parent $py) 'pythonw.exe'
    if (-not (Test-Path $pyw)) { $pyw = $py }
    if (-not $NoLaunch) { Start-Process -FilePath $pyw -ArgumentList "`"$repo\scripts\installer_gui.py`"" -WorkingDirectory $repo }
}

try {
    New-Item -ItemType Directory -Force (Join-Path $repo 'build') | Out-Null
    Unblock-Tree
    $ok = Test-Private
    if (-not $ok) {
        try { Install-Private; $ok = $true }
        catch {
            Write-Host "Private Python install failed: $($_.Exception.Message)"
            if ($PrivateOnly -or $NonInteractive) { throw }
            Write-Host 'Trying a Python already on this PC instead ...'
        }
    }
    if ($ok) {
        Set-Content -Path (Join-Path $repo 'build\python_path.txt') -Value $pyExe -Encoding ASCII
        if (-not $NoLaunch) {
            Start-Process -FilePath 'powershell.exe' -WorkingDirectory $repo -WindowStyle Hidden -ArgumentList @(
                '-NoProfile', '-ExecutionPolicy', 'Bypass', '-STA', '-WindowStyle', 'Hidden', '-File', "`"$repo\scripts\installer_window.ps1`"")
        }
    } else {
        if ($PrivateOnly -or $NonInteractive) { throw 'Private Python setup failed; no system installation was attempted. Check the network and retry.' }
        Start-Fallback
    }
} catch {
    Write-Host "SETUP STOPPED: $($_.Exception.Message)"
    if ($NonInteractive) { exit 1 }
    Say "The installer could not start: $($_.Exception.Message)" 'OK' 'Error' | Out-Null
    exit 1
}
