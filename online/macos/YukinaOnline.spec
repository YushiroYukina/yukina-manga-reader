"""Independent Windows x64 / Apple Silicon bundle. Does not target the local reader."""
import sys
from pathlib import Path
import PySide6
from PySide6.QtCore import QLibraryInfo
root=Path(SPECPATH)
desktop=root/'desktop'
mac=sys.platform=='darwin'
decoder=desktop/'.tools/sevenzip'
if not (decoder/('7zz' if mac else '7z.exe')).is_file():decoder=desktop/'tools/sevenzip'
if not (decoder/('7zz' if mac else '7z.exe')).is_file():raise SystemExit('Run desktop/tools/prepare_archives.py before packaging.')
binaries=[(str(decoder/('7zz' if mac else '7z.exe')),'tools/sevenzip')]
if not mac:binaries.append((str(decoder/'7z.dll'),'tools/sevenzip'))
datas=[(str(desktop/'assets'),'assets'),(str(root/'LICENSE'),'.'),(str(root/'NOTICE.md'),'.'),(str(root/'licenses'),'licenses'),(str(decoder/'License.txt'),'tools/sevenzip'),(str(root/'sources'),'sources'),(str(Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))/'qtbase_zh_CN.qm'),'translations')]
datas.append((str(root/'docs'),'docs'))
datas.append((str(desktop/'builtin_sources.json'),'.'))
a=Analysis([str(desktop/'app.py')],pathex=[str(desktop)],binaries=binaries,datas=datas,hiddenimports=['online_ui','online_core','online_validation','source_dm5'],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False,optimize=0)
# Windows Qt uses the OS's unversioned ICU API. A different ICU from PATH has
# suffixed exports and makes QtNetwork fail with ERROR_PROC_NOT_FOUND.
if not mac:a.binaries=[row for row in a.binaries if Path(row[0]).name.lower() not in ('icuuc.dll','icuin.dll','icudt.dll')]
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='YukinaOnline',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,argv_emulation=False,target_arch='arm64' if mac else None,codesign_identity=None,entitlements_file=None)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='YukinaOnline')
if mac:
    app=BUNDLE(coll,name='YukinaOnline.app',bundle_identifier='cn.yukina.online.mac',info_plist={'CFBundleDisplayName':'yukina漫画阅读器·在线版','CFBundleDevelopmentRegion':'zh_CN','CFBundleLocalizations':['zh_CN','zh-Hans'],'CFBundleShortVersionString':'0.1.3','CFBundleVersion':'20261026.4','NSHighResolutionCapable':True,'LSMinimumSystemVersion':'14.0','NSAppTransportSecurity':{'NSAllowsLocalNetworking':True}})
