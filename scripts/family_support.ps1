# Dot-source this file, then call Export-SetupSupport. No Python or developer tools required.
function Protect-SetupSupportText {
    param([string]$Text, [string]$Repo)
    foreach ($path in @($Repo, $env:USERPROFILE)) {
        if ([string]::IsNullOrEmpty($path)) { continue }
        $label = if ($path -eq $Repo) { '<INSTALL_FOLDER>' } else { '<USERPROFILE>' }
        foreach ($variant in @($path, $path.Replace('\', '/'), $path.Replace('\', '\\'))) {
            $Text = [regex]::Replace($Text, [regex]::Escape($variant), $label, 'IgnoreCase')
        }
    }
    $Text = [regex]::Replace($Text, '(?i)[a-z]:[\\/]+Users[\\/]+[^\\/\s"'']+', '<USERPROFILE>')
    # Query strings can carry signed download URLs. Keep the host/path for diagnosis only.
    $Text = [regex]::Replace($Text, '(?i)(https?://)[^\s/@]+:[^\s/@]+@', '$1<REDACTED>@')
    $Text = [regex]::Replace($Text, '(?i)(https?://[^\s?"''<>]+)\?[^\s"''<>]*', '$1?<REDACTED>')
    $Text = [regex]::Replace($Text, '(?im)(authorization\s*[:=]\s*)[^\r\n]+', '$1<REDACTED>')
    $Text = [regex]::Replace($Text, '(?i)((?:[\w-]*(?:token|password|passwd|secret|api[_-]?key|access[_-]?key|private[_-]?key)|[\w-]+_key)\s*["'']?\s*[:=]\s*)[^\r\n,;]+', '$1<REDACTED>')
    $Text = [regex]::Replace($Text, '(?i)\b(?:[0-9a-f]{32}|[0-9a-f]{64})\b', '<REDACTED_HEX>')
    return $Text
}

function Test-SetupSupportPlainPath {
    param([string]$Path, [string]$Repo)
    $current = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetFullPath($Repo).TrimEnd('\', '/')
    if ($current -ne $root -and -not $current.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { return $false }
    while ($current) {
        if (([IO.File]::GetAttributes($current) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { return $false }
        if ($current -eq $root) { return $true }
        $current = [IO.Path]::GetDirectoryName($current)
    }
    return $false
}

function Read-SetupSupportTail {
    param([string]$Path, [int]$Limit)
    # Allow the running installer to keep writing and rotating its logs.
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    try {
        $encoding = [Text.Encoding]::UTF8
        $first = $stream.ReadByte()
        $second = $stream.ReadByte()
        if ($first -eq 255 -and $second -eq 254) { $encoding = [Text.Encoding]::Unicode }
        if ($first -eq 254 -and $second -eq 255) { $encoding = [Text.Encoding]::BigEndianUnicode }
        $start = [Math]::Max(0, $stream.Length - $Limit)
        if ($encoding -ne [Text.Encoding]::UTF8) { $start -= $start % 2 }
        [void]$stream.Seek($start, [IO.SeekOrigin]::Begin)
        $buffer = New-Object byte[] $Limit
        $count = 0
        while ($count -lt $Limit) {
            $read = $stream.Read($buffer, $count, $Limit - $count)
            if ($read -eq 0) { break }
            $count += $read
        }
        $value = $encoding.GetString($buffer, 0, $count).TrimStart([char]0xFEFF)
        if ($start -gt 0) {
            # Drop a partial first line (including a possible truncated credential).
            $newline = $value.IndexOf("`n")
            $value = if ($newline -ge 0) { $value.Substring($newline + 1) } else { '' }
            $value = "[Earlier log output omitted]`r`n" + $value
        }
        return $value
    } finally { $stream.Dispose() }
}

function Export-SetupSupport {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [Parameter(Mandatory=$true)][string]$Destination,
        [string]$Status = 'Not supplied'
    )
    Add-Type -AssemblyName System.IO.Compression
    $Repo = [IO.Path]::GetFullPath($Repo).TrimEnd('\', '/')
    $Destination = [IO.Path]::GetFullPath($Destination)
    if ([IO.Path]::GetExtension($Destination) -ne '.zip') { throw 'Choose a filename ending in .zip for the support report.' }
    $notes = New-Object 'System.Collections.Generic.List[string]'
    $entries = New-Object 'System.Collections.Generic.Dictionary[string,string]'
    $revision = 'Unavailable (source checkout or missing package manifest)'
    try {
        $manifest = Join-Path $Repo 'INSTALLER-SOURCE.json'
        if ((Test-Path -LiteralPath $manifest -PathType Leaf) -and (Test-SetupSupportPlainPath $manifest $Repo) -and (Get-Item -LiteralPath $manifest).Length -le 2MB) {
            $data = [IO.File]::ReadAllText($manifest) | ConvertFrom-Json
            if ([string]$data.revision -match '^[a-fA-F0-9]{7,40}$') { $revision = [string]$data.revision }
        }
    } catch { $notes.Add('Installer revision could not be read.') }
    $disk = 'Unavailable'
    try {
        $drive = New-Object IO.DriveInfo([IO.Path]::GetPathRoot($Repo))
        $disk = 'Available bytes: ' + $drive.AvailableFreeSpace + '; total bytes: ' + $drive.TotalSize
    } catch { }
    $entries.Add('support-info.txt', (Protect-SetupSupportText (@"
OpenSmash setup support report
UTC: $([DateTime]::UtcNow.ToString('o'))
Installer revision: $revision
Windows/OS: $([Environment]::OSVersion.VersionString)
64-bit OS: $([Environment]::Is64BitOperatingSystem)
PowerShell: $($PSVersionTable.PSVersion)
Install drive: $disk
Status: $($Status.Substring(0, [Math]::Min($Status.Length, 4096)))
Only allowlisted installer log tails are included (256 KiB/file, 2 MiB total, up to 32 logs).
No game files, saves, keys, full environment, or directory listings are collected.
Common paths and credentials are redacted; review the report before sharing.
"@) $Repo))
    $remaining = 2MB
    try {
        $logs = Join-Path $Repo 'build\logs'
        if ((Test-Path -LiteralPath $logs -PathType Container) -and (Test-SetupSupportPlainPath $logs $Repo)) {
            # Current wizard GUIDs and older timestamp names; exact installer steps. Never recurse.
            $allowed = '^(?:wizard-(?:[a-f0-9]{32}|[0-9T_.-]+)(?:-errors)?|family-(?:setup|save|update)|bootstrap|install|setup|convert_(?:rtld|main|sdk|subsdk[0-9]+)|modules|tables|lift|sdk|compile|nro|link|check_(?:sdk|cxxrt|difftest|swkbd))\.log$'
            $files = @(Get-ChildItem -LiteralPath $logs -File -ErrorAction Stop | Where-Object { $_.Name -match $allowed } | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 32)
            foreach ($file in $files) {
                if ($remaining -lt 128) { $notes.Add('Total log limit reached; older logs omitted.'); break }
                try {
                    if (-not (Test-SetupSupportPlainPath $file.FullName $Repo)) { $notes.Add('Skipped reparse point: ' + $file.Name); continue }
                    $value = Protect-SetupSupportText (Read-SetupSupportTail $file.FullName ([Math]::Min(256KB, $remaining) - 128)) $Repo
                    $cap = [Math]::Min(256KB, $remaining)
                    # Sanitization may expand text; bound the exported bytes as well as the read.
                    while ([Text.Encoding]::UTF8.GetByteCount($value) -gt $cap) {
                        $value = "[Earlier log output omitted]`r`n" + $value.Substring([int][Math]::Ceiling($value.Length / 2.0))
                    }
                    $length = [Text.Encoding]::UTF8.GetByteCount($value)
                    if ($length -gt $remaining) { $notes.Add('Skipped log at total size limit: ' + $file.Name); continue }
                    $remaining -= $length
                    $entries.Add('logs/' + $file.Name, $value)
                } catch { $notes.Add('Could not read ' + $file.Name + ' (' + $_.Exception.GetType().Name + ').') }
            }
        } elseif (Test-Path -LiteralPath $logs -PathType Container) {
            $notes.Add('Logs excluded because the install folder, build, or logs directory is a reparse point (a link/junction or cloud placeholder). This exporter does not follow reparse points. Move the installation to a regular local folder, such as C:\OpenSmash, then export again.')
        } else { $notes.Add('No build/logs directory was available; setup may not have started yet.') }
    } catch { $notes.Add('Log enumeration failed (' + $_.Exception.GetType().Name + ').') }
    $entries.Add('collection-notes.txt', ($notes -join "`r`n"))
    # CreateNew avoids silently overwriting another report or a linked file.
    $output = [IO.File]::Open($Destination, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $zip = New-Object IO.Compression.ZipArchive($output, [IO.Compression.ZipArchiveMode]::Create, $true)
        try {
            foreach ($name in $entries.Keys) {
                $entry = $zip.CreateEntry($name)
                $writer = New-Object IO.StreamWriter($entry.Open(), (New-Object Text.UTF8Encoding($false)))
                try { $writer.Write($entries[$name]) } finally { $writer.Dispose() }
            }
        } finally { $zip.Dispose() }
    } finally { $output.Dispose() }
    return $Destination
}
