"""Fetch pinned upstream decoder for builds. Never invoked while reading a book."""
import hashlib
import io
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/ip7z/7zip/releases/download/26.04/'
WINDOWS = sys.platform == 'win32'
NAME = '7z2604-x64.exe' if WINDOWS else '7z2604-mac.tar.xz'
SHA = 'd54bf805f9f3704d1e8db2fa3498ae7ef2df0312b40b558e7c71c734430a665d' if WINDOWS else 'bee04358cbcbc7106273cee0e8d72916db2696c48067a3538c34d8cd6fd16578'
target = ROOT/'tools'/'sevenzip'
if not WINDOWS and sys.platform != 'darwin': raise SystemExit('Windows x64 / macOS only')
data = urllib.request.urlopen(URL+NAME, timeout=90).read()
if hashlib.sha256(data).hexdigest() != SHA: raise SystemExit('7-Zip checksum mismatch')
target.mkdir(parents=True, exist_ok=True)
if WINDOWS:
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp)/NAME; source.write_bytes(data)
        subprocess.run(['tar', '-xf', str(source), '-C', str(target), '7z.exe', '7z.dll', 'License.txt'], check=True)
else:
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:xz') as archive:
        for name in ('7zz', 'License.txt'):
            member = next(m for m in archive.getmembers() if Path(m.name).name == name and m.isfile())
            with archive.extractfile(member) as stream: (target/name).write_bytes(stream.read())
    (target/'7zz').chmod(0o755)
print('Pinned 7-Zip decoder ready:', target)
