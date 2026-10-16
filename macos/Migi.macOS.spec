# macOS arm64 application; build on an Apple Silicon Mac.
import sys
import PySide6
from pathlib import Path
if sys.platform != 'darwin':
    raise SystemExit('Build this spec on macOS with native arm64 Python.')
base = Path(SPECPATH)
import subprocess
_decoder=base/'reader/tools/sevenzip'
if not (_decoder/'7zz').is_file():subprocess.run([sys.executable,str(base/'reader/tools/prepare_archives.py')],check=True)
a = Analysis([str(base/'reader/app.py')], pathex=[str(base/'reader')],
    binaries=[(str(_decoder/'7zz'),'tools/sevenzip')], datas=[(str(_decoder/'License.txt'),'tools/sevenzip'),(str(base.parent/'LICENSE'),'.'),(str(base.parent/'NOTICE.md'),'.'),(str(base.parent/'licenses'),'licenses'),(str(base/'reader/assets'),'assets'),(str(Path(PySide6.__file__).parent/'Qt/translations/qtbase_zh_CN.qm'),'translations')],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Migi',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, argv_emulation=False, target_arch='arm64',
    codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Migi')
app = BUNDLE(coll, name='Migi.app', bundle_identifier='cn.migi.reader.mac',
    info_plist={'CFBundleDisplayName':'右页 · MIGI',
                'CFBundleDevelopmentRegion':'zh_CN','CFBundleLocalizations':['zh_CN','zh-Hans'],
                'CFBundleShortVersionString':'1.1','CFBundleVersion':'20261016.1',
                'NSHighResolutionCapable':True,'LSMinimumSystemVersion':'14.0'})
