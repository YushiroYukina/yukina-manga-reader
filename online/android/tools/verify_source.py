"""Verify a clean source archive without contacting devices or installing dependencies."""
from pathlib import Path
import ast,hashlib,json,os,re,sys,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];manifest=json.loads((root/'SOURCE_MANIFEST.json').read_text('utf-8'));errors=[]
for name,expected in manifest.items():
    path=(root/name).resolve()
    if not path.is_relative_to(root):errors.append('Outside source root: '+name);continue
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:errors.append('Missing or changed: '+name)
skip={'.git','.tools','.venv','__pycache__','build','dist','release','work','online-data','data','cache','qa-temp'}
for directory,dirs,files in os.walk(root,followlinks=False):
    dirs[:]=[d for d in dirs if d not in skip]
    for file in files:
        if file=='.git':continue  # Linked-worktree metadata is not distributable source.
        path=Path(directory)/file;name=path.relative_to(root).as_posix()
        if name not in manifest and name not in ('SOURCE_MANIFEST.json','SOURCE_AUDIT.json'):errors.append('Unlisted source: '+name)
        if path.suffix.lower() in ('.key','.keystore','.jks','.pfx','.p12','.apk','.exe','.dll','.jar'):errors.append('Private key or build artifact: '+name)
        if path.suffix.lower() in ('.pdf','.epub','.mobi','.zip','.rar','.7z','.cbz','.cbr','.cb7') and not name.startswith('android/tests/assets/'):errors.append('Unexpected book/archive: '+name)
        if path.suffix in ('.py','.spec','.template'):ast.parse(path.read_text('utf-8-sig'),filename=name)
        if path.suffix in ('.xml','.svg'):ET.parse(path)
        if path.suffix in ('.py','.java','.md','.xml','.json','.spec'):
            if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}',path.read_text('utf-8-sig')):errors.append('Possible credential: '+name)
if errors:raise SystemExit('\n'.join(errors))
print('SOURCE VERIFIED:',len(manifest),'files; hashes, syntax, credentials and generated-file boundaries checked.')
