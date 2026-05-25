# Launches the TechSupport agent CLI in one step.
# Run from anywhere:
#   .\cli.ps1
#
# Used by start-theo.ps1 to open a "Theo CLI" window. Mirrors the
# shape of bridge.ps1 so both surfaces start the same way.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonDir = Join-Path $repoRoot "python"
$venvActivate = Join-Path $pythonDir ".venv\Scripts\Activate.ps1"

if (-not (Test-Path $venvActivate)) {
    Write-Host "venv not found at $venvActivate" -ForegroundColor Red
    Write-Host "Create it first:" -ForegroundColor Yellow
    Write-Host "  cd python; python -m venv .venv; .\.venv\Scripts\activate; pip install -e .[agent]"
    Read-Host "Press Enter to close"
    exit 1
}

Set-Location $pythonDir
. $venvActivate

Write-Host ""
Write-Host "TechSupport agent CLI" -ForegroundColor Cyan
Write-Host "  Repo: $repoRoot"
Write-Host ""

python -m agent.cli
