"""Build a portable independent Windows bundle; never installs over another reader."""
import hashlib,subprocess,sys,zipfile,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
version=(root/'VERSION').read_text('utf-8').strip()
if sys.platform!='win32':raise SystemExit('Windows x64 Python required')
if not any((root/'desktop'/p/'7z.exe').is_file() for p in ('.tools/sevenzip','tools/sevenzip')):
    subprocess.run([sys.executable,str(root/'desktop/tools/prepare_archives.py')],check=True)
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','YukinaOnline.spec'],cwd=root,check=True)
dist=root/'dist/YukinaOnline';shutil.copy2(root/'README.md',dist/'使用说明.md');shutil.copy2(root/'LICENSE',dist/'LICENSE');shutil.copy2(root/'NOTICE.md',dist/'NOTICE.md');shutil.copytree(root/'sources',dist/'sources',dirs_exist_ok=True)
shutil.copytree(root/'docs',dist/'docs',dirs_exist_ok=True)
out=root/'release';out.mkdir(exist_ok=True);archive=out/f'yukina-online-windows-x64-v{version}.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
    for p in sorted(dist.rglob('*')):
        if p.is_file():
            if any(v in p.relative_to(dist).parts for v in ('online-data','data','cache','work')):raise SystemExit('Unexpected runtime data: '+str(p))
            z.write(p,'YukinaOnline/'+p.relative_to(dist).as_posix())
archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
print('Built',archive)
