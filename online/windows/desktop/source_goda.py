"""Fixed public GoDa catalog adapter (Baozimh.org), never executes site scripts.

Protocol reference: Keiyoushi GoDa / baozimhorg, Apache-2.0.
Original bounded implementation of the published image-list wire format.
"""
import base64,json,re
from urllib.parse import quote,urljoin,parse_qs,urlsplit
from source_html import SourceDocument,markup,text_of,local_path

def decode_images(value):
    if not isinstance(value,str) or len(value)>4*1024*1024 or not value.startswith('J7r') or not value.endswith('nQ'):raise ValueError('未知的图片清单格式')
    body=value[3:-2];length=len(body)-5
    if length<=0:raise ValueError('图片清单不完整')
    a=length//3;b=(length-a)//2;c=length-a-b
    if body[b:b+2]!='kD' or body[b+2+c:b+2+c+3]!='W4s':raise ValueError('图片清单标记无效')
    value=body[b+2+c+3:]+body[:b]+body[b+2:b+2+c]
    value=''.join(value[i:i+7][::-1] if (i//7)%2 else value[i:i+7] for i in range(0,len(value),7))
    custom='_-9876543210abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';standard='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
    if any(ch not in custom for ch in value):raise ValueError('图片清单字符无效')
    value=value.translate(str.maketrans(custom,standard));rows=json.loads(base64.urlsafe_b64decode(value+'='*((-len(value))%4)).decode('utf-8'))
    if not isinstance(rows,list) or not 0<len(rows)<=10000:raise ValueError('图片清单大小无效')
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('url'),str) or not row['url'].startswith('/') or row['url'].startswith('//'):raise ValueError('图片路径无效')
    return sorted(rows,key=lambda r:int(r.get('order',0)))

class GodaProvider:
    def __init__(self,source,http):self.source=source;self.http=http;self.base=source['base_url'].rstrip('/');self.api='https://api-get-v3.mgsearcher.com'
    def search(self,term,page):
        path=f'/s/{quote(term,safe="")}?page={page}' if term else f'/hots/page/{page}'
        doc=SourceDocument(markup(self.http.read(self.base+path,8*1024*1024)));found={};more=False
        for anchor in doc.anchors:
            attrs=anchor['attrs'];path=local_path(self.base,attrs.get('href',''));title=text_of(anchor)
            if re.fullmatch(r'/manga/[^/]+/?',path):
                if 'cardlist' not in anchor['context']:continue
                title=''.join(anchor['headline']).strip() or title
                title=title.removesuffix('連載').removesuffix('完結').strip();row=found.setdefault(path,{'id':path,'title':'','cover':''})
                if title:row['title']=title
                if anchor['cover']:
                    cover=urljoin(self.base,anchor['cover']);row['cover']=parse_qs(urlsplit(cover).query).get('url',[cover])[0]
            label=attrs.get('aria-label','')
            if label in ('下一頁','下一页','NEXT') and attrs.get('aria-disabled')!='true':more=True
        return [r for r in found.values() if r['title']],more
    def chapters(self,book_id):
        if not re.fullmatch(r'/manga/[^/]+/?',book_id):raise ValueError('作品地址无效')
        raw=markup(self.http.read(self.base+book_id,8*1024*1024));match=re.search(r'data-mid=["\'](\d+)["\']',raw)
        if not match:raise ValueError('该作品已下架或没有公开章节')
        mid=match[1];data=self.http.json(self.api+'/api/manga/get?mid='+mid+'&mode=all').get('data',{});rows=[]
        for chapter in sorted(data.get('chapters',[]),key=lambda c:float(c.get('attributes',{}).get('order',0))):
            attrs=chapter.get('attributes',{});cid=str(chapter.get('id',''))
            if cid.isdigit():rows.append({'id':mid+'/'+cid,'title':attrs.get('title') or '未命名章节'})
        if not rows:raise ValueError('该作品没有公开章节，可能已下架或尚未收录')
        return rows
    def pages(self,chapter):
        if not re.fullmatch(r'\d+/\d+',str(chapter['id'])):raise ValueError('章节地址无效')
        mid,cid=chapter['id'].split('/');data=self.http.json(self.api+'/api/v2/chapter/getinfo?m='+mid+'&c='+cid)
        try:value=data['data']['info']['images']['images']
        except (KeyError,TypeError):raise ValueError('该章节没有公开图片清单') from None
        return ['https://c-nd2-1.6wm.top'+row['url'] for row in decode_images(value)]
