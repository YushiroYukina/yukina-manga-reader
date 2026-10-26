"""ComicABC public works. Fixed record decoding, never evaluates site JavaScript.
Protocol reference: Keiyoushi Comicabc (Apache-2.0). Login-only results excluded.
"""
import ast,re
from urllib.parse import urlencode,urlsplit,parse_qs,urljoin
from source_html import SourceDocument,markup,text_of,local_path

def record_images(script,chapter):
    literal=r"'(?:\\.|[^'\\])*'";values=[ast.literal_eval(m[1]) for m in re.finditer(r'var\s+\w+\s*=\s*('+literal+r')',script)]
    candidates=[s for s in values if isinstance(s,str) and len(s)>1000]
    if not candidates:raise ValueError('未找到公开图片记录')
    big=max(candidates,key=len);count=re.search(r'for\s*\(var\s+i=0;i<(\d+);i\+\+\)',script);book=re.search(r'var\s+ti=(\d+)',script)
    if not count or not book or int(count[1])>10000 or len(big)>4*1024*1024:raise ValueError('图片记录格式已变化')
    if not re.search(r'\.length-47-\w+\*6',script):raise ValueError('图片记录版本不受支持')
    target=re.fullmatch(r'(\d+)([a-z]?)',chapter)
    if not target:raise ValueError('章节编号无效')
    alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    def number(text):
        if len(text)!=2:return text
        if any(c not in alphabet for c in text):raise ValueError('图片记录编号无效')
        return 8000+alphabet.index(text[1]) if text[0]=='Z' else alphabet.index(text[0])*52+alphabet.index(text[1])
    def tail(n):
        start=len(big)-47-n*6
        try:return bytes.fromhex(big[start:start+6]).decode('ascii')
        except (ValueError,UnicodeError):raise ValueError('图片主机信息无效') from None
    for i in range(int(count[1])):
        record=big[i*47:(i+1)*47]
        if len(record)!=47:raise ValueError('图片记录不完整')
        cid=number(record[42:44]);part=record[46]
        if cid!=int(target[1]) or target[2] and part!=target[2]:continue
        pages=number(record[:2]);folder=str(number(record[44:46]));cipher=record[2:42]
        if not isinstance(pages,int) or not 0<pages<=10000 or len(folder)<2:raise ValueError('图片记录范围无效')
        host=tail(4)+folder[0]+'.8'+tail(3)+tail(2)+tail(3)
        if not host.endswith('.8comic.com') or not re.fullmatch(r'[A-Za-z0-9.-]+',host):raise ValueError('未知的图片主机')
        prefix='https://'+host+'/'+folder[1]+'/'+book[1]+'/'+str(cid)+('' if part=='0' else part)+'/'
        return [prefix+f'{j:03d}_'+cipher[((j-1)//10)%10+((j-1)%10)*3:((j-1)//10)%10+((j-1)%10)*3+3]+'.'+tail(1) for j in range(1,pages+1)]
    raise ValueError('该章节没有公开图片记录，可能需要登录或已下架')

class ComicabcProvider:
    def __init__(self,source,http):self.base=source['base_url'].rstrip('/');self.http=http;self.reader='https://articles.onemoreplace.tw'
    def get(self,url):return markup(self.http.read(url,8*1024*1024))
    def search(self,term,page):
        url=self.base+'/member/search.aspx?'+urlencode({'key':term,'page':page}) if term else self.base+f'/comic/h-{page}.html'
        doc=SourceDocument(self.get(url));rows={};blocked=set();more=False
        for a in doc.anchors:
            path=local_path(self.base,a['attrs'].get('href',''));title=text_of(a)
            if re.fullmatch(r'/html/\d+\.html',path):
                if 'comicpic_col6' not in a['attrs'].get('class','').split():continue
                if '登入觀看' in title or '登录观看' in title:blocked.add(path);continue
                title=''.join(a['caption']).strip() or title
                row=rows.setdefault(path,{'id':path,'title':'','cover':''})
                if title:row['title']=title
                if a['cover']:row['cover']=urljoin(self.base,a['cover'])
            if '下一頁' in title or '下一页' in title or 'mdi-skip-next' in a['attrs'].get('class',''):more=True
        return [r for k,r in rows.items() if k not in blocked and r['title']],more
    def chapters(self,book_id):
        book=re.fullmatch(r'/html/(\d+)\.html',book_id)
        if not book:raise ValueError('作品地址无效')
        raw=self.get(self.base+book_id);doc=SourceDocument(raw);rows={}
        for a in doc.anchors:
            title=text_of(a);call=a['attrs'].get('onclick','');match=re.search(r"cview\(['\"]"+book[1]+r'-([0-9]+[a-z]?)\.html',call)
            if match:
                cid=match[1];url=self.reader+'/online/new-'+book[1]+'.html?ch='+cid
                rows.setdefault(url,{'id':url,'title':title or '第 '+cid+' 話'})
        if not rows:raise ValueError('未找到公开章节；可能需要登录或作品已下架')
        return sorted(rows.values(),key=lambda c:(int(re.search(r'ch=(\d+)',c['id'])[1]),c['id']))
    def pages(self,chapter):
        parsed=urlsplit(chapter['id']);ch=parse_qs(parsed.query).get('ch',[''])[0]
        if parsed.scheme!='https' or parsed.netloc!='articles.onemoreplace.tw' or not re.fullmatch(r'/online/new-\d+\.html',parsed.path) or not re.fullmatch(r'\d+[a-z]?',ch):raise ValueError('章节地址无效')
        raw=self.get(chapter['id']);scripts=re.findall(r'<script\b[^>]*>([\s\S]*?)</script>',raw,re.I)
        script=next((s for s in scripts if '$("#comics-pics").html(xx)' in s),'')
        return record_images(script,ch)
