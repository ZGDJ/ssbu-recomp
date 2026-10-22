@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0scripts\family_wizard.ps1" -ImportSave
if errorlevel 1 echo Save import stopped. Read the message above before trying again.
pause
