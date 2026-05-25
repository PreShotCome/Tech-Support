@echo off
REM Double-click wrapper for refresh-brain.ps1.
set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%refresh-brain.ps1" %*
pause
