#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Update checker for GitHub releases
    Compares local version with latest GitHub release

.PARAMETER Owner
    GitHub repo owner (default: hwj20)

.PARAMETER Repo
    GitHub repo name (default: engine_external)
#>

param(
    [string]$Owner = "hwj20",
    [string]$Repo = "engine_external"
)

$ErrorActionPreference = "Continue"

Write-Host "Checking for updates..." -ForegroundColor Yellow

$RootDir = Split-Path -Parent $PSScriptRoot
$AppDir = Join-Path $RootDir "app"
$packageJson = Get-Content (Join-Path $AppDir "package.json") -Raw | ConvertFrom-Json
$LocalVersion = $packageJson.version

Write-Host "Local version: v$LocalVersion"

try {
    $response = Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$Repo/releases/latest" -Headers @{
        'Accept' = 'application/vnd.github.v3+json'
        'User-Agent' = 'AURORA-Updater'
    }
    
    $LatestVersion = $response.tag_name -replace '^v', ''
    Write-Host "Latest version: $($response.tag_name)"
    
    if ([version]$LatestVersion -gt [version]$LocalVersion) {
        Write-Host "✓ Update available!" -ForegroundColor Green
        Write-Host "Release URL: $($response.html_url)" -ForegroundColor Cyan
        
        $asset = $response.assets | Where-Object { $_.name -like "*win*.zip" } | Select-Object -First 1
        if ($asset) {
            Write-Host "Download: $($asset.browser_download_url)" -ForegroundColor Cyan
        }
    } else {
        Write-Host "✓ Already up to date" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ Failed to check updates: $_" -ForegroundColor Red
    exit 1
}
