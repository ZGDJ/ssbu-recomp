Add-Type -AssemblyName System.Windows.Forms
. (Join-Path $PSScriptRoot 'family_support.ps1')
$picker = New-Object Windows.Forms.SaveFileDialog
$picker.Filter = 'Support ZIP (*.zip)|*.zip'
$picker.FileName = 'OpenSmash-support-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.zip'
try {
    if ($picker.ShowDialog() -eq 'OK') {
        $null = Export-SetupSupport -Repo (Split-Path -Parent $PSScriptRoot) -Destination $picker.FileName -Status 'Collected using Collect Logs.bat'
        [void][Windows.Forms.MessageBox]::Show('Support ZIP saved. Review the text files, then send it to the person helping you. No game data or saves were collected; nothing was uploaded.', 'OpenSmash support')
    }
} catch {
    [void][Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Could not save support ZIP')
    exit 1
} finally { $picker.Dispose() }
