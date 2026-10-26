"""Read-only live source acceptance: one decoded page per source, held in RAM."""
import hashlib,json,sys,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'))
from online_core import Provider
from PySide6.QtGui import QImage
presets=json.loads((ROOT/'sources/common-presets.json').read_text('utf-8'))
results=[]
for source in presets['sources']:
    p=Provider(source);r={'source':source['name'],'type':source['type'],'stage':'search','passed':False}
    try:
        term={'mangadex':'','manhuagui':'海贼王','mangapill':'one piece','goda':'重生佣兵','comicabc':'世界最強','mangakatana':'one piece'}[source['type']]
        books,more=p.search(term);r['results']=len(books)
        if not books:raise ValueError('No search results')
        expected={'manhuagui':'/comic/1128/','mangapill':'/manga/2/one-piece','goda':'/manga/chongshengyongbingwanmeijihua','comicabc':'/html/21858.html','mangakatana':'/manga/one-piece.49'}.get(source['type'])
        book=next((b for b in books if b['id']==expected),books[0]);r['stage']='chapters'
        if source['type']=='mangadex':
            feed=p.api('/manga/'+book['id']+'/feed',{'limit':1,'translatedLanguage[]':['zh','zh-hk'],'includeExternalUrl':0,'contentRating[]':['safe','suggestive']});chapters=[{'id':x['id']} for x in feed.get('data',[])]
        else:chapters=p.chapters(book['id'])
        r['chapters']=len(chapters)
        if not chapters:raise ValueError('No readable chapters')
        r['stage']='page-manifest';chapter=chapters[0];urls=p.pages(book['id'],chapter);r['pages']=len(urls)
        r['stage']='image';data=p.page_bytes(book['id'],chapter,0,urls);image=QImage.fromData(data)
        if image.isNull():raise ValueError('Response cannot be decoded as an image')
        r.update(passed=True,pageBytes=len(data),width=image.width(),height=image.height(),sha256=hashlib.sha256(data).hexdigest())
    except Exception as e:r['error']=str(e)
    results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
report={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'transport':'production desktop HTTPS, certificate validation enabled','pageFilesSaved':False,'sources':results}
path=ROOT/'work/common-sources/live-verification.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
