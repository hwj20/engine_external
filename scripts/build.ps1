# Build Script for AURORA Local Agent MVP
# This script packages both frontend (Electron) and backend (Python) into a single distributable

param(
    [string]$Version = "0.1.0",
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$BuildDir = Join-Path $RootDir "build"
$DistDir = Join-Path $RootDir "dist"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AURORA Local Agent MVP - Build Script" -ForegroundColor Cyan
Write-Host "Version: $Version" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Clean previous builds
Write-Host "`n[1/5] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
New-Item -ItemType Directory -Path $DistDir -Force | Out-Null

# Update version in package.json
Write-Host "`n[2/5] Updating version to $Version..." -ForegroundColor Yellow
$packageJsonPath = Join-Path $RootDir "app\package.json"
$packageJson = Get-Content $packageJsonPath -Raw | ConvertFrom-Json
$packageJson.version = $Version
$packageJson | ConvertTo-Json -Depth 10 | Set-Content $packageJsonPath -Encoding UTF8

# Build Python backend with PyInstaller
if (-not $SkipBackend) {
    Write-Host "`n[3/5] Building Python backend..." -ForegroundColor Yellow
    
    # Check if PyInstaller is installed
    $pyinstallerCheck = pip show pyinstaller 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing PyInstaller..." -ForegroundColor Gray
        pip install pyinstaller
    }
    
    # Create PyInstaller spec
    $backendDir = Join-Path $RootDir "backend"
    $specContent = @"
# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# Collect all backend files
backend_path = r'$backendDir'

a = Analysis(
    [os.path.join(backend_path, 'main.py')],
    pathex=[backend_path],
    binaries=[],
    datas=[
        (os.path.join(backend_path, 'agent'), 'agent'),
        # Note: data directory is NOT included - it's created at runtime
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'pydantic',
        'starlette',
        'anyio',
        'sniffio',
        'httptools',
        'dotenv',
        'click',
        'h11',
        'httpcore',
        'httpx',
        'openai',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='aurora-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
"@
    
    $specPath = Join-Path $BuildDir "backend.spec"
    $specContent | Set-Content $specPath -Encoding UTF8
    
    Push-Location $backendDir
    try {
        # Install dependencies
        Write-Host "Installing Python dependencies..." -ForegroundColor Gray
        pip install -r requirements.txt
        pip install pyinstaller httpx openai python-dotenv
        
        # Run PyInstaller
        Write-Host "Running PyInstaller..." -ForegroundColor Gray
        pyinstaller --clean --noconfirm $specPath --distpath (Join-Path $BuildDir "backend")
        
        if (-not (Test-Path (Join-Path $BuildDir "backend\aurora-backend.exe"))) {
            throw "Backend build failed - executable not found"
        }
        Write-Host "Backend build successful!" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
} else {
    Write-Host "`n[3/5] Skipping backend build..." -ForegroundColor Gray
}

# Build Electron frontend
if (-not $SkipFrontend) {
    Write-Host "`n[4/5] Building Electron frontend..." -ForegroundColor Yellow
    
    $appDir = Join-Path $RootDir "app"
    Push-Location $appDir
    try {
        # Install dependencies
        Write-Host "Installing npm dependencies..." -ForegroundColor Gray
        npm install
        npm install electron-updater --save
        
        # Run electron-builder
        Write-Host "Running electron-builder..." -ForegroundColor Gray
        npm run dist
        
        Write-Host "Frontend build successful!" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
} else {
    Write-Host "`n[4/5] Skipping frontend build..." -ForegroundColor Gray
}

# Package everything together
Write-Host "`n[5/5] Creating final package..." -ForegroundColor Yellow

$finalDir = Join-Path $DistDir "AURORA-Local-Agent-$Version-win-x64"
New-Item -ItemType Directory -Path $finalDir -Force | Out-Null

# Copy backend
if (Test-Path (Join-Path $BuildDir "backend\aurora-backend.exe")) {
    Copy-Item (Join-Path $BuildDir "backend\aurora-backend.exe") $finalDir
}

# Copy frontend (find the unpacked directory or installer)
$electronDist = Join-Path $RootDir "app\dist"
$unpackedDir = Get-ChildItem $electronDist -Directory -Filter "*unpacked*" | Select-Object -First 1
if ($unpackedDir) {
    Copy-Item "$($unpackedDir.FullName)\*" $finalDir -Recurse -Force
}

# Copy data directory template
$dataDir = Join-Path $finalDir "data"
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null

# Create launcher script
$launcherContent = @'
@echo off
echo Starting AURORA Local Agent...
start "" "%~dp0aurora-backend.exe"
timeout /t 2 /nobreak >nul
start "" "%~dp0AURORA Local Agent MVP.exe"
'@
$launcherContent | Set-Content (Join-Path $finalDir "Start-AURORA.bat") -Encoding ASCII

# Create version file
@{
    version = $Version
    buildDate = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    platform = "win-x64"
} | ConvertTo-Json | Set-Content (Join-Path $finalDir "version.json") -Encoding UTF8

# Create ZIP for release
$zipPath = Join-Path $DistDir "AURORA-Local-Agent-$Version-win-x64.zip"
Compress-Archive -Path "$finalDir\*" -DestinationPath $zipPath -Force

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Output: $zipPath" -ForegroundColor White
Write-Host "`nTo release on GitHub:" -ForegroundColor Yellow
Write-Host "1. Create a new release with tag v$Version" -ForegroundColor White
Write-Host "2. Upload: $zipPath" -ForegroundColor White
