# Find files anywhere in the Tech-Support repo by name pattern.
# Skips the noise: .git, .venv, node_modules, build dirs, .dart_tool.
#
# Usage from the repo root (or anywhere if you give the full path):
#   .\find.ps1 brain.json
#   .\find.ps1 *.ico
#   .\find.ps1 theo
#   .\find.ps1 *.ps1
#
# The pattern is wildcard-style. If you don't include a `*`, the
# script wraps your input as `*<pattern>*` so partial matches work.

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Pattern,
    [switch]$ShowSize
)

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$skipDirs = @(".git", ".venv", "node_modules", "build", ".dart_tool",
              "__pycache__", ".cache", ".pytest_cache")

# If pattern has no wildcards, treat it as a substring search.
$effective = $Pattern
if ($Pattern -notmatch '[\*\?]') {
    $effective = "*$Pattern*"
}

Write-Host ""
Write-Host "Searching repo for: $effective" -ForegroundColor Cyan
Write-Host "  (skipping: $($skipDirs -join ', '))" -ForegroundColor DarkGray
Write-Host ""

$results = Get-ChildItem -Path $repoRoot -Recurse -Filter $effective `
    -File -ErrorAction SilentlyContinue |
    Where-Object {
        $skip = $false
        foreach ($d in $skipDirs) {
            if ($_.FullName -like "*\$d\*") { $skip = $true; break }
        }
        -not $skip
    } |
    Sort-Object LastWriteTime -Descending

if (-not $results -or $results.Count -eq 0) {
    Write-Host "  no matches" -ForegroundColor Yellow
    Write-Host ""
    exit
}

foreach ($f in $results) {
    $rel = $f.FullName.Substring($repoRoot.Length + 1)
    $age = [int]((Get-Date) - $f.LastWriteTime).TotalDays
    $ageStr = if ($age -eq 0) { "today" }
              elseif ($age -eq 1) { "1d ago" }
              else { "${age}d ago" }
    if ($ShowSize) {
        $size = if ($f.Length -lt 1024) { "$($f.Length)B" }
                elseif ($f.Length -lt 1MB) { "{0:N1}KB" -f ($f.Length / 1KB) }
                else { "{0:N1}MB" -f ($f.Length / 1MB) }
        Write-Host ("  {0,-12} {1,-8} {2}" -f $ageStr, $size, $rel)
    } else {
        Write-Host ("  {0,-12} {1}" -f $ageStr, $rel)
    }
}

Write-Host ""
Write-Host "  $($results.Count) match$(if ($results.Count -ne 1) { 'es' })" -ForegroundColor DarkGray
Write-Host ""
