# Build Script for AURORA Local Agent MVP
# This script packages both frontend (Electron) and backend (Python) into a single distributable

param(
    [string]$Version = "0.1.1",
    [string]$ProjectName = "Engine External",
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$BuildDir = Join-Path $RootDir "build"
$DistDir = Join-Path $RootDir "dist"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "$ProjectName - Build Script" -ForegroundColor Cyan
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
    $projectBackendName = ($ProjectName -replace ' ', '-') + "-backend"
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
        'main',
        'agent',
        'agent.core',
        'agent.llm',
        'agent.context',
        'agent.store',
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
    excludes=['torch', 'tensorflow', 'pandas', 'numpy', 'scipy', 'matplotlib', 'jupyter', 'IPython'],
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
    name='$projectBackendName',
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
        
        if (-not (Test-Path (Join-Path $BuildDir "backend\$projectBackendName.exe"))) {
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

$projectSafeName = $ProjectName -replace ' ', '-'
$finalDir = Join-Path $DistDir "$projectSafeName-$Version-win-x64"
New-Item -ItemType Directory -Path $finalDir -Force | Out-Null

# Copy backend
if (Test-Path (Join-Path $BuildDir "backend\$projectBackendName.exe")) {
    Copy-Item (Join-Path $BuildDir "backend\$projectBackendName.exe") $finalDir
}

# Copy frontend - electron-builder creates files in win-unpacked subdirectory
$electronDist = Join-Path $RootDir "app\dist"
if (Test-Path $electronDist) {
    # Copy from win-unpacked directory (contains the .exe and resources)
    $unpackedDir = Get-ChildItem $electronDist -Directory -Filter "*unpacked*" | Select-Object -First 1
    if ($unpackedDir) {
        Get-ChildItem $unpackedDir.FullName | ForEach-Object {
            Copy-Item $_.FullName $finalDir -Recurse -Force
        }
    }
} else {
    Write-Host "Warning: Frontend dist folder not found at $electronDist" -ForegroundColor Yellow
}

# Copy data directory template
$dataDir = Join-Path $finalDir "data"
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null

# Create launcher script (bat)
$projectExeName = $ProjectName + ".exe"
$projectBackendExeName = $projectBackendName + ".exe"
$launcherContent = @"
@echo off
echo Starting $ProjectName...
start "" "%~dp0$projectBackendExeName"
timeout /t 2 /nobreak >nul
start "" "%~dp0$projectExeName"
"@
$launcherContent | Set-Content (Join-Path $finalDir "Start-AURORA.bat") -Encoding ASCII

# Create Python launcher wrapper for exe
$launcherPyName = "launcher.py"
$launcherBuildDir = Join-Path $BuildDir "launcher"
New-Item -ItemType Directory -Path $launcherBuildDir -Force | Out-Null
$launcherPyPath = Join-Path $launcherBuildDir $launcherPyName
$launcherPyContent = @'
import subprocess
import sys
import os
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
bat_path = os.path.join(script_dir, "Start-AURORA.bat")
log_path = os.path.join(script_dir, "Start-AURORA-launcher.log")

def log_msg(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(msg, flush=True)

try:
    # Clear old log
    if os.path.exists(log_path):
        os.remove(log_path)
    
    log_msg("=== Start-AURORA Launcher ===")
    log_msg(f"Script dir: {script_dir}")
    log_msg(f"Bat path: {bat_path}")
    log_msg(f"Bat exists: {os.path.exists(bat_path)}")
    
    if not os.path.exists(bat_path):
        log_msg("ERROR: Start-AURORA.bat not found!")
        log_msg(f"Files in directory: {os.listdir(script_dir)}")
        sys.exit(1)
    
    log_msg("Starting batch file with cmd.exe...")
    
    # Use cmd.exe to run the bat file
    result = subprocess.call(['cmd.exe', '/c', bat_path], 
                             cwd=script_dir,
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
    
    log_msg(f"Batch file completed with code: {result}")
    
except Exception as e:
    log_msg(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    log_msg(traceback.format_exc())
    sys.exit(1)
'@
$launcherPyContent | Set-Content $launcherPyPath -Encoding UTF8

# Package Python launcher as exe using PyInstaller
Write-Host "Creating launcher executable..." -ForegroundColor Gray
Push-Location $launcherBuildDir
try {
    pyinstaller --onefile --windowed --name "Start-AURORA" --distpath "dist" $launcherPyName
    
    if (Test-Path "dist\Start-AURORA.exe") {
        Copy-Item "dist\Start-AURORA.exe" $finalDir
        Write-Host "Launcher executable created successfully!" -ForegroundColor Green
    } else {
        Write-Host "Warning: Launcher executable not created" -ForegroundColor Yellow
    }
    
    # Clean up build artifacts
    Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force "dist" -ErrorAction SilentlyContinue
    Remove-Item "*.spec" -ErrorAction SilentlyContinue
}
catch {
    Write-Host "Warning: Failed to create launcher executable: $_" -ForegroundColor Yellow
}
finally {
    Pop-Location
}

# Create version file
@{
    version = $Version
    buildDate = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    platform = "win-x64"
} | ConvertTo-Json | Set-Content (Join-Path $finalDir "version.json") -Encoding UTF8

# Create ZIP for release
$zipPath = Join-Path $DistDir "$projectSafeName-$Version-win-x64.zip"
Compress-Archive -Path "$finalDir\*" -DestinationPath $zipPath -Force

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Output: $zipPath" -ForegroundColor White
Write-Host "`nTo release on GitHub:" -ForegroundColor Yellow
Write-Host "1. Create a new release with tag v$Version" -ForegroundColor White
Write-Host "2. Upload: $zipPath" -ForegroundColor White
