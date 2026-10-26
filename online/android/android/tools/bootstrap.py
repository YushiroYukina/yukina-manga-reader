import urllib.request,json,xml.etree.ElementTree as ET,zipfile,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'.tools'; root.mkdir(parents=True,exist_ok=True)
def fetch(url):
    with urllib.request.urlopen(url,timeout=90) as r:return r.read()
def archive(url,name,checksum,algorithm='sha256'):
    p=root/name
    if not p.exists():
        print('Downloading',name,flush=True)
        with urllib.request.urlopen(url,timeout=180) as r,p.open('wb') as f:
            while True:
                b=r.read(1024*1024)
                if not b:break
                f.write(b)
    assert hashlib.new(algorithm,p.read_bytes()).hexdigest()==checksum,(name,'checksum mismatch')
    print('Verified',name,flush=True); return p
url='https://download.oracle.com/java/21/latest/jdk-21_windows-x64_bin.zip'
checksum=fetch(url+'.sha256').decode().strip()
p=archive(url,'jdk21.zip',checksum)
if not (root/'jdk').exists():
    with zipfile.ZipFile(p) as z:
        top=z.namelist()[0].split('/')[0]; z.extractall(root/'jdk')
    (root/'jdk-path.txt').write_text(str((root/'jdk'/top).resolve()),encoding='utf-8')
xml=ET.fromstring(fetch('https://dl.google.com/android/repository/repository2-1.xml'))
for key,dest in [('platforms;android-34','sdk/platforms/android-34'),('build-tools;34.0.0','sdk/build-tools/34.0.0'),('platform-tools','sdk/platform-tools')]:
    target=root/dest
    if target.exists():continue
    package=next(e for e in xml if e.tag.endswith('remotePackage') and e.attrib.get('path')==key)
    archives=package.find('archives').findall('archive')
    item=next(a for a in archives if a.findtext('host-os') in ('windows',None))
    complete=item.find('complete'); url=complete.findtext('url'); checksum=complete.find('checksum')
    p=archive('https://dl.google.com/android/repository/'+url,url.split('/')[-1],checksum.text,checksum.attrib.get('type','sha1'))
    with zipfile.ZipFile(p) as z:
        prefix=z.namelist()[0].split('/')[0]+'/'
        target.mkdir(parents=True,exist_ok=True)
        for name in z.namelist():
            rel=name[len(prefix):]
            if not rel or name.endswith('/'):continue
            out=target/rel; out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(z.read(name))
print('Portable JDK and SDK ready',flush=True)
