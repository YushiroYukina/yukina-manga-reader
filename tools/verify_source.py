"""Verify the curated snapshot. Does not install dependencies or contact devices."""
from pathlib import Path
import ast, hashlib, json, re, sys, xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
errors=[]
for name,expected in manifest.items():
 p=root/name
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:errors.append('Missing or changed: '+name)
allowed={'android/tests/assets/测试漫画.pdf','android/tests/assets/测试漫画.epub','android/tests/assets/测试漫画.mobi','android/tests/assets/scan.zip','android/tests/assets/scan.rar','android/tests/assets/scan.7z','android/tests/assets/unicode.zip'}
for p in root.rglob('*'):
 if not p.is_file() or '.git' in p.relative_to(root).parts:continue
 name=p.relative_to(root).as_posix()
 if any(x in p.relative_to(root).parts for x in ('.tools','.venv','data','cache','build','dist')):errors.append('Generated/private path: '+name)
 if p.suffix.lower() in ('.key','.keystore','.jks','.pfx','.p12','.exe','.apk'):errors.append('Private key or binary: '+name)
 if p.suffix.lower() in ('.pdf','.epub','.mobi','.zip','.cbz','.rar','.cbr','.7z','.cb7') and name not in allowed and not (name.startswith('online/android/') and name[len('online/android/'):] in allowed):errors.append('Unexpected book: '+name)
 if name not in manifest and name not in ('SOURCE_MANIFEST.json','SOURCE_AUDIT.json'):errors.append('Unlisted file: '+name)
 if p.suffix in ('.py','.spec','.template'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=name)
 if p.suffix in ('.xml','.svg'):ET.parse(p)
 if p.suffix in ('.py','.java','.md','.xml','.json','.template','.spec'):
  text=p.read_text(encoding='utf-8-sig')
  if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}',text):errors.append('Possible credential: '+name)
if errors:print('\n'.join(errors));sys.exit(1)
print('SOURCE VERIFIED:',len(manifest),'files; hashes, Python/XML syntax and scoped credential/path checks passed.')
