# GitHub Release Script for AURORA Local Agent MVP
# Uses GitHub CLI (gh) with SSH authentication - no token needed

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [string]$ProjectName = "Engine External",
    [string]$RepoOwner = "hwj20",
    [string]$RepoName = "engine_external",
    
    [switch]$Draft,
    [switch]$PreRelease
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$DistDir = Join-Path $RootDir "dist"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "$ProjectName - GitHub Release Script (SSH)" -ForegroundColor Cyan
Write-Host "Version: v$Version" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if gh CLI is installed
Write-Host "`nChecking GitHub CLI..." -ForegroundColor Yellow
try {
    gh --version | Out-Null
}
catch {
    Write-Host "Error: GitHub CLI (gh) not found!" -ForegroundColor Red
    Write-Host "Install it from: https://cli.github.com/" -ForegroundColor Yellow
    exit 1
}

# Check if gh is authenticated with SSH
Write-Host "Checking SSH authentication..." -ForegroundColor Yellow
$ghAuth = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Not authenticated with gh CLI" -ForegroundColor Red
    Write-Host "Run: gh auth login" -ForegroundColor Yellow
    exit 1
}
Write-Host $ghAuth -ForegroundColor Green

# Check if artifact exists
$projectSafeName = $ProjectName -replace ' ', '-'
$zipPath = Join-Path $DistDir "$projectSafeName-$Version-win-x64.zip"
if (-not (Test-Path $zipPath)) {
    Write-Host "`nError: Build artifact not found at $zipPath" -ForegroundColor Red
    Write-Host "Please run build.ps1 first" -ForegroundColor Yellow
    exit 1
}

# Create release notes
$releaseNotes = @"
## $ProjectName v$Version

### Installation
1. Download ``$projectSafeName-$Version-win-x64.zip``
2. Extract to your preferred location
3. Run ``Start-AURORA.bat``

### Requirements
- Windows 10/11 x64
- No additional dependencies required (fully bundled)

### Auto-Update
The application will automatically check for updates on startup.
"@

# Create release using gh CLI
Write-Host "`n[1/2] Creating GitHub release..." -ForegroundColor Yellow

$ghArgs = @(
    "release", "create", "v$Version",
    "--title=$ProjectName v$Version",
    "--notes=$releaseNotes"
)

if ($Draft) {
    $ghArgs += "--draft"
}
if ($PreRelease) {
    $ghArgs += "--prerelease"
}

try {
    gh @ghArgs $zipPath
    Write-Host "Release created successfully!" -ForegroundColor Green
}
catch {
    Write-Host "Error creating release: $_" -ForegroundColor Red
    exit 1
}

# Create latest.json for auto-updater
Write-Host "`n[2/2] Creating update manifest..." -ForegroundColor Yellow

$sha512Hash = (Get-FileHash $zipPath -Algorithm SHA512).Hash
$fileSize = (Get-Item $zipPath).Length

$latestJson = @{
    version = $Version
    releaseDate = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    sha512 = $sha512Hash
    releaseNotes = "https://github.com/$RepoOwner/$RepoName/releases/tag/v$Version"
    files = @(
        @{
            url = "https://github.com/$RepoOwner/$RepoName/releases/download/v$Version/$projectSafeName-$Version-win-x64.zip"
            sha512 = $sha512Hash
            size = $fileSize
        }
    )
} | ConvertTo-Json -Depth 10

$latestJsonPath = Join-Path $DistDir "latest.json"
$latestJson | Set-Content $latestJsonPath -Encoding UTF8

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Release Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Release: https://github.com/$RepoOwner/$RepoName/releases/tag/v$Version" -ForegroundColor White
Write-Host "`nLatest manifest: $latestJsonPath" -ForegroundColor Yellow
Write-Host "Content:`n$latestJson" -ForegroundColor White
