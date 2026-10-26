"""Open-source source adapters and explicit, resumable chapter downloads.

No background page disk cache. Network transport is separate from both UIs.
Adapter implementations are original AGPL code; upstream API references in docs.
"""
from __future__ import annotations
import base64
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urljoin, urlencode, urlsplit, urlunsplit, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError, URLError
import uuid
from online_memory import PageMemory,decode_page

USER_AGENT = 'YukinaOnline/0.1.3 (personal manga reader; Python)'
PAGE_LIMIT = 32 * 1024 * 1024
JSON_LIMIT = 8 * 1024 * 1024
KINDS = ('mangadex', 'manhuagui', 'mangapill', 'dm5', 'komga', 'suwayomi', 'catalog')
BACKGROUND=threading.local()

class OnlineError(Exception): pass
class Cancelled(OnlineError): pass
class SourceHttpError(OnlineError):
    def __init__(self,status):self.status=status;super().__init__(f'书源返回 HTTP {status}；请检查服务地址、认证或稍后重试')

def atomic_json(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    try: os.chmod(temp, 0o600)
    except OSError: pass
    temp.replace(path)

def checked_url(url):
    p = urlsplit(str(url))
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise OnlineError('书源地址必须是 http(s) 地址，账号请填入独立认证字段')
    # Manga image directories can contain CJK names and spaces. urllib requires
    # an ASCII request target; retain already escaped bytes and URL separators.
    host=p.hostname if ':' in p.hostname else p.hostname.encode('idna').decode('ascii')
    authority=('['+host+']' if ':' in host else host)+((':'+str(p.port)) if p.port else '')
    return urlunsplit((p.scheme,authority,quote(p.path,safe="/%:@!$&'()*+,;=-._~"),
                      quote(p.query,safe="/%?:@!$&'()*+,;=-._~"),quote(p.fragment,safe="/%?:@!$&'()*+,;=-._~")))

def origin(url):
    p = urlsplit(url)
    host=(p.hostname or '').lower()
    if ':' not in host:host=host.encode('idna').decode('ascii')
    return p.scheme.lower(), host, p.port or (443 if p.scheme == 'https' else 80)

class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl)
        if urlsplit(req.full_url).scheme == 'https' and urlsplit(newurl).scheme != 'https':
            raise OnlineError('拒绝将 HTTPS 请求重定向到不加密的地址')
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        if result and origin(req.full_url) != origin(newurl):
            for key in ('Authorization', 'X-api-key', 'Cookie'):
                result.remove_header(key)
        return result

class Http:
    gates={}
    gates_lock=threading.Lock()
    def __init__(self, source):
        self.source = source
        # Explicit per-source route; retain certificate validation and system defaults.
        self.opener = build_opener(ProxyHandler({}), SafeRedirect()) if source.get('connection') == 'direct' else build_opener(SafeRedirect())

    def read(self, url, limit=PAGE_LIMIT):
        url = checked_url(url)
        with self.gates_lock:
            gate=self.gates.setdefault(origin(url),[threading.Lock(),0.0])
        with gate[0]:
            interval = 1.6 if self.source.get('type') == 'mangadex' and '/at-home/' in url else .35
            if self.source.get('type')=='manhuagui':interval=3.0 if origin(url)==origin(self.source['base_url']) else 1.0
            delay = gate[1] + interval - time.monotonic()
            if delay > 0: time.sleep(delay)
            gate[1] = time.monotonic()
        headers = {'User-Agent': USER_AGENT, 'Accept': '*/*'}
        if self.source.get('type') in ('manhuagui','mangapill'):
            headers['Referer'] = self.source['base_url'].rstrip('/')+'/'
        if self.source.get('type')=='dm5':
            from urllib.parse import parse_qs
            import re
            cid=parse_qs(urlsplit(url).query).get('cid',[''])[0]
            match=re.match(r'/m(\d+)/',urlsplit(url).path)
            if match:cid=match[1]
            headers['Referer']=self.source['base_url'].rstrip('/')+('/m'+cid+'/' if cid.isdigit() else '/')
            headers['Accept-Language']='zh-CN,zh;q=0.9'
        if origin(url) == origin(self.source['base_url']):
            if self.source.get('api_key'): headers['X-API-Key'] = self.source['api_key']
            if self.source.get('username'):
                auth = self.source['username'] + ':' + self.source.get('password', '')
                headers['Authorization'] = 'Basic ' + base64.b64encode(auth.encode()).decode()
            elif self.source.get('token'): headers['Authorization'] = 'Bearer ' + self.source['token']
        attempts=1 if getattr(BACKGROUND,'active',False) else 3
        for attempt in range(attempts):
            try:
                with self.opener.open(Request(url, headers=headers), timeout=8 if attempts==1 else 25) as response:
                    size = response.headers.get('Content-Length')
                    if size and int(size) > limit: raise OnlineError('书源响应超出大小限制')
                    data = response.read(limit + 1)
                    if len(data) > limit: raise OnlineError('书源响应超出大小限制')
                    return data
            except HTTPError as exc:
                if exc.code == 429 and attempt < attempts-1:
                    try: wait = min(60, max(1, int(exc.headers.get('Retry-After', '3'))))
                    except ValueError: wait = 3
                    time.sleep(wait); continue
                raise SourceHttpError(exc.code) from None
            except (URLError, TimeoutError, OSError) as exc:
                if attempt<attempts-1:
                    time.sleep(.5*(attempt+1));continue
                raise OnlineError('网络连接失败，请检查网络或书源服务；已下载章节仍可离线阅读') from exc
        raise OnlineError('书源请求未完成')

    def json(self, url):
        try: return json.loads(self.read(url, JSON_LIMIT))
        except (ValueError, UnicodeError): raise OnlineError('书源没有返回有效的 JSON 数据') from None

def normalize_source(raw):
    if not isinstance(raw, dict) or raw.get('type') not in KINDS: raise OnlineError('不支持的书源类型')
    out = {k: raw[k] for k in ('id','name','type','base_url','language','source_id','username','password','api_key','token','enabled','connection') if k in raw}
    out['id'] = str(out.get('id') or uuid.uuid4().hex)
    out['name'] = str(out.get('name') or out['type'])[:120]
    out['base_url'] = checked_url(out.get('base_url', '')).rstrip('/')
    out.setdefault('enabled', True); out.setdefault('language', 'zh')
    if out.get('connection', 'system') not in ('system', 'direct'): raise OnlineError('连接方式必须是 system 或 direct')
    return out

class Sources:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists():
            try: self.data = json.loads(self.path.read_text('utf-8'))
            except (ValueError, OSError): raise OnlineError('书源配置损坏，原文件没有覆盖') from None
        else:
            self.data = {'version':1, 'sources':[], 'cache_roots':[]}
        self.data['sources'] = [normalize_source(s) for s in self.data.get('sources', [])]
        presets=json.loads(Path(__file__).with_name('builtin_sources.json').read_text('utf-8'))
        if self.data.get('builtin_revision',0)<presets['revision']:
            known={s['id'] for s in self.all}
            self.all.extend(normalize_source(s) for s in presets['sources'] if s['id'] not in known)
            self.data['builtin_revision']=presets['revision'];self.save()

    @property
    def all(self): return self.data['sources']
    def save(self): atomic_json(self.path, self.data)
    def get(self, source_id):
        s = next((s for s in self.all if s['id'] == source_id), None)
        if not s or not s.get('enabled', True): raise OnlineError('此书源已停用或移除；完整下载的章节仍可阅读')
        return s
    def put(self, source):
        s = normalize_source(source)
        old = next((v for v in self.all if v['id'] == s['id']), None)
        if old: old.clear(); old.update(s)
        else: self.all.append(s)
        self.save(); return s
    def import_configs(self, payload):
        raw = payload.get('sources') if isinstance(payload,dict) else payload
        if not isinstance(raw,list) or len(raw) > 100: raise OnlineError('书源包需要 sources 数组，最多 100 项')
        # Validate the entire batch before changing persisted state; never import secrets.
        candidates = [normalize_source(s) for s in raw]
        seen = {s['id'] for s in self.all}; count = 0
        for s in candidates:
            for key in ('username','password','api_key','token'): s.pop(key,None)
            if s['id'] not in seen: self.all.append(s); seen.add(s['id']); count += 1
        self.save(); return count
    def set_cache_root(self, directory):
        root = Path(directory).expanduser().resolve() / 'yukina-online-downloads'
        if os.name=='nt' and root.drive.casefold()=='c:': raise OnlineError('请为在线版选择 C 盘以外的独立缓存目录')
        root.mkdir(parents=True, exist_ok=True)
        marker = root / '.yukina-online-cache'
        if not marker.exists():
            if any(root.iterdir()): raise OnlineError('目标目录已存在其他内容，请另选一个缓存目录')
            marker.write_text('Yukina Online chapter cache v1\n',encoding='ascii')
        # Check writable now; retain prior roots so changing destination keeps offline books.
        test = root / ('.write-' + uuid.uuid4().hex); test.write_bytes(b''); test.unlink()
        roots = self.data.setdefault('cache_roots', [])
        roots[:] = [str(root)] + [r for r in roots if r != str(root)]
        self.save(); return root

class Provider:
    def __init__(self, source): self.s=source; self.http=Http(source); self.base=source['base_url'].rstrip('/')
    def api(self, path, query=None):
        return self.http.json(self.base + path + (('?' + urlencode(query, doseq=True)) if query else ''))
    def search(self, term, page=1):
        kind=self.s['type']
        if kind=='dm5':
            from source_dm5 import Dm5Provider
            return Dm5Provider(self.s,self.http).search(term,page)
        if kind in ('manhuagui','mangapill'):
            from source_html import HtmlProvider
            return HtmlProvider(self.s,self.http).search(term,page)
        if kind == 'mangadex':
            q={'limit':30,'offset':(page-1)*30,'includes[]':['cover_art'],'contentRating[]':['safe','suggestive'],'order[followedCount]':'desc'}
            lang=self.s.get('language','zh');q['availableTranslatedLanguage[]']=['zh','zh-hk'] if lang=='zh' else [lang]
            if term: q['title']=term
            d=self.api('/manga',q); rows=[]
            for b in d.get('data',[]):
                a=b.get('attributes',{}); titles=a.get('title',{}); title=titles.get('zh') or titles.get('ja') or titles.get('en') or next(iter(titles.values()),'未命名')
                file=next((r.get('attributes',{}).get('fileName') for r in b.get('relationships',[]) if r.get('type')=='cover_art'),None)
                rows.append({'id':b['id'],'title':title,'cover':f"https://uploads.mangadex.org/covers/{b['id']}/{quote(file)}.256.jpg" if file else ''})
            return rows, d.get('offset',0)+len(rows)<d.get('total',0)
        if kind == 'komga':
            d=self.api('/api/v1/series',{'search':term,'page':page-1,'size':30,'sort':'metadata.titleSort,asc'})
            return [{'id':str(b['id']),'title':b.get('metadata',{}).get('title') or b.get('name','未命名'),'cover':self.base+f"/api/v1/series/{b['id']}/thumbnail"} for b in d.get('content',[])], not d.get('last',True)
        if kind == 'suwayomi':
            sid=quote(str(self.s.get('source_id','')),safe='')
            if not sid: raise OnlineError('请先从服务端选择一个扩展书源')
            d=self.api(f'/api/v1/source/{sid}/search',{'searchTerm':term,'pageNum':page}) if term else self.api(f'/api/v1/source/{sid}/popular/{page}')
            return [{'id':str(b['id']),'title':b.get('title','未命名'),'cover':self.base+f"/api/v1/manga/{b['id']}/thumbnail"} for b in d.get('mangaList',[])],d.get('hasNextPage',False)
        d=self.http.json(self.base)
        if not isinstance(d,dict) or not isinstance(d.get('books'),list): raise OnlineError('目录书源缺少 books 数组')
        rows=[dict(id=str(b['id']), title=b.get('title','未命名'),cover=urljoin(self.base,b.get('cover','')) if b.get('cover') else '') for b in d['books'] if term.casefold() in str(b.get('title','')).casefold()]
        return rows[(page-1)*30:page*30],len(rows)>page*30

    def extension_sources(self):
        if self.s['type']!='suwayomi': return []
        return self.api('/api/v1/source/list')
    def page_bytes(self,book_id,chapter,index,urls):
        try:
            if self.s['type']=='dm5':
                from source_dm5 import Dm5Provider
                return self.http.read(Dm5Provider(self.s,self.http).image_url(urls[index]))
            return self.http.read(urls[index])
        except SourceHttpError as error:
            if self.s['type'] not in ('mangadex','manhuagui','dm5') or error.status not in (401,403,404):raise
            # MangaDex CDN delivery tokens expire; refresh through the official API once.
            fresh=self.pages(book_id,chapter)
            if len(fresh)!=len(urls):raise OnlineError('章节页数已变化，请重新打开章节')
            urls[:]=fresh
            if self.s['type']=='dm5':
                from source_dm5 import Dm5Provider
                return self.http.read(Dm5Provider(self.s,self.http).image_url(urls[index]))
            return self.http.read(urls[index])

    def chapters(self, book_id):
        bid=quote(str(book_id),safe='');kind=self.s['type']
        if kind=='dm5':
            from source_dm5 import Dm5Provider
            return Dm5Provider(self.s,self.http).chapters(book_id)
        if kind in ('manhuagui','mangapill'):
            from source_html import HtmlProvider
            return HtmlProvider(self.s,self.http).chapters(book_id)
        if kind=='mangadex':
            lang=self.s.get('language','zh'); result=[]; offset=0
            while True:
                d=self.api(f'/manga/{bid}/feed',{'translatedLanguage[]':['zh','zh-hk'] if lang=='zh' else [lang],'limit':100,'offset':offset,'order[volume]':'asc','order[chapter]':'asc','includeExternalUrl':0,'contentRating[]':['safe','suggestive']})
                for c in d.get('data',[]):
                    a=c.get('attributes',{})
                    if a.get('externalUrl') or a.get('pages',0)<=0: continue
                    title=' · '.join(filter(None, [('卷 '+str(a['volume'])) if a.get('volume') else '',('第 '+str(a['chapter'])+' 话') if a.get('chapter') else '',a.get('title',''),a.get('translatedLanguage','')]))
                    result.append({'id':str(c['id']),'title':title or '未命名章节'})
                offset+=len(d.get('data',[]))
                if offset>=d.get('total',0) or not d.get('data'): break
                if offset>=10000: raise OnlineError('章节结果超过 10000 条，请缩小书源语言范围')
            return result
        if kind=='komga':
            result=[];page=0
            while True:
                d=self.api(f'/api/v1/series/{bid}/books',{'page':page,'size':100,'sort':'metadata.numberSort,asc'})
                result.extend({'id':str(c['id']),'title':c.get('metadata',{}).get('title') or c.get('name','未命名章节')} for c in d.get('content',[]))
                if d.get('last',True): return result
                page+=1
                if page>=100: raise OnlineError('章节过多，请拆分服务端图书')
        if kind=='suwayomi':
            d=self.api(f'/api/v1/manga/{bid}/chapters',{'onlineFetch':'true'})
            return [{'id':str(c['id']),'title':c.get('name','未命名章节'),'index':c['index']} for c in sorted(d,key=lambda c:c.get('chapterNumber',c['index']))]
        d=self.http.json(self.base);b=next((b for b in d.get('books',[]) if str(b['id'])==str(book_id)),None)
        if not b: raise OnlineError('书源目录中未找到该作品')
        return [{'id':str(c['id']),'title':c.get('title','未命名章节'),'pages':[urljoin(self.base,p) for p in c.get('pages',[])]} for c in b.get('chapters',[])]

    def pages(self, book_id, chapter):
        kind=self.s['type']; cid=quote(str(chapter['id']),safe='');bid=quote(str(book_id),safe='')
        if kind=='mangadex':
            d=self.api(f'/at-home/server/{cid}',{'forcePort443':'true'});c=d.get('chapter',{});base=checked_url(d['baseUrl']);h=quote(c['hash'],safe='')
            original=[f'{base}/data/{h}/{quote(p,safe="")}' for p in c.get('data',[])]
            saver=[f'{base}/data-saver/{h}/{quote(p,safe="")}' for p in c.get('dataSaver',[])]
            pages=(original or saver) if self.s.get('_quality','original')=='original' else (saver or original)
        elif kind=='dm5':
            from source_dm5 import Dm5Provider
            pages=Dm5Provider(self.s,self.http).pages(chapter)
        elif kind in ('manhuagui','mangapill'):
            from source_html import HtmlProvider
            pages=HtmlProvider(self.s,self.http).pages(chapter)
        elif kind=='komga':
            d=self.api(f'/api/v1/books/{cid}/pages')
            pages=[self.base+f'/api/v1/books/{cid}/pages/{int(p["number"])}' for p in d]
        elif kind=='suwayomi':
            idx=int(chapter['index']);d=self.api(f'/api/v1/manga/{bid}/chapter/{idx}')
            pages=[self.base+f'/api/v1/manga/{bid}/chapter/{idx}/page/{i}' for i in range(int(d.get('pageCount',0)))]
        else:
            pages=chapter.get('pages',[])
            if not pages:
                chapter=next((c for c in self.chapters(book_id) if c['id']==str(chapter['id'])),{})
                pages=chapter.get('pages',[])
        if not pages: raise OnlineError('章节没有可用页面，可能已移除或需要登录')
        if len(pages)>10000: raise OnlineError('单章节超过 10000 页')
        return [checked_url(p) for p in pages]

def chapter_uri(source_id, book_id, chapter_id):
    return 'online://'+quote(str(source_id),safe='')+'/'+quote(str(book_id),safe='')+'/'+quote(str(chapter_id),safe='')

def merge_entry(source, book, chapters, old=None):
    if not chapters: raise OnlineError('此作品没有当前语言可阅读的章节')
    entry=old or {'id':uuid.uuid4().hex,'kind':'folder','page':0,'added':time.time(),'reading_status':'想读'}
    prior={c['path']:c for c in entry.get('volumes',[])};children=[];seen=set()
    for ch in chapters:
        path=chapter_uri(source['id'],book['id'],ch['id'])
        if path in seen: continue
        seen.add(path);c=prior.get(path,{'id':uuid.uuid4().hex,'path':path,'page':0})
        c.update(title=ch['title'],online={'source_id':source['id'],'book_id':str(book['id']),'chapter':ch})
        children.append(c)
    children.extend(c for path,c in prior.items() if path not in seen)
    entry.update(kind='folder',path='online://'+quote(source['id'],safe='')+'/'+quote(str(book['id']),safe=''),volumes=children,
                 online={'source_id':source['id'],'source_name':source['name'],'book_id':str(book['id']),'cover':book.get('cover',''),'title':book['title']})
    if not entry.get('title_custom'): entry['title']=book['title']
    return entry

def cache_key(volume):
    return hashlib.sha256(volume['path'].encode('utf-8')).hexdigest()

def page_identity(source,url):
    if source.get('type')=='dm5':
        from urllib.parse import parse_qs
        parsed=urlsplit(url);page=parse_qs(parsed.query).get('page',[''])[0]
        return urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode({'page':page}),''))
    parts=urlsplit(url).path.split('/')
    if source.get('type')=='manhuagui':return urlsplit(url)._replace(query='',fragment='').geturl()
    if source.get('type')=='mangadex' and len(parts)>=3 and parts[-3] in ('data','data-saver'):
        return '/'.join(parts[-3:])
    return url

class Cache:
    def __init__(self, sources): self.sources=sources; self.lock=threading.RLock()
    def locations(self, volume):
        return [Path(r)/'chapters'/cache_key(volume) for r in self.sources.data.get('cache_roots',[])]
    def manifest(self, volume, complete=True):
        for folder in self.locations(volume):
            try:
                d=json.loads((folder/'chapter.json').read_text('utf-8'))
                if d.get('path')!=volume['path'] or complete and not d.get('complete'): continue
                pages=d.get('pages',[])
                if not pages or len(pages)>10000: continue
                if any(p.get('file')!=f'{i+1:06d}.img' for i,p in enumerate(pages)): continue
                return folder,d
            except (OSError,ValueError,TypeError): continue
        return None
    def read_page(self, folder, item):
        file=(folder/item['file']).resolve()
        if file.parent!=folder.resolve(): raise OnlineError('缓存清单路径非法')
        if not file.is_file() or file.stat().st_size>PAGE_LIMIT: raise OnlineError('离线缓存缺失或过大，请重新下载章节')
        data=file.read_bytes()
        if hashlib.sha256(data).hexdigest()!=item['sha256']: raise OnlineError('离线缓存校验失败，请重新下载章节')
        return data
    def download(self, volume, provider, cancelled=None, progress=lambda n,total:None, book_title=None):
        with self.lock:
            roots=self.sources.data.get('cache_roots',[])
            if not roots: raise OnlineError('请先选择独立的下载缓存目录')
            root=Path(roots[0]).resolve()
            if not (root/'.yukina-online-cache').is_file(): raise OnlineError('缓存目录标记不存在，请重新选择下载路径')
            folder=root/'chapters'/cache_key(volume);folder.mkdir(parents=True,exist_ok=True)
            if folder.is_symlink() or (root/'chapters').resolve().parent!=root or folder.resolve().parent!=(root/'chapters').resolve():raise OnlineError('缓存章节目录不能是外部链接')
            prior=self.manifest(volume,False);old={page_identity(provider.s,p['url']):p for p in prior[1].get('pages',[])} if prior and prior[0]==folder else {}
            meta=volume['online'];urls=provider.pages(meta['book_id'],meta['chapter'])
            manifest={'version':1,'path':volume['path'],'title':volume['title'],'complete':False,'pages':[]}
            if book_title:manifest['book_title']=book_title
            elif prior and prior[1].get('book_title'):manifest['book_title']=prior[1]['book_title']
            for i,url in enumerate(urls):
                if cancelled and cancelled.is_set(): raise Cancelled('下载已暂停，可再次下载继续')
                name=f'{i+1:06d}.img';oldpage=old.get(page_identity(provider.s,url))
                try:
                    data=self.read_page(folder,oldpage) if oldpage and oldpage.get('file')==name else None
                except OnlineError: data=None
                if data is None:
                    data=provider.page_bytes(meta['book_id'],meta['chapter'],i,urls);url=urls[i]
                    # Validate image before declaring it offline-ready (Qt imported lazily).
                    from PySide6.QtGui import QImageReader
                    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
                    buf=QBuffer();buf.setData(QByteArray(data));buf.open(QIODevice.OpenModeFlag.ReadOnly);reader=QImageReader(buf)
                    size=reader.size()
                    if not size.isValid() or size.width()*size.height()>120_000_000: raise OnlineError('书源返回了无效或过大的页面图片')
                    reader.setScaledSize(size.scaled(QSize(2048,4096),Qt.AspectRatioMode.KeepAspectRatio))
                    if reader.read().isNull():raise OnlineError('页面图片不完整或无法解码，未记为下载完成')
                    temp=folder/(name+'.part');temp.write_bytes(data);temp.replace(folder/name)
                manifest['pages'].append({'file':name,'url':url,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)})
                atomic_json(folder/'chapter.json',manifest);progress(i+1,len(urls))
            manifest['complete']=True;atomic_json(folder/'chapter.json',manifest)
            return folder
    def remove(self, volume):
        # Never recursively delete arbitrary user directories or follow symlinks.
        for folder in self.locations(volume):
            root=folder.parent.parent
            if folder.is_symlink() or not (root/'.yukina-online-cache').is_file(): continue
            if (root/'chapters').resolve().parent!=root.resolve() or folder.resolve().parent!=(root/'chapters').resolve(): continue
            if not folder.exists(): continue
            for path in folder.iterdir():
                if path.is_file() and not path.is_symlink() and (path.name=='chapter.json' or path.name.endswith(('.img','.img.part','.json.tmp'))): path.unlink()
            try: folder.rmdir()
            except OSError: pass
    def size(self):
        return sum(p.stat().st_size for r in self.sources.data.get('cache_roots',[]) for p in (Path(r)/'chapters').glob('*/*') if p.is_file() and not p.is_symlink())
    def all_volumes(self):
        found={}
        for raw in self.sources.data.get('cache_roots',[]):
            root=Path(raw).resolve()
            if not (root/'.yukina-online-cache').is_file():continue
            for file in (root/'chapters').glob('*/chapter.json'):
                try:
                    if file.is_symlink() or (root/'chapters').resolve().parent!=root or file.parent.resolve().parent!=(root/'chapters').resolve() or file.stat().st_size>JSON_LIMIT:continue
                    meta=json.loads(file.read_text('utf-8'));path=meta['path']
                    if not path.startswith('online://') or hashlib.sha256(path.encode()).hexdigest()!=file.parent.name:continue
                    found[path]={'path':path,'title':meta.get('title','离线章节')}
                except (OSError,ValueError,KeyError,TypeError):continue
        return list(found.values())

class OnlineService:
    def __init__(self, root, library):
        self.root=Path(root);self.library=library;self.sources=Sources(self.root/'data'/'online-sources.json');self.cache=Cache(self.sources);self.providers={};self.memory=PageMemory()
    def provider(self, source_id,quality='original'):
        s=dict(self.sources.get(source_id),_quality=quality);fingerprint=json.dumps(s,sort_keys=True);key=(source_id,quality)
        if key not in self.providers or self.providers[key][0]!=fingerprint:self.providers[key]=(fingerprint,Provider(s))
        return self.providers[key][1]
    def find_volume(self, path):
        for entry in self.library.data['books']:
            for child in entry.get('volumes',[entry]):
                if child.get('path')==path: return child
        raise OnlineError('章节已从书库移除')

SERVICE=None

class OnlineBook:
    online=True
    doc=None
    def __init__(self,path,quality=None):
        if SERVICE is None:raise OnlineError('在线书源服务尚未初始化')
        self.service=SERVICE;self.path=str(path);self.volume=SERVICE.find_volume(self.path);self.title=self.volume['title'];self.images=OrderedDict();self.lock=threading.RLock();self.closed=False
        self.quality=quality or SERVICE.library.data['settings'].get('online_quality','smooth');self.quality=self.quality if self.quality in ('low','smooth','original') else 'smooth'
        self.offline=SERVICE.cache.manifest(self.volume);memory=SERVICE.memory
        if self.offline:
            self.urls=[p['url'] for p in self.offline[1]['pages']];self.provider=None;self.identity=('offline',self.path,hashlib.sha256(json.dumps(self.offline[1],sort_keys=True).encode()).hexdigest())
        else:
            meta=self.volume['online'];self.provider=SERVICE.provider(meta['source_id'],self.quality)
            source_key=hashlib.sha256(json.dumps(SERVICE.sources.get(meta['source_id']),sort_keys=True).encode()).hexdigest()
            mode='saver' if self.provider.s['type']=='mangadex' and self.quality!='original' else 'original'
            self.identity=(source_key,self.path,mode)
            def manifest():
                cached=memory.manifests.get(self.identity)
                if cached is not None:return cached
                urls=self.provider.pages(meta['book_id'],meta['chapter']);memory.manifests.put(self.identity,tuple(urls),sum(len(u)*4 for u in urls),300);return tuple(urls)
            self.urls=list(memory.load(('manifest',self.identity),manifest))
    def __len__(self):return len(self.urls)
    def ready(self,index):return index in self.images or self.service.memory.images.get((self.identity,index,self.quality)) is not None
    def render(self,index,scale=1.5):
        from PySide6.QtGui import QImage
        if self.closed:raise OnlineError('章节已关闭')
        if not 0<=index<len(self):raise IndexError(index)
        memory=self.service.memory;key=(self.identity,index,self.quality);raw_key=(self.identity,index)
        with self.lock:
            image=self.images.get(index)
            if image is not None:self.images.move_to_end(index);return image
        def prepare():
            existing=memory.images.get(key)
            if existing is not None:return existing
            packed=memory.prepared.get(key)
            if packed is not None:image=QImage.fromData(packed)
            else:
                def fetch():
                    data=memory.raw.get(raw_key)
                    if data is not None:return data
                    if self.offline:data=self.service.cache.read_page(self.offline[0],self.offline[1]['pages'][index])
                    else:
                        meta=self.volume['online'];data=self.provider.page_bytes(meta['book_id'],meta['chapter'],index,self.urls)
                    memory.raw.put(raw_key,data,len(data));return data
                data=memory.load(('bytes',raw_key),fetch)
                try:image,packed=decode_page(data,self.quality)
                except ValueError as e:
                    memory.raw.discard(raw_key);raise OnlineError(str(e)) from e
                if packed is not None:memory.prepared.put(key,packed,len(packed))
            if image.isNull():raise OnlineError('图片解码失败')
            memory.images.put(key,image,image.sizeInBytes());return image
        image=memory.load(('render',key),prepare)
        with self.lock:
            if self.closed:raise OnlineError('章节已关闭')
            self.images[index]=image
            while len(self.images)>2 and (len(self.images)>8 or sum(im.sizeInBytes() for im in self.images.values())>64*1024*1024):self.images.popitem(last=False)
        return image
    def close(self):
        self.closed=True
        with self.lock:self.images.clear()
