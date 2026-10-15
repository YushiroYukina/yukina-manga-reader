from pathlib import Path
repo = Path(SPECPATH).parent
# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('assets','assets'),(str(repo/'LICENSE'),'.'),(str(repo/'NOTICE.md'),'.'),(str(repo/'licenses'),'licenses')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt 6.12 uses the Windows ICU API. Do not bundle an incompatible
# Poppler/Conda ICU discovered on the build machine's PATH.
a.binaries = [item for item in a.binaries if not item[0].lower().startswith(('icuuc', 'icudt'))]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='yukina-reader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='yukina-reader',
)
