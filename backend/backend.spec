# -*- mode: python ; coding: utf-8 -*-
# AURORA Local Agent Backend - PyInstaller Configuration
# This spec file configures PyInstaller to build a standalone backend executable

import sys
import os

block_cipher = None

# Collect data files
datas = []
if os.path.isdir('system_prompts'):
    datas.append(('system_prompts', 'system_prompts'))
if os.path.isdir('data'):
    datas.append(('data', 'data'))

# Hidden imports for dependencies
hidden_imports = [
    'fastapi',
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'pydantic',
    'pydantic_core',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for API server output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
