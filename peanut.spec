# -*- mode: python ; coding: utf-8 -*-
"""
Peanut PyInstaller spec
=======================
Builds a standalone application for macOS, Windows, and Linux using
pywebview for native windowing (real drag-and-drop with filesystem paths).

Usage:
  pyinstaller peanut.spec --clean --noconfirm

Outputs:
  dist/Peanut.app          (macOS — proper .app bundle)
  dist/Peanut/Peanut.exe   (Windows — folder distribution)
  dist/Peanut/Peanut       (Linux — folder distribution)
"""

import sys
from pathlib import Path

APP_NAME = "Peanut"
APP_VERSION = "1.0.0"

# ── Bundled data ──────────────────────────────────────────────────────────
# Templates and static assets are read at runtime, so they need to ride
# along inside the bundle.
datas = [
    ("templates", "templates"),
    ("static", "static"),
]

# ── Hidden imports ────────────────────────────────────────────────────────
# PyInstaller can't always trace dynamic imports. List anything we touch
# via getattr / lazy imports / plugin systems.
hiddenimports = [
    # Core stdlib
    "sqlite3",
    "json",
    "hashlib",
    "subprocess",
    "queue",
    "threading",
    "argparse",
    # Pillow + plugins (we use these directly + via image_phash)
    "PIL",
    "PIL.Image",
    "PIL.ImageFilter",
    "PIL.ExifTags",
    # pillow-heif registers an opener at import time (HEIC support)
    "pillow_heif",
    # Numerics
    "imagehash",
    "numpy",
    # Web
    "flask",
    "werkzeug",
    "jinja2",
    # File ops
    "send2trash",
    # Document parsers
    "docx",
    "pptx",
    "openpyxl",
    "PyPDF2",
    # pywebview — native window
    "webview",
    "webview.platforms.cocoa",   # macOS
    "webview.platforms.winforms", # Windows
    "webview.platforms.gtk",      # Linux
    "webview.platforms.qt",       # Linux fallback
]

# ── Excludes ──────────────────────────────────────────────────────────────
# PyInstaller pulls in a LOT by default. Trim heavyweight packages we
# don't actually use to keep the bundle size sane.
excludes = [
    "matplotlib",
    "scipy",
    "pandas",
    "tkinter",
    "test", "tests",
    "pytest", "unittest",
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "IPython", "jupyter", "notebook",
    "sphinx", "docutils",
]

block_cipher = None

a = Analysis(
    ["peanut_desktop.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


# ── macOS .app bundle ─────────────────────────────────────────────────────
if sys.platform == "darwin":
    icon_path = "static/icon.icns" if Path("static/icon.icns").exists() else None
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=True,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_path,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False, upx=False, upx_exclude=[],
        name=APP_NAME,
    )
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon_path,
        bundle_identifier="com.cbrwe.peanut",
        version=APP_VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleVersion": APP_VERSION,
            "CFBundleShortVersionString": APP_VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            # Allow the app to access local network (the Flask server)
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
            "NSHumanReadableCopyright": "Copyright (c) 2026 Cody Browne",
            "LSUIElement": False,
        },
    )

# ── Windows folder distribution ───────────────────────────────────────────
elif sys.platform == "win32":
    icon_path = "static/icon.ico" if Path("static/icon.ico").exists() else None
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False, upx=False,
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_path,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False, upx=False, upx_exclude=[],
        name=APP_NAME,
    )

# ── Linux folder distribution ─────────────────────────────────────────────
else:
    icon_path = "static/icon.png" if Path("static/icon.png").exists() else None
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False, upx=False,
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_path,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False, upx=False, upx_exclude=[],
        name=APP_NAME,
    )
