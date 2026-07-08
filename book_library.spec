# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Book Library
# Build with: pyinstaller book_library.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('VERSION', '.'),
        ('books.json', '.'),
        ('app_icon.png', '.'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'sqlite3',
        'json',
        'csv',
        'threading',
        'urllib.request',
        'urllib.error',
        'webbrowser',
        'pathlib',
        'shutil',
        # Optional — included so exe works if user has them installed
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'cv2',
        'pyzbar',
        'pyzbar.pyzbar',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy',        # large, not needed unless PIL pulls it in
        'matplotlib',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
    ],
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
    name='BookLibrary',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',    # Windows taskbar + desktop icon
    version_info=None,
)
