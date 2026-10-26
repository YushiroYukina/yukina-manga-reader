"""Fixed, reviewed HTML adapters. Never evaluates or downloads JavaScript.

Endpoint/selector references: Keiyoushi MangaPill / Manhuagui (Apache-2.0).
LZ-string format reference: pieroxy/lz-string (MIT). Implementation below is
bounded and shared in behaviour with the Android SourceHtml implementation.
"""
import ast
import html
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin,urlsplit,urlencode,quote,parse_qs

class SourceDocument(HTMLParser):
    def __init__(self,text):
        super().__init__(convert_charrefs=True);self.stack=[];self.anchor=None;self.anchors=[];self.images=[];self.feed(text);self.close()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a':
            self.anchor={'attrs':attrs,'text':[],'group':next((v.get('id','') for t,v in reversed(self.stack) if v.get('id','').startswith('chapter-list-')),''),'cover':'','ancestors':[(t,dict(v)) for t,v in self.stack],'locked':False};self.anchors.append(self.anchor)
        if self.anchor and set(attrs.get('class','').split()) & {'detail-lock','view-lock'}:self.anchor['locked']=True
        if tag=='img':
            self.images.append((attrs,any(t=='picture' for t,a in self.stack)))
            if self.anchor:self.anchor['cover']=attrs.get('data-src') or attrs.get('data-original') or attrs.get('src','')
        if tag not in ('img','br','hr','meta','link','input','source','wbr','area','base','embed','param'):self.stack.append((tag,attrs))
    def handle_endtag(self,tag):
        if tag=='a':self.anchor=None
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:del self.stack[i:];break
    def handle_data(self,data):
        if self.anchor:self.anchor['text'].append(data)

def markup(raw):
    header=raw[:4096].decode('ascii','ignore').lower()
    charset='gb18030' if re.search(r'charset\s*=\s*["\']?(gbk|gb2312|gb18030)',header) else 'utf-8-sig'
    return raw.decode(charset,'replace')

def text_of(anchor):return ' '.join(html.unescape(anchor['attrs'].get('title') or ''.join(anchor['text'])).split())

def local_path(base,href):
    url=urljoin(base,html.unescape(href));a=urlsplit(base);b=urlsplit(url)
    if (a.scheme,a.netloc)!=(b.scheme,b.netloc):return ''
    return b.path

def lz_base64(value):
    alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='
    values=[alphabet.index(c) for c in value];state=[0,32]
    def bits(n):
        out=0
        for shift in range(n):
            if state[0]>=len(values):raise ValueError('压缩图片清单不完整')
            if values[state[0]]&state[1]:out|=1<<shift
            state[1]>>=1
            if not state[1]:state[1]=32;state[0]+=1
        return out
    lead=bits(2)
    if lead==2:return ''
    if lead not in (0,1):raise ValueError('不支持的压缩图片清单')
    previous=chr(bits(8 if lead==0 else 16));dictionary=['','','',previous];result=[previous];size=len(previous);width=3;remaining=4
    while size<2*1024*1024 and len(dictionary)<65536:
        code=bits(width)
        if code==2:return ''.join(result)
        if code in (0,1):dictionary.append(chr(bits(8 if code==0 else 16)));code=len(dictionary)-1;remaining-=1
        if remaining==0:remaining=1<<width;width+=1
        if code<len(dictionary):entry=dictionary[code]
        elif code==len(dictionary):entry=previous+previous[0]
        else:raise ValueError('压缩图片字典无效')
        result.append(entry);size+=len(entry);dictionary.append(previous+entry[0]);remaining-=1;previous=entry
        if remaining==0:remaining=1<<width;width+=1
    raise ValueError('图片清单解码超过限制')

def unpack_literal_script(document):
    if len(document)>2*1024*1024:raise ValueError('图片清单过大')
    literal=r"'(?:\\.|[^'\\])*'"
    pattern=r'\}\s*\(\s*('+literal+r')\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*('+literal+r')'
    match=re.search(pattern,document)
    if not match:raise ValueError('未找到公开图片清单；该章节可能不可用')
    payload=ast.literal_eval(match[1]);radix=int(match[2]);count=int(match[3]);symbols=ast.literal_eval(match[4]);suffix=document[match.end():match.end()+200].lstrip()
    if not 2<=radix<=62 or count>10000:raise ValueError('图片清单字典超出范围')
    if suffix.startswith('['):symbols=lz_base64(symbols)
    words=symbols.split('|');digits='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    def number(n):
        result=''
        while True:
            result=digits[n%radix]+result;n//=radix
            if not n:return result
    mapping={number(i):word for i,word in enumerate(words[:count]) if word}
    expanded=0
    def replace_word(match):
        nonlocal expanded
        value=mapping.get(match[0],match[0]);expanded+=len(value)
        if expanded>2*1024*1024:raise ValueError('解码图片清单过大')
        return value
    decoded=re.sub(r'\b[0-9A-Za-z]+\b',replace_word,payload)
    if len(decoded)>2*1024*1024:raise ValueError('解码图片清单过大')
    return decoded

def unpack_images(document):
    decoded=unpack_literal_script(document)
    start=decoded.find('{')
    if start<0:raise ValueError('图片清单缺少数据')
    meta,_=json.JSONDecoder().raw_decode(decoded[start:])
    if not isinstance(meta.get('files'),list) or not isinstance(meta.get('path'),str):raise ValueError('图片清单格式已改变')
    return meta

class HtmlProvider:
    def __init__(self,source,http):self.source=source;self.http=http;self.base=source['base_url'].rstrip('/');self.kind=source['type']
    def get(self,path):return markup(self.http.read(urljoin(self.base+'/',path),8*1024*1024))
    def search(self,term,page):
        url=('/search?'+urlencode({'q':term,'page':page})) if self.kind=='mangapill' else (f'/s/{quote(term,safe="")}_p{page}.html' if term else f'/list/view_p{page}.html')
        doc=SourceDocument(self.get(url));found={};more=False
        for anchor in doc.anchors:
            path=local_path(self.base,anchor['attrs'].get('href',''));title=text_of(anchor)
            pattern=r'/manga/\d+/[^/]+' if self.kind=='mangapill' else r'/comic/\d+/'
            if re.fullmatch(pattern,path):
                old=found.setdefault(path,{'id':path,'title':'','cover':''})
                if title and (not old['title'] or 'bcover' in anchor['attrs'].get('class','').split()):old['title']=title
                if anchor['cover']:old['cover']=urljoin(self.base,anchor['cover'])
            href=urljoin(self.base,anchor['attrs'].get('href',''));params=parse_qs(urlsplit(href).query)
            if self.kind=='mangapill' and urlsplit(href).path=='/search' and params.get('page')==[str(page+1)]:more=True
            if self.kind=='manhuagui' and re.search(r'_p'+str(page+1)+r'\.html$',path):more=True
        return [b for b in found.values() if b['title']],more
    def chapters(self,book_id):
        valid=re.fullmatch(r'/manga/(\d+)/[^/]+',book_id) if self.kind=='mangapill' else re.fullmatch(r'/comic/(\d+)/',book_id)
        if not valid:raise ValueError('作品地址无效')
        doc=SourceDocument(self.get(book_id));found={};group_order={}
        for anchor in doc.anchors:
            path=local_path(self.base,anchor['attrs'].get('href',''));title=text_of(anchor)
            okay=bool(re.fullmatch(r'/chapters/'+valid[1]+r'-[^/]+/[^/]+',path)) if self.kind=='mangapill' else bool(re.fullmatch(re.escape(book_id)+r'\d+\.html',path)) and 'status0' in anchor['attrs'].get('class','').split()
            if okay and path not in found:
                group=anchor['group'];group_order.setdefault(group,len(group_order));found[path]={'id':path,'title':title or '未命名章节','_group':group_order[group]}
        if self.kind=='mangapill':rows=list(reversed(list(found.values())))
        else:
            def key(ch):
                m=re.search(r'\d+(?:\.\d+)?',ch['title']);return ch['_group'],float(m[0]) if m else 1e10
            rows=sorted(found.values(),key=key)
        for ch in rows:ch.pop('_group',None)
        return rows
    def pages(self,chapter):
        path=chapter['id']
        if not re.fullmatch(r'/chapters/[^/]+/[^/]+|/comic/\d+/\d+\.html',path):raise ValueError('章节地址无效')
        raw=self.get(path)
        if self.kind=='mangapill':
            doc=SourceDocument(raw);return [urljoin(self.base,a.get('data-src') or a.get('src','')) for a,picture in doc.images if picture and (a.get('data-src') or a.get('src'))]
        meta=unpack_images(raw);signature=meta.get('sl') or {};query=urlencode({k:signature[k] for k in ('e','m') if k in signature})
        return ['https://i.hamreus.com'+meta['path']+quote(name,safe='/@')+('?' +query if query else '') for name in meta['files']]
