# Launches the TechSupport Firebase bridge in one step.
# Run from anywhere:
#   .\bridge.ps1
#
# Override defaults at the command line:
#   .\bridge.ps1 -KeyPath "C:\path\to\key.json" -ProjectId "other-project"

param(
    [string]$KeyPath   = $(if ($env:GOOGLE_APPLICATION_CREDENTIALS) { $env:GOOGLE_APPLICATION_CREDENTIALS } else { "C:\Users\Ian\data.json" }),
    [string]$ProjectId = $(if ($env:FIREBASE_PROJECT_ID) { $env:FIREBASE_PROJECT_ID } else { "data-55089" }),
    [string]$Backend   = "auto",
    [string]$Model     = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonDir = Join-Path $repoRoot "python"
$venvActivate = Join-Path $pythonDir ".venv\Scripts\Activate.ps1"

if (-not (Test-Path $venvActivate)) {
    throw "venv not found at $venvActivate. Create it first: cd python; python -m venv .venv; .\.venv\Scripts\activate; pip install -e .[firebase]"
}
if (-not (Test-Path $KeyPath)) {
    throw "Service-account JSON not found at $KeyPath. Pass -KeyPath to override."
}

Set-Location $pythonDir
. $venvActivate

$env:GOOGLE_APPLICATION_CREDENTIALS = $KeyPath
$env:FIREBASE_PROJECT_ID            = $ProjectId

Write-Host ""
Write-Host "TechSupport bridge" -ForegroundColor Cyan
Write-Host "  Project:    $ProjectId"
Write-Host "  Key:        $KeyPath"
Write-Host "  Backend:    $Backend"
if ($Model) { Write-Host "  Model:      $Model" }
Write-Host ""

$args = @("--backend", $Backend, "--project-id", $ProjectId)
if ($Model) { $args += @("--model", $Model) }

python -m agent.bridges.firebase_bridge @args
