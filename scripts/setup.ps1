#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick development setup script
    Installs all dependencies and configures the project

.PARAMETER CheckUpdates
    Check for npm and pip updates after setup
#>

param(
    [switch]$CheckUpdates
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$AppDir = Join-Path $RootDir "app"
$BackendDir = Join-Path $RootDir "backend"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AURORA Local Agent - Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check Node.js
Write-Host "`n[1/3] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Node.js not found. Please install from https://nodejs.org/" -ForegroundColor Red
    exit 1
}

# Install Node dependencies
Write-Host "`n[2/3] Installing Node dependencies..." -ForegroundColor Yellow
Push-Location $AppDir
try {
    npm ci
    if ($CheckUpdates) {
        Write-Host "Checking for npm updates..." -ForegroundColor Gray
        npm outdated
    }
    Write-Host "Node dependencies installed" -ForegroundColor Green
} finally {
    Pop-Location
}

# Check Python dependencies
Write-Host "`n[3/3] Installing Python dependencies..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version
    Write-Host "$pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "WARNING: Python not found in PATH" -ForegroundColor Yellow
}

Push-Location $BackendDir
try {
    pip install -r requirements.txt
    pip install pyinstaller  # For building
    if ($CheckUpdates) {
        Write-Host "Checking for pip updates..." -ForegroundColor Gray
        pip list --outdated
    }
    Write-Host "Python dependencies installed" -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "  Dev:     npm run dev (in ./app)" -ForegroundColor White
Write-Host "  Release: .\scripts\release.ps1 -Version major|minor|patch" -ForegroundColor White
Write-Host "  Build:   .\scripts\build-all.ps1" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
