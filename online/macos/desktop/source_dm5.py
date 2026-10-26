"""DM5 public chapters: fixed HTML/literal parsing, never executes site scripts.

Endpoint reference: Keiyoushi dm5 (Apache-2.0). Each page resolver is fetched
only when requested; no full-chapter image download and no disk page cache.
"""
import ast
import re
from urllib.parse import urlencode,urljoin,urlsplit,parse_qs
from source_html import SourceDocument,text_of,local_path,markup,unpack_literal_script

STRING=r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')'''

def literal(text,name):
    match=re.search(r'\b(?:var\s+)?'+re.escape(name)+r'\s*=\s*('+STRING+r'|\d+)\s*;',text)
    if not match:raise ValueError('章节未提供公开图片数据，可能需要登录、付费或已下架')
    return ast.literal_eval(match[1])

class Dm5Provider:
    def __init__(self,source,http):self.base=source['base_url'].rstrip('/');self.http=http
    def document(self,path):return markup(self.http.read(urljoin(self.base+'/',path),8*1024*1024))
    def search(self,term,page):
        path='/search?'+urlencode({'title':term,'language':1,'page':page}) if term else f'/manhua-list-p{page}/'
        doc=SourceDocument(self.document(path));found={};more=False
        for a in doc.anchors:
            p=local_path(self.base,a['attrs'].get('href',''));parents=a['ancestors']
            in_title=any('title' in v.get('class','').split() for t,v in parents)
            if re.fullmatch(r'/manhua-[a-zA-Z0-9-]+/',p) and in_title and text_of(a):found.setdefault(p,{'id':p,'title':text_of(a),'cover':''})
            if parse_qs(urlsplit(a['attrs'].get('href','')).query).get('page')==[str(page+1)]:more=True
            if re.fullmatch(r'/manhua-list-p'+str(page+1)+'/',p):more=True
        # Search endpoints also suggest loosely related titles. Keep their real
        # titles intact so a guidebook is never presented as the main series.
        rows=list(found.values())
        if term:
            key=lambda text:re.sub(r'[\W_]+','',text.casefold())
            query=key(term);rows=[b for b in rows if query in key(b['title'])]
            rows.sort(key=lambda b:len(key(b['title']))-len(query))
        return rows,more
    def chapters(self,book_id):
        if not re.fullmatch(r'/manhua-[a-zA-Z0-9-]+/',str(book_id)):raise ValueError('作品地址无效')
        doc=SourceDocument(self.document(book_id));groups={};seen=set()
        for a in doc.anchors:
            p=local_path(self.base,a['attrs'].get('href',''))
            if not any(v.get('id')=='chapterlistload' for t,v in a['ancestors']):continue
            if not re.fullmatch(r'/m\d+/',p) or a['locked'] or p in seen:continue
            seen.add(p);group=next((v.get('id','') for t,v in a['ancestors'] if t=='ul' and v.get('id','').startswith('detail-list-select-')),'default')
            groups.setdefault(group,[]).append({'id':p,'title':text_of(a) or '未命名章节'})
        # Native site lists each chapter group newest-first.
        return [chapter for group in groups.values() for chapter in reversed(group)]
    def pages(self,chapter):
        path=chapter['id']
        if not re.fullmatch(r'/m\d+/',path):raise ValueError('章节地址无效')
        raw=self.document(path)
        cid=literal(raw,'DM5_CID');mid=literal(raw,'DM5_MID');count=literal(raw,'DM5_IMAGE_COUNT')
        if not isinstance(count,int) or not 0<count<=10000:raise ValueError('章节页数无效')
        dt=literal(raw,'DM5_VIEWSIGN_DT');sign=literal(raw,'DM5_VIEWSIGN')
        if not dt or not sign:raise ValueError('该章节未提供公开阅读数据')
        return [urljoin(self.base,path+'chapterfun.ashx')+'?'+urlencode({'cid':cid,'page':i,'key':'','language':1,'gtk':6,'_cid':cid,'_mid':mid,'_dt':dt,'_sign':sign}) for i in range(1,count+1)]
    def image_url(self,resolver):
        from online_core import checked_url,origin
        if origin(resolver)!=origin(self.base) or not re.fullmatch(r'/m\d+/chapterfun\.ashx',urlsplit(resolver).path):raise ValueError('图片解析地址无效')
        raw=unpack_literal_script(self.document(resolver));prefix=literal(raw,'pix')
        match=re.search(r'\bvar\s+pvalue\s*=\s*(\[\s*'+STRING+r'(?:\s*,\s*'+STRING+r')*\s*\])',raw)
        tail=re.search(r'pix\s*\+\s*pvalue\[i\]\s*\+\s*('+STRING+r')',raw)
        if not match:raise ValueError('该页未提供可用图片，可能已下架')
        values=ast.literal_eval(match[1])
        if not values:raise ValueError('该页没有可用图片')
        first=values[0]
        if first.startswith(('https://','http://','//')):return checked_url(urljoin(self.base,first))
        if not tail:raise ValueError('图片地址格式已改变')
        return checked_url(prefix+first+ast.literal_eval(tail[1]))
