# TechSupport — local test harness.
#
# This is the script to run on your Windows PC to validate everything works.
# Designed to be safe to re-run. It will:
#   1. Check .NET 8 SDK is installed
#   2. Build the whole solution
#   3. Offer to launch Agent + ConsentPrompt + Console for a loopback test
#
# Usage:
#   .\scripts\test.ps1               # build + check
#   .\scripts\test.ps1 -Run          # build + launch everything for a manual loopback test
#   .\scripts\test.ps1 -Run -Stop    # stop any agent/console you started earlier and exit

[CmdletBinding()]
param(
    [switch]$Run,
    [switch]$Stop,
    [string]$Configuration = "Debug"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Write-Section($text) {
    Write-Host ""
    Write-Host "==> $text" -ForegroundColor Cyan
}

function Stop-TestProcesses {
    Write-Section "Stopping any running agent / console / consent processes"
    foreach ($name in @("TechSupport.Agent", "TechSupport.Console", "TechSupport.ConsentPrompt")) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host "  killing PID $($_.Id) ($($_.ProcessName))"
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($Stop) {
    Stop-TestProcesses
    return
}

Write-Section "Checking .NET SDK"
$sdks = & dotnet --list-sdks 2>$null
if (-not $sdks) {
    throw "No .NET SDK found. Install .NET 8 (or newer) from https://dotnet.microsoft.com/download"
}
$compatible = $sdks | Where-Object {
    if ($_ -match "^(\d+)\.") { [int]$Matches[1] -ge 8 } else { $false }
}
if (-not $compatible) {
    throw "Need .NET 8 SDK or newer to build. Installed SDKs:`n$($sdks -join "`n")"
}
Write-Host ($compatible -join "`n")

# The apps target net8.0. To RUN them you need either the .NET 8 Desktop
# Runtime, or roll-forward enabled. Check for the desktop runtime here so
# the user sees a clear hint before launching anything.
$runtimes = & dotnet --list-runtimes 2>$null | Where-Object {
    $_ -match "Microsoft\.WindowsDesktop\.App 8\."
}
if (-not $runtimes -and $Run) {
    Write-Host ""
    Write-Host "WARNING: .NET 8 Desktop Runtime not detected. The WPF apps need it to run." -ForegroundColor Yellow
    Write-Host "         Install from: https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Yellow
    Write-Host "         (Pick the 'Desktop Runtime' x64 download.)" -ForegroundColor Yellow
    Write-Host ""
}

Write-Section "Restoring packages"
& dotnet restore "$repoRoot\TechSupport.sln" | Out-Null

# Kill any previous run before building — otherwise the loaded agent
# holds bin\...\TechSupport.Shared.dll open and the copy fails.
if ($Run) {
    Stop-TestProcesses
}

Write-Section "Building solution ($Configuration)"
& dotnet build "$repoRoot\TechSupport.sln" -c $Configuration --nologo
if ($LASTEXITCODE -ne 0) {
    throw "Build failed. Fix the errors above before continuing."
}

$tfm = "net8.0-windows10.0.19041.0"
$agentExe   = "$repoRoot\src\TechSupport.Agent\bin\$Configuration\$tfm\TechSupport.Agent.exe"
$consoleExe = "$repoRoot\src\TechSupport.Console\bin\$Configuration\$tfm\TechSupport.Console.exe"
$consentExe = "$repoRoot\src\TechSupport.ConsentPrompt\bin\$Configuration\$tfm\TechSupport.ConsentPrompt.exe"

Write-Section "Build outputs"
foreach ($p in @($agentExe, $consoleExe, $consentExe)) {
    if (Test-Path $p) {
        Write-Host "  OK  $p"
    } else {
        Write-Host "  MISSING  $p" -ForegroundColor Red
    }
}

if (-not $Run) {
    Write-Section "Done. Pass -Run to launch a loopback test."
    return
}

Write-Section "Launching for loopback test"
Stop-TestProcesses

# Copy the consent prompt next to the agent so ConsentBroker finds it
# without falling back to the dev path.
$agentDir = Split-Path -Parent $agentExe
Copy-Item -Path (Join-Path (Split-Path -Parent $consentExe) "*") -Destination $agentDir -Force -Recurse

Write-Host "Starting agent..."
$agentProc = Start-Process -FilePath $agentExe -PassThru -WindowStyle Normal `
    -WorkingDirectory $agentDir `
    -RedirectStandardOutput "$repoRoot\.agent.log" -RedirectStandardError "$repoRoot\.agent.err"
Write-Host "  agent PID $($agentProc.Id), logs in .agent.log"

Start-Sleep -Seconds 2

Write-Host "Starting console..."
$consoleProc = Start-Process -FilePath $consoleExe -PassThru
Write-Host "  console PID $($consoleProc.Id)"

Write-Section "Loopback test instructions"
Write-Host @"

1. In the Console window, on the Home tab, enter:
       Host:  127.0.0.1
       Port:  7022
   and click Connect.

2. A consent dialog should appear in this same session. Click Allow.

3. You should see your own desktop mirrored in the Console.
   Move the mouse / press keys in the Console's remote-view pane —
   they will drive your real desktop (it's a loopback, so the cursor
   you're moving IS the one you're seeing).

4. When done, close the Console window. Then run:
       .\scripts\test.ps1 -Stop
   to clean up the agent process.

Agent log: $repoRoot\.agent.log
"@
