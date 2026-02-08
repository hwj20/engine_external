#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Development launcher
    Starts backend API server and Electron dev environment
#>

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$AppDir = Join-Path $RootDir "app"
$BackendDir = Join-Path $RootDir "backend"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AURORA Local Agent - Dev Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Start backend in background
Write-Host "`n[1/2] Starting Python backend..." -ForegroundColor Yellow
Push-Location $BackendDir
$backendJob = Start-Process -NoNewWindow -PassThru python -ArgumentList "main.py"
Write-Host "Backend started (PID: $($backendJob.Id))" -ForegroundColor Green
Pop-Location

# Give backend time to start
Start-Sleep -Seconds 2

# Start frontend
Write-Host "`n[2/2] Starting Electron dev environment..." -ForegroundColor Yellow
Push-Location $AppDir
npm run dev
Pop-Location

# Cleanup
Write-Host "`nStopping backend..." -ForegroundColor Yellow
Stop-Process -Id $backendJob.Id -Force -ErrorAction SilentlyContinue

Write-Host "Dev session ended" -ForegroundColor Green
