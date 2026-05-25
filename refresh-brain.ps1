# Regenerate brain.json and redeploy the PWA + brain visualization.
# One command for the whole pipeline:
#   1. Activate venv, run `python -m scripts.dump_brain`
#   2. `flutter clean` (so static assets are picked up fresh)
#   3. `flutter build web`
#   4. `firebase deploy --only hosting`
#
# Run from anywhere:
#   .\refresh-brain.ps1
#
# Flags:
#   .\refresh-brain.ps1 -NoClean    # skip flutter clean (faster, but
#                                   # brain.json updates might miss)
#   .\refresh-brain.ps1 -DumpOnly   # just regenerate brain.json, no deploy

param(
    [switch]$NoClean,
    [switch]$DumpOnly
)

$ErrorActionPreference = "Stop"
$repoRoot   = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonDir  = Join-Path $repoRoot "python"
$flutterDir = Join-Path $repoRoot "flutter_app"
$venvActivate = Join-Path $pythonDir ".venv\Scripts\Activate.ps1"

if (-not (Test-Path $venvActivate)) {
    throw "venv not found at $venvActivate. Create it first: cd python; python -m venv .venv; .\.venv\Scripts\activate; pip install -e .[agent]"
}
if (-not (Test-Path $flutterDir)) {
    throw "flutter_app not found at $flutterDir"
}

Write-Host ""
Write-Host "Refreshing Theo's brain..." -ForegroundColor Cyan
Write-Host ""

# 1. dump brain.json
Write-Host "[1/4] Generating brain.json" -ForegroundColor Yellow
Set-Location $pythonDir
. $venvActivate
python -m scripts.dump_brain
if ($LASTEXITCODE -ne 0) { throw "dump_brain failed (exit $LASTEXITCODE)" }

if ($DumpOnly) {
    Write-Host ""
    Write-Host "DumpOnly mode - skipping flutter build + firebase deploy." -ForegroundColor Yellow
    Write-Host "brain.json is at $flutterDir\web\brain.json"
    return
}

# 2. clean (so the new brain.json is picked up; Flutter's incremental
#    build doesn't always recopy static assets)
Set-Location $flutterDir
if (-not $NoClean) {
    Write-Host ""
    Write-Host "[2/4] flutter clean" -ForegroundColor Yellow
    flutter clean
    if ($LASTEXITCODE -ne 0) { throw "flutter clean failed (exit $LASTEXITCODE)" }
} else {
    Write-Host ""
    Write-Host "[2/4] skipping flutter clean (-NoClean)" -ForegroundColor DarkGray
}

# 3. build
# --pwa-strategy=none disables the offline-first service worker so
# deploys reach the browser immediately. Trade-off: no offline support
# and no install-prompt for fresh PWA installs (existing installed
# instances on phones keep working).
Write-Host ""
Write-Host "[3/4] flutter build web --pwa-strategy=none" -ForegroundColor Yellow
flutter build web --pwa-strategy=none
if ($LASTEXITCODE -ne 0) { throw "flutter build web failed (exit $LASTEXITCODE)" }

# 4. deploy
Write-Host ""
Write-Host "[4/4] firebase deploy --only hosting" -ForegroundColor Yellow
firebase deploy --only hosting
if ($LASTEXITCODE -ne 0) { throw "firebase deploy failed (exit $LASTEXITCODE)" }

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Chat:  https://data-55089.web.app"
Write-Host "  Brain: https://data-55089.web.app/brain.html"
Write-Host ""
