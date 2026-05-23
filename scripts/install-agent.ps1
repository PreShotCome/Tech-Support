# Installs TechSupport.Agent as a Windows service. Run as administrator.
#
# Usage:
#   .\install-agent.ps1                          # install from default build output
#   .\install-agent.ps1 -BinaryPath "C:\path"    # install from custom path
#   .\install-agent.ps1 -Uninstall               # remove the service

[CmdletBinding()]
param(
    [string]$ServiceName = "TechSupport.Agent",
    [string]$DisplayName = "TechSupport Remote Agent",
    [string]$Description = "Provides remote support access for authorized technicians.",
    [string]$BinaryPath,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

if (-not ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(`
    [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "This script must be run as Administrator."
}

if ($Uninstall) {
    if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        sc.exe delete $ServiceName | Out-Null
        Write-Host "Removed service $ServiceName."
    } else {
        Write-Host "Service $ServiceName is not installed."
    }
    return
}

if (-not $BinaryPath) {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $BinaryPath = Join-Path $repoRoot "src\TechSupport.Agent\bin\Release\net8.0-windows10.0.19041.0\TechSupport.Agent.exe"
}

if (-not (Test-Path $BinaryPath)) {
    throw "Agent binary not found at $BinaryPath. Build the solution in Release first."
}

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Service $ServiceName already exists — stopping before reinstall."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 1
}

New-Service `
    -Name $ServiceName `
    -BinaryPathName "`"$BinaryPath`"" `
    -DisplayName $DisplayName `
    -Description $Description `
    -StartupType Automatic | Out-Null

Start-Service -Name $ServiceName
Write-Host "Installed and started $ServiceName."
