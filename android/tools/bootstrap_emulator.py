import urllib.request,xml.etree.ElementTree as ET,zipfile,hashlib
from pathlib import Path
root=Path('.tools').resolve()
def fetch(u):
    with urllib.request.urlopen(u,timeout=60) as r:return r.read()
for repository,key,target in [('https://dl.google.com/android/repository/repository2-1.xml','emulator','sdk/emulator'),('https://dl.google.com/android/repository/sys-img/android/sys-img2-1.xml','system-images;android-34;default;x86_64','sdk/system-images/android-34/default/x86_64')]:
    dest=root/target
    if dest.exists():continue
    xml=ET.fromstring(fetch(repository));package=next(e for e in xml if e.tag.endswith('remotePackage') and e.attrib.get('path')==key)
    item=next(a for a in package.find('archives').findall('archive') if a.findtext('host-os') in ('windows',None))
    complete=item.find('complete');name=complete.findtext('url');checksum=complete.find('checksum');url=urllib.request.urljoin(repository,name);p=root/Path(name).name
    if not p.exists():
        print('Downloading',p.name,'MiB',int(complete.findtext('size'))//1048576,flush=True)
        with urllib.request.urlopen(url,timeout=180) as r,p.open('wb') as f:
            while True:
                b=r.read(1048576)
                if not b:break
                f.write(b)
    assert hashlib.new(checksum.attrib.get('type','sha1'),p.read_bytes()).hexdigest()==checksum.text
    print('Checksum verified',p.name,flush=True)
    with zipfile.ZipFile(p) as z:
        prefix=z.namelist()[0].split('/')[0]+'/'
        dest.mkdir(parents=True,exist_ok=True)
        for name in z.namelist():
            rel=name[len(prefix):]
            if not rel or name.endswith('/'):continue
            out=dest/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(name))
print('Android 14 emulator tools installed',flush=True)
