# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Muhammet\\.gemini\\antigravity\\scratch\\rustchain-installer\\src\\rustchain_windows_miner.py'],
    pathex=['C:\\Users\\Muhammet\\.gemini\\antigravity\\scratch\\rustchain-installer\\src'],
    binaries=[],
    datas=[('C:\\Users\\Muhammet\\.gemini\\antigravity\\scratch\\rustchain-installer\\src\\config_manager.py', '.'), ('C:\\Users\\Muhammet\\.gemini\\antigravity\\scratch\\rustchain-installer\\src\\tray_icon.py', '.'), ('C:\\Users\\Muhammet\\.gemini\\antigravity\\scratch\\rustchain-installer\\assets\\rustchain.ico', 'assets')],
    hiddenimports=['requests', 'urllib3', 'pystray', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'pystray._win32', 'config_manager', 'tray_icon'],
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
    icon=['C:\\Users\\Muhammet\\.gemini\\antigravity\\scratch\\rustchain-installer\\assets\\rustchain.ico'],
)
