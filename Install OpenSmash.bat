@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0scripts\family_wizard.ps1"
if errorlevel 1 echo Setup did not complete. See the message above and run this helper again to resume.
pause
