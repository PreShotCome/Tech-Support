@echo off
REM Double-click wrapper for refresh-brain.ps1. Logs everything to a
REM file so we can see crashes that close the window too fast to read.
setlocal
set SCRIPT_DIR=%~dp0
set LOG_FILE=%SCRIPT_DIR%refresh-brain.log

echo Running refresh-brain.ps1 — full output also logged to:
echo   %LOG_FILE%
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "& '%SCRIPT_DIR%refresh-brain.ps1' %* *>&1 | Tee-Object -FilePath '%LOG_FILE%'"

echo.
echo === ps exit code: %ERRORLEVEL% ===
echo === log saved to: %LOG_FILE% ===
echo.
pause
endlocal
