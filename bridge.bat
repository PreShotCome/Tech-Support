@echo off
REM Double-clickable launcher for the bridge. Forwards any extra args to bridge.ps1.
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0bridge.ps1" %*
