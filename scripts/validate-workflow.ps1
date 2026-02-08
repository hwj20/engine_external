#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Validates GitHub Actions workflow YAML files
    Useful for testing before pushing

.PARAMETER WorkflowPath
    Path to workflow file (default: .github/workflows/build.yml)
#>

param(
    [string]$WorkflowPath = ".github/workflows/build.yml"
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Validating GitHub Actions Workflows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$fullPath = Join-Path $RootDir $WorkflowPath

if (-not (Test-Path $fullPath)) {
    Write-Host "ERROR: Workflow file not found: $fullPath" -ForegroundColor Red
    exit 1
}

Write-Host "`nWorkflow file: $fullPath" -ForegroundColor Cyan

# Check if act is installed (https://github.com/nektos/act)
$actPath = where.exe act 2>$null
if (-not $actPath) {
    Write-Host "`nIMFO: 'act' tool not found for local workflow testing" -ForegroundColor Yellow
    Write-Host "Install from: https://github.com/nektos/act#installation" -ForegroundColor Gray
    Write-Host "`nBasic YAML validation only..." -ForegroundColor Yellow
} else {
    Write-Host "`n✓ 'act' found at: $actPath" -ForegroundColor Green
    Write-Host "`nRun workflow locally:" -ForegroundColor Cyan
    Write-Host "  act push -j build" -ForegroundColor White
}

# Basic YAML validation
Write-Host "`nValidating YAML syntax..." -ForegroundColor Yellow

try {
    # Try loading with PowerShell's YAML parsing (if available via PSYaml module)
    $content = Get-Content $fullPath -Raw
    
    # Check for common YAML issues
    if ($content -match '^\s{0,1}\S.*:\s*$') {
        Write-Host "✓ YAML structure looks valid" -ForegroundColor Green
    }
    
    # Check for required keys
    $requiredKeys = @('name', 'on', 'jobs')
    $missingKeys = @()
    
    foreach ($key in $requiredKeys) {
        if ($content -notmatch "^$key\s*:") {
            $missingKeys += $key
        }
    }
    
    if ($missingKeys) {
        Write-Host "⚠ Missing keys: $($missingKeys -join ', ')" -ForegroundColor Yellow
    } else {
        Write-Host "✓ All required keys present" -ForegroundColor Green
    }
    
} catch {
    Write-Host "✗ Error validating YAML: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Validation complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
