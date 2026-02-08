#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Complete build script for local development and distribution builds
    Builds both Python backend and Electron frontend

.PARAMETER Version
    Optional version override (default: read from package.json)

.PARAMETER SkipBackend
    Skip Python backend build

.PARAMETER SkipFrontend
    Skip Electron frontend build

.PARAMETER Portable
    Build portable version (Windows only)
#>

param(
    [string]$Version,
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$Portable
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$AppDir = Join-Path $RootDir "app"
$BackendDir = Join-Path $RootDir "backend"
$DistDir = Join-Path $AppDir "dist"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AURORA Local Agent - Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Read version
if (-not $Version) {
    $packageJson = Get-Content (Join-Path $AppDir "package.json") -Raw | ConvertFrom-Json
    $Version = $packageJson.version
}

Write-Host "Version: $Version`n" -ForegroundColor Green

# Clean
Write-Host "[1/4] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
New-Item -ItemType Directory -Path $DistDir -Force | Out-Null

# Build Python backend
if (-not $SkipBackend) {
    Write-Host "`n[2/4] Building Python backend..." -ForegroundColor Yellow
    
    # Check PyInstaller
    $pyCheck = pip show pyinstaller 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing PyInstaller..." -ForegroundColor Gray
        pip install pyinstaller
    }
    
    # Create resources directory
    $resourcesDir = Join-Path $AppDir "resources\bin"
    New-Item -ItemType Directory -Path $resourcesDir -Force | Out-Null
    
    # Build (--onedir mode for fast startup)
    Push-Location $BackendDir
    try {
        pyinstaller --name backend --distpath "$resourcesDir" main.py --add-data "system_prompts;system_prompts" --add-data "memory_plugins;memory_plugins"
        Write-Host "Backend built successfully" -ForegroundColor Green
    } finally {
        Pop-Location
    }
    
    # Copy data files (system_prompts already bundled via --add-data)
    Write-Host "Copying backend data files..." -ForegroundColor Gray
    $dataDir = Join-Path $AppDir "resources\data"
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
    
    $backendDataDir = Join-Path $BackendDir "data"
    if (Test-Path $backendDataDir) {
        Copy-Item -Recurse -Force $backendDataDir (Join-Path $dataDir "default_data")
    }
} else {
    Write-Host "`n[2/4] Skipping Python backend (use -SkipBackend)" -ForegroundColor Gray
}

# Install Node dependencies
Write-Host "`n[3/4] Installing Node dependencies..." -ForegroundColor Yellow
Push-Location $AppDir
try {
    npm ci
    Write-Host "Dependencies installed" -ForegroundColor Green
} finally {
    Pop-Location
}

# Build Electron
Write-Host "`n[4/4] Building Electron app..." -ForegroundColor Yellow
Push-Location $AppDir
try {
    if ($Portable) {
        Write-Host "Building portable version..." -ForegroundColor Gray
        npm run build:win -- --publish never
    } else {
        npm run build
    }
    Write-Host "Build completed successfully" -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Build completed!" -ForegroundColor Green
Write-Host "Output: $DistDir" -ForegroundColor Cyan
Get-ChildItem $DistDir -Recurse -Include "*.exe", "*.zip", "*.AppImage", "*.deb" | ForEach-Object {
    Write-Host "  - $($_.Name) ($([math]::Round($_.Length / 1MB, 2)) MB)" -ForegroundColor White
}
Write-Host "========================================" -ForegroundColor Cyan
