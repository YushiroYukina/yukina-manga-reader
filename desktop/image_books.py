"""Read-only scan books. Archive members are streamed to memory, never extracted."""
import os
import re
import shutil
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

IMAGES = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
ARCHIVES = {'.zip', '.cbz', '.rar', '.cbr', '.7z', '.cb7'}
LIMIT = 32 * 1024 * 1024

def natural(value):
    return tuple((1, int(x)) if x.isdigit() else (0, x.casefold()) for x in re.split(r'(\d+)', str(value)))

def archive_page_key(name):
    # Compare logical member paths, but retain original names/ZipInfo for reads.
    # Slash spelling and harmless ./ components must not override page numbers.
    parts = str(name).replace('\\', '/').split('/')
    return natural('/'.join(part for part in parts if part not in ('', '.')))

def page_name(name):
    parts = str(name).replace('\\', '/').split('/')
    return bool(parts[-1]) and not any((p.startswith('.') and p != '.') or p == '__MACOSX' for p in parts) and Path(parts[-1]).suffix.lower() in IMAGES

def image_files(folder, recursive=True):
    result = []
    def failed(error): raise error
    for base, dirs, files in os.walk(folder, followlinks=False, onerror=failed):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__MACOSX']
        result.extend(Path(base)/name for name in files if page_name(name) and not (Path(base)/name).is_symlink())
        if not recursive: break
    if len(result) > 20000: raise ValueError('单本书超过 20000 页，请分卷导入。')
    return sorted(result, key=lambda p: natural(p.relative_to(folder)))

def decoder():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    name = '7z.exe' if sys.platform == 'win32' else '7zz'
    for path in (root/'tools'/'sevenzip'/name, root/'.tools'/'sevenzip'/name, root.parent/'.tools'/'sevenzip'/name):
        if path.is_file(): return str(path)
    found = shutil.which(name)
    if found: return found
    raise ValueError('压缩包解码组件缺失，请运行 tools/prepare_archives.py 或重新下载完整程序。')

def command(args, limit):
    # A reader thread drains stdout with a hard limit; stderr goes to the null
    # device so a malformed archive cannot deadlock the process with diagnostics.
    proc = subprocess.Popen([decoder(), *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    chunks = []; error = []
    def read():
        try:
            size = 0
            while True:
                block = proc.stdout.read(65536)
                if not block: break
                size += len(block)
                if size > limit: raise ValueError('页面或压缩包目录过大，已停止读取。')
                chunks.append(block)
        except Exception as e:
            error.append(e); proc.kill()
    thread = threading.Thread(target=read, daemon=True); thread.start()
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait(); raise ValueError('压缩包读取超时，请检查文件是否损坏。')
    finally:
        thread.join(); proc.stdout.close()
    if error: raise error[0]
    if proc.returncode: raise ValueError('压缩包无法读取：文件损坏、加密或不受支持；请使用无密码的完整压缩包。')
    return b''.join(chunks)

class ImageBook:
    def __init__(self, path):
        self.path = Path(path); self.zip = None
        try:
            if self.path.is_dir(): self.pages = image_files(self.path, recursive=False)
            elif self.path.suffix.lower() in IMAGES: self.pages = [self.path]
            elif self.path.suffix.lower() in {'.zip', '.cbz'}:
                self.zip = zipfile.ZipFile(self.path, 'r')
                self.pages = sorted((e for e in self.zip.infolist() if not e.is_dir() and page_name(e.filename)), key=lambda e: archive_page_key(e.filename))
                if any(e.flag_bits & 1 for e in self.pages): raise ValueError('暂不支持加密压缩包。')
            else:
                listing = command(['l', '-slt', '-ba', '-sccUTF-8', '-p', '--', str(self.path)], 16*1024*1024).decode('utf-8-sig')
                self.pages = []
                for block in re.split(r'\r?\n\r?\n', listing):
                    item = dict(line.split(' = ', 1) for line in block.splitlines() if ' = ' in line)
                    name = item.get('Path', '')
                    if not page_name(name) or item.get('Folder') == '+': continue
                    if item.get('Encrypted') == '+': raise ValueError('暂不支持加密压缩包。')
                    if int(item.get('Size', '0')) > LIMIT: raise ValueError('压缩包中的单页超过 32 MiB。')
                    self.pages.append(name)
                self.pages.sort(key=archive_page_key)
                if len(set(self.pages)) != len(self.pages): raise ValueError('压缩包包含重名图片，请整理后导入。')
            if len(self.pages) > 20000: raise ValueError('单本书超过 20000 页，请分卷导入。')
            if not self.pages: raise ValueError('未找到可阅读的 JPG、PNG、WebP、BMP 或 GIF 图片。')
        except Exception:
            self.close(); raise

    def read(self, index):
        page = self.pages[index]
        if isinstance(page, Path):
            with page.open('rb') as stream: data = stream.read(LIMIT+1)
        elif self.zip:
            if page.file_size > LIMIT: raise ValueError('单页超过 32 MiB。')
            with self.zip.open(page) as stream: data = stream.read(LIMIT+1)
        else:
            data = command(['x', '-so', '-y', '-spd', '-p', '--', str(self.path), page], LIMIT)
        if len(data) > LIMIT: raise ValueError('单页超过 32 MiB。')
        return data

    def close(self):
        if self.zip: self.zip.close()
