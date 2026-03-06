# iearnbot.spec — PyInstaller spec for iEarn.Bot macOS Desktop App
# Usage: pyinstaller iearnbot.spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect rumps / AppKit data
hiddenimports = (
    collect_submodules("rumps")
    + collect_submodules("flask")
    + collect_submodules("requests")
    + [
        "webbrowser",
        "threading",
        "subprocess",
        "pathlib",
        "dotenv",
        "skillpay",
    ]
)

datas = (
    collect_data_files("rumps")
    + [
        ("../src", "src"),
        ("../.env.example", "."),
    ]
)

a = Analysis(
    ["main.py"],
    pathex=["../src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="iEarn.Bot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="iEarn.Bot",
)

app = BUNDLE(
    coll,
    name="iEarn.Bot.app",
    icon=None,          # replace with path to .icns if available
    bundle_identifier="bot.iearn.desktop",
    info_plist={
        "NSPrincipalClass": "NSApplication",
        "NSAppleScriptEnabled": False,
        "CFBundleName": "iEarn.Bot",
        "CFBundleDisplayName": "iEarn.Bot",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1",
        "LSUIElement": True,      # menu-bar-only app (no dock icon)
        "NSHighResolutionCapable": True,
    },
)
