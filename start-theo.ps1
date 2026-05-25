# Press-and-play launcher for Theo.
#
# Double-click start-theo.bat from File Explorer, OR right-click this
# .ps1 -> "Run with PowerShell". One-time setup at the bottom of this
# file shows how to make a desktop / Start-menu shortcut with an icon.
#
# What this does:
#   - Opens a new PowerShell window titled "Theo bridge"
#   - In that window: activates the venv, sets env vars, runs the bridge
#   - Returns immediately so this launcher process exits cleanly
#
# Override the Firebase key path or project at the launcher's command line:
#   .\start-theo.ps1 -KeyPath "C:\path\to\key.json" -ProjectId "other-project"
#   .\start-theo.ps1 -OpenPwa "https://your-app.web.app"   # also open the PWA
#   .\start-theo.ps1 -NoCli                                # bridge only, skip CLI

param(
    [string]$KeyPath   = $(if ($env:GOOGLE_APPLICATION_CREDENTIALS) { $env:GOOGLE_APPLICATION_CREDENTIALS } else { "C:\Users\Ian\data.json" }),
    [string]$ProjectId = $(if ($env:FIREBASE_PROJECT_ID) { $env:FIREBASE_PROJECT_ID } else { "data-55089" }),
    [string]$Backend   = "auto",
    [string]$Model     = "",
    [string]$OpenPwa   = "",        # URL of the deployed PWA; opens in default browser if set
    [switch]$NoCli                   # skip the terminal CLI window (bridge only)
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bridgePs1 = Join-Path $repoRoot "bridge.ps1"
$cliPs1    = Join-Path $repoRoot "cli.ps1"

if (-not (Test-Path $bridgePs1)) {
    throw "bridge.ps1 not found at $bridgePs1"
}
if (-not $NoCli -and -not (Test-Path $cliPs1)) {
    throw "cli.ps1 not found at $cliPs1"
}

Write-Host ""
Write-Host "Starting Theo..." -ForegroundColor Cyan
Write-Host "  Project: $ProjectId"
Write-Host "  Key:     $KeyPath"
Write-Host ""

# Prefer Windows Terminal (`wt`) so bridge + CLI live as tabs in ONE
# window. Falls back to separate powershell windows when wt isn't
# installed (older Win10 setups).
$wt = Get-Command wt -ErrorAction SilentlyContinue

if ($wt) {
    # Build a single wt invocation with one tab per surface. The bare
    # ";" between tabs is wt's command separator. Start-Process with
    # an array ArgumentList passes each element as its own argv slot,
    # so the semicolon survives untouched.
    $wtArgs = @(
        "new-tab", "--title", "Theo bridge",
        "-d", $repoRoot,
        "powershell.exe", "-NoExit", "-File", $bridgePs1,
        "-KeyPath",   $KeyPath,
        "-ProjectId", $ProjectId,
        "-Backend",   $Backend
    )
    if ($Model) {
        $wtArgs += @("-Model", $Model)
    }
    if (-not $NoCli) {
        $wtArgs += @(
            ";",
            "new-tab", "--title", "Theo CLI",
            "-d", $repoRoot,
            "powershell.exe", "-NoExit", "-File", $cliPs1
        )
    }
    Start-Process -FilePath $wt.Source -ArgumentList $wtArgs
    Write-Host "  Surface:        Windows Terminal (one window, tabs)"
} else {
    # Fallback: separate PowerShell windows, one per surface.
    $bridgeCmd = "`$Host.UI.RawUI.WindowTitle = 'Theo bridge'; & '$bridgePs1' -KeyPath '$KeyPath' -ProjectId '$ProjectId' -Backend '$Backend'"
    if ($Model) { $bridgeCmd += " -Model '$Model'" }
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoExit", "-Command", $bridgeCmd) `
        -WorkingDirectory $repoRoot

    if (-not $NoCli) {
        $cliCmd = "`$Host.UI.RawUI.WindowTitle = 'Theo CLI'; & '$cliPs1'"
        Start-Process -FilePath "powershell.exe" `
            -ArgumentList @("-NoExit", "-Command", $cliCmd) `
            -WorkingDirectory $repoRoot
    }
    Write-Host "  Surface:        separate PowerShell windows (install Windows Terminal for tabs)"
}

# Optionally open the PWA in the default browser.
if ($OpenPwa) {
    Start-Process $OpenPwa
}

Write-Host "Theo is online." -ForegroundColor Green
Write-Host "  Bridge window:  'Theo bridge' (Ctrl+C in that window to stop)"
if (-not $NoCli) { Write-Host "  CLI window:     'Theo CLI'" }
if ($OpenPwa)    { Write-Host "  PWA:            opened in browser" }
Write-Host ""
Start-Sleep -Seconds 2   # leave the message visible briefly before the launcher exits

# -----------------------------------------------------------------------
# One-time setup — create a desktop shortcut with an icon:
#
#   1. Right-click start-theo.bat -> "Send to" -> "Desktop (create shortcut)".
#   2. On the desktop, right-click the new shortcut -> Properties.
#   3. (optional) "Change Icon..." -> Browse to an .ico file. Microsoft's
#      icon library has plenty: shell32.dll, imageres.dll, or download one.
#   4. (optional) Rename the shortcut to "Theo".
#
# Auto-start on Windows login:
#   1. Press Win+R, type:  shell:startup  -> Enter.
#   2. Drag a copy of the shortcut into that folder. Done.
# -----------------------------------------------------------------------
