@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0scripts\family_setup.ps1" -Update
if errorlevel 1 echo Update did not complete. See the message above before retrying.
pause
