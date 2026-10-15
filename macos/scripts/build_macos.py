"""Build, audit, sign-verify and archive the native arm64 macOS application."""
import sys,platform,subprocess,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if sys.platform!='darwin' or platform.machine()!='arm64':
    raise SystemExit('Use native arm64 Python on an Apple Silicon Mac.')
version=(root/'VERSION').read_text().strip()
def run(*args):return subprocess.run(args,cwd=root,check=True)
run(sys.executable,'-m','PyInstaller','--noconfirm','Migi.macOS.spec')
app=root/'dist/Migi.app'
magic={bytes.fromhex(s) for s in ('cffaedfe','feedfacf','cafebabe','bebafeca')}
count=0
for path in app.rglob('*'):
    if path.is_symlink() or not path.is_file():continue
    with path.open('rb') as stream:head=stream.read(4)
    if head not in magic:continue
    arch=subprocess.check_output(['lipo','-archs',str(path)],text=True)
    if 'arm64' not in arch:raise SystemExit('Missing arm64: '+str(path))
    count+=1
run('codesign','--verify','--deep','--strict',str(app))
release=root/'release';release.mkdir(exist_ok=True)
archive=release/f'Migi-Mac-arm64-v{version}.zip'
run('ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(archive))
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
(archive.with_suffix('.zip.sha256')).write_text(digest+'  '+archive.name+'\n')
print(f'Verified {count} arm64 Mach-O files. Created {archive.name}')
