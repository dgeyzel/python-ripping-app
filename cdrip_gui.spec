# PyInstaller spec for cdrip-gui. Run from project root: pyinstaller cdrip_gui.spec

import os
import sys

block_cipher = None

# Optional: bundle flac/lame from bin/ (place Windows or Linux binaries in bin/ before building)
bin_dir = os.path.join(SPECPATH, "bin")
datas = [(bin_dir, "bin")] if os.path.isdir(bin_dir) else []

a = Analysis(
    ["scripts/cdrip_gui_entry.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "discid",
        "typer",
        "musicbrainzngs",
        "mutagen",
        "mutagen.flac",
        "mutagen.id3",
        "customtkinter",
    ],
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

# Windows: no console window for GUI
console_enabled = not (sys.platform == "win32")

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="cdrip-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console_enabled,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
