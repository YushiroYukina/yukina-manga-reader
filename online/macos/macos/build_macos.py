"""Run on an Apple Silicon Mac; creates only the independent online application."""
import hashlib,platform,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if sys.platform!='darwin' or platform.machine()!='arm64':raise SystemExit('请在 Apple Silicon Mac 上使用原生 arm64 Python 3.12 构建。')
subprocess.run([sys.executable,str(root/'desktop/tools/prepare_archives.py')],cwd=root,check=True)
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','YukinaOnline.spec'],cwd=root,check=True)
app=root/'dist/YukinaOnline.app'
magic={bytes.fromhex(x) for x in ('cffaedfe','feedfacf','cafebabe','bebafeca')};count=0
for p in app.rglob('*'):
    if p.is_symlink() or not p.is_file():continue
    with p.open('rb') as f:head=f.read(4)
    if head not in magic:continue
    arch=subprocess.check_output(['lipo','-archs',str(p)],text=True)
    if 'arm64' not in arch:raise SystemExit('Missing arm64: '+str(p))
    count+=1
subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
out=root/'release';out.mkdir(exist_ok=True);archive=out/'yukina-online-mac-arm64-v0.1.3-preview.zip'
subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(archive)],check=True)
archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
print('Verified',count,'arm64 Mach-O files. Built',archive)
