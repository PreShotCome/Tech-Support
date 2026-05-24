@echo off
REM Double-click wrapper for start-theo.ps1.
REM Bypasses PowerShell's execution policy for this one invocation only,
REM so you don't have to globally permit unsigned scripts.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-theo.ps1" %*
