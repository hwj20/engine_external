# AURORA Local Agent - 打包与发布指南

## 前置要求

### 开发环境
- Node.js 18+ 
- Python 3.10+
- Git

### 工具
- PyInstaller (`pip install pyinstaller`)
- electron-builder (会在构建时自动安装)

## 配置 GitHub 信息

在使用打包和发布脚本之前，需要修改以下文件中的 GitHub 用户名：

### 1. 更新 updater.js
编辑 `app/electron/updater.js`，将以下配置改为你的 GitHub 信息：

```javascript
const UPDATE_CONFIG = {
  owner: 'YOUR_GITHUB_USERNAME',  // 替换为你的 GitHub 用户名
  repo: 'aurora_local_agent_mvp', // 替换为你的仓库名
  ...
};
```

### 2. 更新 release.ps1
编辑 `scripts/release.ps1`，修改默认参数：

```powershell
[string]$RepoOwner = "YOUR_GITHUB_USERNAME",  # 替换为你的 GitHub 用户名
[string]$RepoName = "aurora_local_agent_mvp", # 替换为你的仓库名
```

## 打包步骤

### 方法 1: 使用打包脚本（推荐）

```powershell
# 进入项目根目录
cd c:\Users\wanji\projects\aurora_local_agent_mvp\aurora_local_agent_mvp

# 运行打包脚本
.\scripts\build.ps1 -Version "0.1.0"

# 可选参数:
# -SkipBackend  : 跳过 Python 后端打包
# -SkipFrontend : 跳过 Electron 前端打包
```

### 输出文件
打包完成后，会在 `dist/` 目录生成：
- `AURORA-Local-Agent-0.1.0-win-x64.zip` - 完整发布包
- `AURORA-Local-Agent-0.1.0-win-x64/` - 解压后的文件夹

## 发布到 GitHub Release

### 前置准备
1. 在 GitHub 上创建 Personal Access Token (PAT)：
   - 访问 https://github.com/settings/tokens
   - 点击 "Generate new token (classic)"
   - 勾选 `repo` 权限
   - 复制生成的 token

### 自动发布（推荐）

```powershell
# 发布正式版本
.\scripts\release.ps1 -Version "0.1.0" -GitHubToken "your_github_token"

# 发布草稿版本（不公开）
.\scripts\release.ps1 -Version "0.1.0" -GitHubToken "your_github_token" -Draft

# 发布预发布版本
.\scripts\release.ps1 -Version "0.1.0" -GitHubToken "your_github_token" -PreRelease
```

### 手动发布

1. 在 GitHub 仓库页面点击 "Releases"
2. 点击 "Create a new release"
3. 设置 Tag: `v0.1.0`
4. 填写 Release 标题和说明
5. 上传 `dist/AURORA-Local-Agent-0.1.0-win-x64.zip`
6. 发布

## 自动更新功能

### 工作原理
1. 应用启动时自动检查 GitHub Releases 的最新版本
2. 如果发现新版本，弹窗询问用户是否更新
3. 用户可以选择：
   - **Download** - 打开浏览器下载最新版本
   - **Release Notes** - 查看更新说明
   - **Later** - 稍后提醒

### 手动检查更新
在应用菜单中选择 **Help → Check for Updates...**

### 禁用启动时自动检查
在 `app/electron/updater.js` 中修改：

```javascript
const CHECK_ON_STARTUP = false;  // 设为 false 禁用
```

## 版本号规范

推荐使用语义化版本 (SemVer)：
- **MAJOR.MINOR.PATCH** (例如 1.0.0)
- MAJOR: 不兼容的 API 变更
- MINOR: 向后兼容的功能新增
- PATCH: 向后兼容的问题修复

## 故障排除

### PyInstaller 打包失败
```powershell
# 重新安装 PyInstaller
pip uninstall pyinstaller
pip install pyinstaller

# 清理并重新打包
.\scripts\build.ps1 -Version "0.1.0"
```

### Electron-builder 失败
```powershell
# 清理 node_modules
cd app
Remove-Item -Recurse -Force node_modules
npm install
npm run dist
```

### 检查更新失败
- 确保 `updater.js` 中的 GitHub 仓库信息正确
- 确保网络可以访问 `api.github.com`
- 检查 Release 是否设为公开（非 Draft）

## 文件结构

```
dist/
├── AURORA-Local-Agent-0.1.0-win-x64/
│   ├── aurora-backend.exe      # Python 后端
│   ├── AURORA Local Agent MVP.exe  # Electron 前端
│   ├── Start-AURORA.bat        # 启动脚本
│   ├── version.json            # 版本信息
│   └── data/                   # 数据目录
└── AURORA-Local-Agent-0.1.0-win-x64.zip  # 发布包
```
