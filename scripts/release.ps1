# GitHub Release Script for AURORA Local Agent MVP
# Automatically creates a GitHub release and uploads the build artifacts

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$GitHubToken,
    
    [string]$ProjectName = "AURORA Local Agent MVP",
    [string]$RepoOwner = "hwj20",
    [string]$RepoName = "engine_external",
    
    [switch]$Draft,
    [switch]$PreRelease
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$DistDir = Join-Path $RootDir "dist"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "$ProjectName - GitHub Release Script" -ForegroundColor Cyan
Write-Host "Version: v$Version" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if artifact exists
$projectSafeName = $ProjectName -replace ' ', '-'
$zipPath = Join-Path $DistDir "$projectSafeName-$Version-win-x64.zip"
if (-not (Test-Path $zipPath)) {
    Write-Host "Error: Build artifact not found at $zipPath" -ForegroundColor Red
    Write-Host "Please run build.ps1 first" -ForegroundColor Yellow
    exit 1
}

# GitHub API headers
$headers = @{
    "Authorization" = "token $GitHubToken"
    "Accept" = "application/vnd.github.v3+json"
    "Content-Type" = "application/json"
}

# Create release
Write-Host "`n[1/3] Creating GitHub release..." -ForegroundColor Yellow

$releaseBody = @{
    tag_name = "v$Version"
    target_commitish = "main"
    name = "$ProjectName v$Version"
    body = @"
## $ProjectName v$Version

### Changes
- See commit history for details

### Installation
1. Download `$projectSafeName-$Version-win-x64.zip`
2. Extract to your preferred location
3. Run `Start-AURORA.bat`

### Requirements
- Windows 10/11 x64
- No additional dependencies required (fully bundled)

### Auto-Update
The application will automatically check for updates on startup.
"@
    draft = $Draft.IsPresent
    prerelease = $PreRelease.IsPresent
} | ConvertTo-Json

$releaseUrl = "https://api.github.com/repos/$RepoOwner/$RepoName/releases"

try {
    $release = Invoke-RestMethod -Uri $releaseUrl -Method Post -Headers $headers -Body $releaseBody
    Write-Host "Release created: $($release.html_url)" -ForegroundColor Green
}
catch {
    Write-Host "Error creating release: $_" -ForegroundColor Red
    exit 1
}

# Upload asset
Write-Host "`n[2/3] Uploading release asset..." -ForegroundColor Yellow

$uploadUrl = $release.upload_url -replace '\{.*\}', ''
$assetName = "$projectSafeName-$Version-win-x64.zip"
$uploadHeaders = @{
    "Authorization" = "token $GitHubToken"
    "Accept" = "application/vnd.github.v3+json"
    "Content-Type" = "application/zip"
}

try {
    $asset = Invoke-RestMethod -Uri "$uploadUrl`?name=$assetName" -Method Post -Headers $uploadHeaders -InFile $zipPath
    Write-Host "Asset uploaded: $($asset.browser_download_url)" -ForegroundColor Green
}
catch {
    Write-Host "Error uploading asset: $_" -ForegroundColor Red
    exit 1
}

# Create latest.json for auto-updater
Write-Host "`n[3/3] Creating update manifest..." -ForegroundColor Yellow

$latestJson = @{
    version = $Version
    releaseDate = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
    url = $asset.browser_download_url
    sha256 = (Get-FileHash $zipPath -Algorithm SHA256).Hash
    releaseNotes = "https://github.com/$RepoOwner/$RepoName/releases/tag/v$Version"
} | ConvertTo-Json

$latestJsonPath = Join-Path $DistDir "latest.json"
$latestJson | Set-Content $latestJsonPath -Encoding UTF8

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Release Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Release URL: $($release.html_url)" -ForegroundColor White
Write-Host "Download URL: $($asset.browser_download_url)" -ForegroundColor White
Write-Host "`nNote: Upload latest.json to your release or hosting for auto-update" -ForegroundColor Yellow
