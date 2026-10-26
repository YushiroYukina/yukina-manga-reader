"""Fetch the checksum-pinned, upstream JNI decoder for Android builds."""
from pathlib import Path
import hashlib, io, urllib.request, zipfile
root=Path(__file__).resolve().parents[1]
url='https://repo.maven.apache.org/maven2/me/zhanghai/android/libarchive/library/1.1.6/library-1.1.6.aar'
data=urllib.request.urlopen(url,timeout=90).read()
if hashlib.sha256(data).hexdigest()!='06d97a37872a9574ceb2bf94a3ad8dc38fcc89a60f2424067b20eb5efaa62189':
    raise SystemExit('libarchive AAR checksum mismatch')
target=root/'.tools/libarchive';target.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    for name in archive.namelist():
        if name=='classes.jar' or name.startswith('jni/') and name.endswith('.so'):
            output=target/name;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(archive.read(name))
print('Pinned Android libarchive decoder ready')
