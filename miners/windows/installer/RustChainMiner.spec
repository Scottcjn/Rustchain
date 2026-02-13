# -*- mode: python ; coding: utf-8 -*-
import os

# Get the current directory to make paths relative
current_dir = os.getcwd()

a = Analysis(
    ['src/rustchain_windows_miner.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/config_manager.py', '.'),
        ('src/tray_icon.py', '.'),
        ('src/fingerprint_checks_win.py', '.'),
        ('assets/rustchain.ico', 'assets')
    ],
    hiddenimports=[
        'requests', 
        'urllib3', 
        'pystray', 
        'PIL', 
        'PIL.Image', 
        'PIL.ImageDraw', 
        'PIL.ImageFont', 
        'pystray._win32', 
        'config_manager', 
        'tray_icon',
        'fingerprint_checks_win'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'matplotlib', 'pandas', 'scipy', 'cryptography', 'tcl', 'tk'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RustChainMiner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/rustchain.ico'],
)
