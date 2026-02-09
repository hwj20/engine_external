# AURORA Local Agent MVP Startup Script
# Starts backend first, then frontend

$ErrorActionPreference = "Continue"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "  AURORA Local Agent MVP" -ForegroundColor Cyan
Write-Host "  Startup Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Get project root directory
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Project directory: $RootDir" -ForegroundColor Green

# Check backend and frontend directories
$BackendDir = Join-Path $RootDir "backend"
$AppDir = Join-Path $RootDir "app"

if (-not (Test-Path $BackendDir)) {
    Write-Host "ERROR: Backend directory not found: $BackendDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $AppDir)) {
    Write-Host "ERROR: Frontend directory not found: $AppDir" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting backend..." -ForegroundColor Yellow
Write-Host "Location: $BackendDir" -ForegroundColor Gray

# Start backend (background)
$BackendProcess = Start-Process -FilePath "python" -ArgumentList "-u main.py" -WorkingDirectory $BackendDir -NoNewWindow -PassThru
$BackendPID = $BackendProcess.Id
Write-Host "Backend started (PID: $BackendPID)" -ForegroundColor Green
Write-Host ""

# Wait for backend to be ready
Write-Host "Waiting for backend service..." -ForegroundColor Yellow
$MaxRetries = 30
$Retry = 0
$BackendReady = $false

while ($Retry -lt $MaxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8787/health" -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $BackendReady = $true
            break
        }
    } catch {
        # Ignore errors, retry
    }
    $Retry++
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 1
}

Write-Host ""
if ($BackendReady) {
    Write-Host "Backend service is ready!" -ForegroundColor Green
} else {
    Write-Host "Backend may be starting slowly, continuing with frontend..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting frontend..." -ForegroundColor Yellow
Write-Host "Location: $AppDir" -ForegroundColor Gray
Write-Host ""

# Start frontend (blocking, with --skip-backend since we started backend above)
Push-Location $AppDir
try {
    npx electron . --skip-backend
} finally {
    Pop-Location
    
    Write-Host ""
    Write-Host "Frontend closed, shutting down backend..." -ForegroundColor Yellow
    
    # Close backend process
    try {
        Stop-Process -Id $BackendPID -ErrorAction SilentlyContinue
        Write-Host "Backend stopped" -ForegroundColor Green
    } catch {
        Write-Host "Failed to stop backend" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Goodbye!" -ForegroundColor Cyan
