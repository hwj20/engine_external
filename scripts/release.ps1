#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Release Script for AURORA Local Agent
    Handles version bumping, git tagging, and GitHub release

.PARAMETER Version
    Version number (e.g., "1.0.1") or semantic shorthand (major/minor/patch)
    
.PARAMETER Message
    Release message
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$false)]
    [string]$Message = "Release"
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AURORA Local Agent - Release Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

function Test-VersionFormat {
    param([string]$Ver)
    $Ver -match '^\d+\.\d+\.\d+$'
}

# Handle semantic versioning
if ($Version -in @("major", "minor", "patch")) {
    Write-Host "`n[1/5] Reading current version..." -ForegroundColor Yellow
    $packageJsonPath = Join-Path $RootDir "app\package.json"
    $packageJson = Get-Content $packageJsonPath -Raw | ConvertFrom-Json
    $currentVersion = $packageJson.version
    
    Write-Host "Current version: $currentVersion"
    
    $parts = $currentVersion.Split('.')
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    $patch = [int]$parts[2]
    
    switch ($Version) {
        "major" { $major++; $minor = 0; $patch = 0 }
        "minor" { $minor++; $patch = 0 }
        "patch" { $patch++ }
    }
    
    $Version = "$major.$minor.$patch"
    Write-Host "New version: $Version"
} else {
    if (-not (Test-VersionFormat $Version)) {
        Write-Host "ERROR: Invalid version format (use X.Y.Z)" -ForegroundColor Red
        exit 1
    }
}

# Check git status
Write-Host "`n[2/5] Checking git status..." -ForegroundColor Yellow
try {
    $gitStatus = & git status --porcelain
    if ($gitStatus) {
        Write-Host "ERROR: Uncommitted changes detected" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "ERROR: git not available" -ForegroundColor Red
    exit 1
}

# Update version
Write-Host "`n[3/5] Updating version to v$Version..." -ForegroundColor Yellow
$packageJsonPath = Join-Path $RootDir "app\package.json"
$packageJson = Get-Content $packageJsonPath -Raw | ConvertFrom-Json
$packageJson.version = $Version
$packageJson | ConvertTo-Json -Depth 10 | Set-Content $packageJsonPath -Encoding UTF8

# Commit and tag
Write-Host "`n[4/5] Committing and tagging..." -ForegroundColor Yellow
& git add "$packageJsonPath"
& git commit -m "chore: release v$Version"
& git tag -a "v$Version" -m "Release $Version - $Message"

# Push
Write-Host "`n[5/5] Pushing to GitHub..." -ForegroundColor Yellow
& git push origin main
& git push origin "v$Version"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Release v$Version initiated!" -ForegroundColor Green
Write-Host "GitHub Actions will now build and release" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
