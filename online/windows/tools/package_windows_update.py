"""Package a verified Windows update only; leaves Android and Mac untouched."""
import hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def git(*args):return subprocess.check_output(['git',*args],cwd=root)
if git('status','--porcelain').strip():raise SystemExit('Commit source before packaging.')
version=(root/'VERSION').read_text('utf-8').strip();out=root/'release';out.mkdir(exist_ok=True);commit=git('rev-parse','HEAD').decode().strip();dist=root/'dist/YukinaOnline'
for folder in (dist/'docs',dist/'_internal/docs'):shutil.copytree(root/'docs',folder,dirs_exist_ok=True)
shutil.copy2(root/'README.md',dist/'使用说明.md');shutil.copy2(root/'NOTICE.md',dist/'NOTICE.md')
portable=out/f'yukina-online-windows-x64-v{version}.zip'
with zipfile.ZipFile(portable,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
    for p in sorted(dist.rglob('*')):
        if p.is_file():
            if any(x in ('online-data','data','cache','work') for x in p.relative_to(dist).parts):raise SystemExit('Unexpected runtime data')
            z.write(p,'YukinaOnline/'+p.relative_to(dist).as_posix())
names=git('ls-files','-z').decode('utf-8').strip('\0').split('\0');keep=[]
root_files={'README.md','LICENSE','NOTICE.md','VERSION','YukinaOnline.spec','.gitignore','.gitattributes','SOURCE_AUDIT.json'}
win_tools={'tools/build_windows.py','tools/package_windows_update.py','tools/verify_source.py','tools/probe_common_sources.py'}
for n in names:
    if n in root_files or n in win_tools or n.startswith(('desktop/','sources/','docs/','licenses/','tests/')):keep.append(n)
manifest={n:hashlib.sha256(git('show',f'HEAD:{n}')).hexdigest() for n in keep if n!='SOURCE_AUDIT.json'}
source=out/f'yukina-online-windows-source-v{version}.zip'
with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
    for n in keep:z.writestr('yukina-online-windows/'+n,git('show',f'HEAD:{n}'))
    z.writestr('yukina-online-windows/SOURCE_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
record={'version':version,'commit':commit,'scope':'Windows only','androidModified':False,'macModified':False,'artifacts':{}}
for p in (portable,source):
    with zipfile.ZipFile(p) as z:
        if z.testzip():raise SystemExit('Invalid ZIP: '+str(p))
    digest=hashlib.sha256(p.read_bytes()).hexdigest();p.with_suffix('.zip.sha256').write_text(digest+'  '+p.name+'\n');record['artifacts'][p.name]={'sha256':digest,'bytes':p.stat().st_size}
(out/'WINDOWS_BUILD_RECORD.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
