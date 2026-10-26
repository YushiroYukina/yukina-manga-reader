"""MangaKatana fixed HTML/literal-array adapter. No JavaScript execution.
Endpoint reference: Keiyoushi MangaKatana, Apache-2.0.
"""
import ast,re
from urllib.parse import urlencode,urljoin
from source_html import SourceDocument,markup,text_of,local_path

class KatanaProvider:
    def __init__(self,source,http):self.http=http;self.base=source['base_url'].rstrip('/')
    def get(self,path):return markup(self.http.read(urljoin(self.base+'/',path),8*1024*1024))
    def search(self,term,page):
        path=f'/page/{page}?'+urlencode({'search':term,'search_by':'book_name'}) if term else f'/manga/page/{page}'
        doc=SourceDocument(self.get(path));rows={};more=False
        for a in doc.anchors:
            path=local_path(self.base,a['attrs'].get('href',''))
            if re.fullmatch(r'/manga/[^/]+\.\d+',path):
                if 'book_list' not in a['context']:continue
                row=rows.setdefault(path,{'id':path,'title':'','cover':''});title=text_of(a)
                if title:row['title']=title
                if a['cover']:row['cover']=urljoin(self.base,a['cover'])
            if 'next' in a['attrs'].get('class','').split() and 'page-numbers' in a['attrs'].get('class','').split():more=True
        return [r for r in rows.values() if r['title']],more
    def chapters(self,book_id):
        if not re.fullmatch(r'/manga/[^/]+\.\d+',book_id):raise ValueError('作品地址无效')
        doc=SourceDocument(self.get(book_id));rows={}
        for a in doc.anchors:
            path=local_path(self.base,a['attrs'].get('href',''))
            if re.fullmatch(re.escape(book_id)+r'/c[0-9.]+(?:x\d+)?',path):rows.setdefault(path,{'id':path,'title':text_of(a) or '未命名章节'})
        return list(reversed(list(rows.values())))
    def pages(self,chapter):
        if not re.fullmatch(r'/manga/[^/]+\.\d+/c[0-9.]+(?:x\d+)?',chapter['id']):raise ValueError('章节地址无效')
        raw=self.get(chapter['id']);name=re.search(r'''data-src['"],\s*(\w+)''',raw)
        if not name:raise ValueError('未找到公开图片清单')
        match=re.search(r'var\s+'+re.escape(name[1])+r'\s*=\s*\[([^\[]*)\]',raw)
        if not match or len(match[1])>4*1024*1024:raise ValueError('图片清单格式已变化')
        literals=re.findall(r"'(?:\\.|[^'\\])*'",match[1]);urls=[ast.literal_eval(v) for v in literals]
        if not urls or len(urls)>10000:raise ValueError('章节没有可用页面')
        return urls
