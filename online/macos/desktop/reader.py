"""源文件只读；页面按需解码到内存，永不提取到磁盘。"""
import json
import os
import re
import time
import uuid
import struct
from html.parser import HTMLParser
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote
import pymupdf

from image_books import IMAGES, ARCHIVES, ImageBook, image_files
FORMATS = {'.pdf', '.epub', '.mobi'} | IMAGES | ARCHIVES
READING_STATUSES=('未标记','想读','在读','已读','搁置','弃读')

def reading_status(entry):
    return entry.get('reading_status') or '未标记'

def natural_key(value):
    return tuple((1,int(part)) if part.isdigit() else (0,part.casefold()) for part in re.split(r'(\d+)',str(value)))

def volumes(entry):
    return entry.get('volumes',[]) if entry.get('kind')=='folder' else [entry]

def path_key(path):
    return str(Path(path).resolve()).casefold()

class Book:
    def __new__(cls,path):
        if str(path).startswith("online://"):
            from online_core import OnlineBook
            return OnlineBook(path)
        return super().__new__(cls)
    def __init__(self, path):
        self.path = Path(path).resolve(strict=True)
        if not self.path.is_dir() and self.path.suffix.lower() not in FORMATS:
            raise ValueError('请选择图书、图片或扫图压缩包')
        self.doc = self.archive = self.image_book = None
        self.mobi_file = None
        self.images = []
        self.title = self.path.name if self.path.is_dir() else self.path.stem
        try:
            if self.path.is_dir() or self.path.suffix.lower() in IMAGES | ARCHIVES:
                self.image_book = ImageBook(self.path)
                self.images = list(range(len(self.image_book.pages)))
            elif self.path.suffix.lower() == '.epub':
                self._epub()
            elif self.path.suffix.lower() == '.mobi':
                self._mobi()
            if not self.images:
                if self.archive:
                    self.archive.close()
                    self.archive = None
                self.doc = pymupdf.open(str(self.path))
                if self.doc.needs_pass:
                    raise ValueError('该图书已加密，请使用无密码／无 DRM 的文件。')
                if self.doc.is_reflowable:
                    self.doc.layout(width=900, height=1280, fontsize=18)
                self.title = self.doc.metadata.get('title') or self.title
            if len(self) == 0:
                raise ValueError('图书没有可阅读的页面')
        except Exception:
            self.close()
            raise

    def _epub(self):
        self.archive = zipfile.ZipFile(self.path, 'r')
        container = ET.fromstring(self.archive.read('META-INF/container.xml'))
        opf = next(e for e in container.iter() if e.tag.endswith('rootfile')).attrib['full-path']
        root = ET.fromstring(self.archive.read(opf))
        title = next((e.text for e in root.iter() if e.tag.endswith('}title')), None)
        self.title = title or self.title
        base = posixpath.dirname(opf)
        manifest = {e.attrib['id']: e.attrib for e in root.iter() if e.tag.endswith('}item')}
        # 按 spine 阅读顺序查找实际引用图片，而非按 ZIP 文件名排序。
        pages = []
        for ref in (e for e in root.iter() if e.tag.endswith('}itemref')):
            if ref.attrib.get('linear') == 'no':
                continue
            item = manifest.get(ref.attrib.get('idref'), {})
            name = posixpath.normpath(posixpath.join(base, unquote(item.get('href', '').split('#')[0])))
            if item.get('media-type', '').startswith('image/'):
                pages.append(name)
                continue
            if 'html' not in item.get('media-type', ''):
                continue
            content = ET.fromstring(self.archive.read(name))
            # 含有正文的 EPUB 用文档引擎完整渲染，避免漏掉文字。
            body = next((e for e in content.iter() if e.tag.endswith('}body') or e.tag == 'body'), content)
            if ''.join(body.itertext()).strip():
                return
            for e in body.iter():
                local = e.tag.rsplit('}', 1)[-1]
                href = e.attrib.get('src') if local == 'img' else (e.attrib.get('{http://www.w3.org/1999/xlink}href') or e.attrib.get('href')) if local == 'image' else None
                if href and '://' not in href and not href.startswith('data:'):
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(href.split('#')[0])))
                    if target in self.archive.namelist():
                        pages.append(target)
        self.images = pages

    def __len__(self):
        return len(self.images) if self.images else self.doc.page_count if self.doc else 0

    def _mobi(self):
        self.mobi_file = self.path.open('rb')
        f = self.mobi_file
        header = f.read(78)
        if len(header) < 78 or header[60:68] != b'BOOKMOBI':
            f.close(); self.mobi_file = None; return
        count = struct.unpack_from('>H', header, 76)[0]
        table = f.read(count * 8)
        offsets = [struct.unpack_from('>I', table, i*8)[0] for i in range(count)] + [self.path.stat().st_size]
        def record(i):
            f.seek(offsets[i]); return f.read(offsets[i+1]-offsets[i])
        meta = record(0)
        if len(meta)<132 or meta[16:20]!=b'MOBI':
            f.close(); self.mobi_file=None; return
        compression, text_count, encryption = struct.unpack_from('>H',meta,0)[0], struct.unpack_from('>H',meta,8)[0], struct.unpack_from('>H',meta,12)[0]
        if encryption:
            raise ValueError('该 MOBI 有 DRM／加密，无法读取。')
        version = struct.unpack_from('>I',meta,36)[0]
        if compression not in (1,2) or version>=8:
            f.close(); self.mobi_file=None; return
        first_image = struct.unpack_from('>I',meta,108)[0]
        def decompress(data):
            if compression==1: return data
            out=bytearray(); i=0
            while i<len(data):
                c=data[i]; i+=1
                if 1<=c<=8: out.extend(data[i:i+c]); i+=c
                elif c<128: out.append(c)
                elif c>=192: out.extend((32,c^128))
                else:
                    if i>=len(data): raise ValueError('MOBI 压缩数据不完整')
                    pair=(c<<8)|data[i]; i+=1; distance=(pair & 0x3fff)>>3; length=(pair & 7)+3
                    if not distance or distance>len(out): raise ValueError('MOBI 压缩引用无效')
                    for _ in range(length): out.append(out[-distance])
            return bytes(out)
        flags=struct.unpack_from('>H',meta,242)[0] if len(meta)>=244 and struct.unpack_from('>I',meta,20)[0]>=228 else 0
        def strip_trailer(data):
            for bit in range(15,0,-1):
                if flags & (1<<bit):
                    value=0; shift=0
                    for byte in reversed(data[-4:]):
                        value |= (byte & 127)<<shift; shift+=7
                        if byte & 128: break
                    if value<=0 or value>len(data): raise ValueError('MOBI 尾部数据无效')
                    data=data[:-value]
            if flags & 1 and data: data=data[:-(data[-1]&3)-1]
            return data
        raw=b''.join(decompress(strip_trailer(record(i))) for i in range(1,min(text_count+1,count)))
        class Images(HTMLParser):
            def __init__(self): super().__init__(); self.refs=[]; self.text=[]; self.hidden=0
            def handle_starttag(self, tag, attrs):
                if tag in ('head','script','style'): self.hidden+=1
                if tag=='img':
                    value=dict(attrs).get('recindex')
                    if value and value.isdigit(): self.refs.append(int(value))
            def handle_endtag(self,tag):
                if tag in ('head','script','style'): self.hidden=max(0,self.hidden-1)
            def handle_data(self,data):
                if not self.hidden: self.text.append(data.strip())
        parser=Images(); parser.feed(raw.decode('utf-8',errors='replace'))
        if parser.refs and not ''.join(parser.text):
            pages=[]
            for ref in parser.refs:
                idx=first_image+ref-1
                if not 0<=idx<count: raise ValueError('MOBI 图片记录超出范围')
                pages.append((offsets[idx],offsets[idx+1]-offsets[idx]))
            self.images=pages
        else:
            f.close(); self.mobi_file=None

    def render(self, index, scale=1.0):
        from PySide6.QtGui import QImage
        if self.images:
            if self.image_book:
                data = self.image_book.read(index)
            elif self.mobi_file:
                offset, length = self.images[index]
                self.mobi_file.seek(offset)
                data = self.mobi_file.read(length)
            else: data = self.archive.read(self.images[index])
            image = QImage.fromData(data)
            if image.isNull():
                raise ValueError('无法解码本页图片：' + str(self.images[index]))
            return image
        page = self.doc.load_page(index)
        scale = min(scale, 4500 / max(page.rect.width, page.rect.height))
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        return QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()

    def close(self):
        if self.image_book:
            self.image_book.close()
        if self.doc:
            self.doc.close()
        if self.archive:
            self.archive.close()
        if self.mobi_file:
            self.mobi_file.close()

def spread(index, count, double=True, cover=True):
    if not double or (cover and index == 0):
        return [index]
    return list(range(index, min(index + 2, count)))

class Library:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {'books': [], 'settings': {}}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if isinstance(data.get('books'), list) and isinstance(data.get('settings'), dict):
                    self.data = data
            except (ValueError, OSError, AttributeError):
                raise ValueError('书库记录损坏，请先备份 library.json 再修复，原图书不受影响。')
        for entry in self.data['books']:
            entry.setdefault('id',uuid.uuid4().hex)
            entry.setdefault('kind','file')
        self.data.setdefault('stats',{}).setdefault('total_reading_seconds',sum(e.get('reading_seconds',0) for e in self.data['books']))
        self.data['version']=3

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.path)

    def add(self, paths,save=True):
        known = {path_key(b['path']) for b in self.data['books'] if b.get('kind')!='folder'}
        added=[]
        for path in paths:
            p = Path(path).resolve()
            if (p.is_dir() or p.is_file() and p.suffix.lower() in FORMATS) and str(p).casefold() not in known:
                entry={'id':uuid.uuid4().hex,'kind':'images' if p.is_dir() else 'file','path':str(p),'title':p.name if p.is_dir() else p.stem,'page':0,'added':time.time()}
                self.data['books'].append(entry); added.append(entry)
                known.add(str(p).casefold())
        if save: self.save()
        return added

    def find(self, entry_id):
        return next((b for b in self.data['books'] if b['id']==entry_id),None)

    @staticmethod
    def scan_folder(folder, recursive=True):
        root=Path(folder).resolve(strict=True)
        if not root.is_dir(): raise ValueError('请选择文件夹')
        result=[]
        def failed(error): raise error
        for base, dirs, files in os.walk(root,followlinks=False,onerror=failed):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__MACOSX']
            if any(Path(n).suffix.lower() in IMAGES and not n.startswith('.') for n in files): result.append(Path(base))
            for name in files:
                p=Path(base)/name
                if p.suffix.lower() in FORMATS - IMAGES: result.append(p)
            if not recursive: dirs.clear()
        return sorted(result,key=lambda p:natural_key(p.relative_to(root)))

    def import_folder(self, folder, grouped=True, recursive=True, title=None,save=True):
        root=Path(folder).resolve(strict=True)
        paths=self.scan_folder(root,recursive)
        if not paths: raise ValueError('该文件夹内没有支持的图书、压缩包或图片。')
        if paths == [root]: return self.add([root],save=save)
        if not grouped: return self.add(paths,save=save)
        existing=next((b for b in self.data['books'] if b.get('kind')=='folder' and path_key(b['path'])==str(root).casefold()),None)
        if existing:
            old_recursive=existing.get('recursive',True); existing['recursive']=recursive
            try: self.rescan(existing,save=save)
            except Exception:
                existing['recursive']=old_recursive; raise
            return [existing]
        # Reuse existing single-volume progress without silently removing its card.
        known={path_key(v['path']):v for b in self.data['books'] for v in volumes(b)}
        children=[]
        for p in paths:
            previous=known.get(str(p).casefold(),{})
            child={'path':str(p),'title':previous.get('title',p.stem),'page':previous.get('page',0)}
            for key in ('total','last_read','reading_status'):
                if key in previous: child[key]=previous[key]
            children.append(child)
        current=max(children,key=lambda v:v.get('last_read',0))
        entry={'id':uuid.uuid4().hex,'kind':'folder','path':str(root),'title':(title or root.name).strip() or root.name,
               'volumes':children,'current_volume':current['path'],'recursive':recursive,'added':time.time()}
        self.data['books'].append(entry)
        if save: self.save()
        return [entry]

    def rescan(self, entry, new_folder=None,save=True):
        if entry.get('kind')!='folder': return 0
        original=Path(entry['path'])
        root=Path(new_folder or original).resolve(strict=True)
        paths=self.scan_folder(root,entry.get('recursive',True))
        if new_folder:
            for volume in entry['volumes']:
                try: relative=Path(volume['path']).relative_to(original)
                except ValueError: continue
                relocated=str(root/relative)
                if entry.get('current_volume')==volume['path']: entry['current_volume']=relocated
                if entry.get('cover_volume')==volume['path']: entry['cover_volume']=relocated
                volume['path']=relocated
            entry['path']=str(root)
        known={path_key(v['path']) for v in entry['volumes']}
        new=[{'path':str(p),'title':p.stem,'page':0} for p in paths if str(p).casefold() not in known]
        entry['volumes'].extend(new)
        if not entry.get('manual_order'): entry['volumes'].sort(key=lambda v:natural_key(Path(v['path']).relative_to(root)))
        if save: self.save()
        return len(new)

    def import_batch(self,sources,grouped=True,recursive=True):
        report={'added':0,'updated':0,'skipped':0,'errors':[]}
        seen=set(); files=[]
        for source in sources:
            try:
                p=Path(source).resolve(strict=True); key=str(p).casefold()
                if key in seen: report['skipped']+=1; continue
                seen.add(key)
                if p.is_dir():
                    count=len(self.data['books'])
                    result=self.import_folder(p,grouped,recursive,save=False)
                    added=len(self.data['books'])-count; report['added']+=added
                    if not added:
                        if grouped and result: report['updated']+=len(result)
                        else: report['skipped']+=1
                elif p.is_file() and p.suffix.lower() in FORMATS:
                    files.append(p)
                else: raise ValueError('请选择支持的图书、扫图压缩包、图片或文件夹')
            except (OSError,ValueError) as error: report['errors'].append(str(source)+'：'+str(error))
        added_files=self.add(files,save=False)
        report['added']+=len(added_files); report['skipped']+=len(files)-len(added_files)
        self.save()
        return report

    def set_cover(self, entry, path=None):
        if path:
            from PySide6.QtGui import QImageReader
            p=Path(path).resolve(strict=True)
            reader=QImageReader(str(p))
            if not reader.canRead(): raise ValueError('无法读取该图片，请选择 JPG、PNG、WebP 或其他受支持图片。')
            entry['cover_path']=str(p)
            entry.pop('cover_volume',None)
        else:
            entry.pop('cover_path',None); entry.pop('cover_volume',None)
        self.save()

    def set_cover_volume(self,entry,path):
        if entry.get('kind')!='folder' or not any(path_key(v['path'])==path_key(path) for v in volumes(entry)):
            raise ValueError('请选择该合辑中的一个分卷作为封面')
        entry['cover_volume']=next(v['path'] for v in volumes(entry) if path_key(v['path'])==path_key(path))
        entry.pop('cover_path',None); self.save()

    def set_reading_status(self,entry,status,save=True):
        if not isinstance(status,str): raise ValueError('阅读状态应为文字')
        status=status.strip() or '未标记'
        if len(status)>30 or any(ch in status for ch in ('\n','\r','\x00')):
            raise ValueError('阅读状态请使用不超过 30 个字的单行文字')
        if status=='未标记': entry.pop('reading_status',None)
        else: entry['reading_status']=status
        if save: self.save()
