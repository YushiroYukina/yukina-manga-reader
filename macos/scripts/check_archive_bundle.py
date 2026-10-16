"""Exercise archive covers using the packaged executable, without system 7-Zip."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'reader'),str(root/'reader/tests')]
from test_scan_books import fixtures
from PySide6.QtGui import QImage

exe=root/'dist/Migi.app/Contents/MacOS/Migi'
(root/'work').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=root/'work') as temp:
    folder=Path(temp);images=fixtures(folder)
    for original,alias in [('scan.cbz','scan.zip'),('scan.rar','scan.cbr'),('scan.7z','scan.cb7')]:
        shutil.copyfile(folder/original,folder/alias)
    sources=[folder/name for name in ['scan.zip','scan.cbz','scan.rar','scan.cbr','scan.7z','scan.cb7']]+[images,images/'page2.png']
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
    covers=folder/'covers';covers.mkdir()
    jobs=[dict(id=str(i),kind='book',source=str(p),output=str(covers/f'{i}.png')) for i,p in enumerate(sources)]
    env=os.environ.copy();env['PATH']='/usr/bin:/bin:/usr/sbin:/sbin'
    env['QT_QPA_PLATFORM']='offscreen';env['MIGI_DATA_ROOT']=str(folder/'runtime')
    result=subprocess.run([str(exe),'--thumbnail-worker',str(covers)],cwd=folder,env=env,
                          input=''.join(json.dumps(j)+'\n' for j in jobs),text=True,capture_output=True,timeout=120)
    if result.returncode:raise RuntimeError(result.stderr)
    replies=[json.loads(line) for line in result.stdout.splitlines()]
    assert len(replies)==len(jobs) and all(r.get('ok') for r in replies),replies
    for i in range(len(jobs)):
        image=QImage(str(covers/f'{i}.png'));assert not image.isNull()
        pixel=image.pixelColor(image.width()//2,image.height()//2)
        assert pixel.red()>240 and pixel.green()<10 and pixel.blue()<10,i
    for name,digest in before.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
    created={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and str(p) not in before}
    assert created=={f'covers/{i}.png' for i in range(len(jobs))},created
report={'version':'1.1','platform':sys.platform,'packagedExecutable':True,'system7ZipOnPath':False,
        'archiveAndImageCoverChecks':len(jobs),'originalHashesUnchanged':True,'extractedPageFiles':0,
        'scope':'Packaged helper covers; not manual physical-device UI verification'}
(root/'work/archive-bundle-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
