#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick reference - Print command cheatsheet to console
#>

Write-Host @"

╔════════════════════════════════════════════════════════════╗
║        AURORA Local Agent - Quick Reference              ║
╚════════════════════════════════════════════════════════════╝

📦 初始化
  .\scripts\setup.ps1                 # 第一次设置

🚀 开发
  .\scripts\dev.ps1                   # 启动后端+前端
  cd app; npm run dev                 # 仅前端开发

🔨 构建
  .\scripts\build-all.ps1             # 完整构建
  .\scripts\build-all.ps1 -Portable   # 便携版本
  npm run build:win                   # Windows NSIS
  npm run build:mac                   # macOS DMG
  npm run build:linux                 # Linux AppImage

📤 发布
  .\scripts\release.ps1 -Version patch
  .\scripts\release.ps1 -Version minor
  .\scripts\release.ps1 -Version major

🔍 工具
  .\scripts\check-updates.ps1         # 检查远程更新
  .\scripts\validate-workflow.ps1     # 验证CI/CD工作流

📋 版本流程
  1. 修改代码
  2. .\scripts\release.ps1 -Version patch -Message "说明"
  3. GitHub Actions自动构建并发布
  4. 检查 https://github.com/hwj20/engine_external/releases

📄 详细文档: 查看 BUILD_AND_RELEASE.md

╔════════════════════════════════════════════════════════════╗
║                        技术栈                              ║
╠════════════════════════════════════════════════════════════╣
║ 前端        Electron + Node.js 18+                         ║
║ 后端        FastAPI + Python 3.11+                         ║
║ 更新        electron-updater + GitHub Releases             ║
║ 构建        electron-builder + PyInstaller                 ║
║ CI/CD       GitHub Actions                                 ║
╚════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan
