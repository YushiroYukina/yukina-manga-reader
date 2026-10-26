"""Small real API probe; at most one image in RAM, never a disk page download."""
import argparse,json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'))
from online_core import Provider
p=argparse.ArgumentParser();p.add_argument('--image',action='store_true');args=p.parse_args()
source={'id':'mangadex-zh','type':'mangadex','base_url':'https://api.mangadex.org','language':'zh'}
provider=Provider(source);result={'date':'2026-10-25','provider':'MangaDex','metadata':False,'pageDecoded':False}
try:
    result['stage']='search'
    rows,more=provider.search('',1);result.update(metadata=True,results=len(rows))
    if args.image:
        for book in rows[:3]:
            result['stage']='chapter-feed'
            feed=provider.api('/manga/'+book['id']+'/feed',{'limit':1,'translatedLanguage[]':['zh','zh-hk'],'includeExternalUrl':0,'contentRating[]':['safe','suggestive']})
            chapters=feed.get('data',[])
            if not chapters:continue
            result['stage']='page-manifest';ch=chapters[0];urls=provider.pages(book['id'],{'id':ch['id']})
            result['stage']='image';data=provider.http.read(urls[0])
            from PySide6.QtGui import QImage
            image=QImage.fromData(data)
            if image.isNull():raise ValueError('Live page is not a decoded image')
            result.update(pageDecoded=True,pageBytes=len(data),width=image.width(),height=image.height(),sha256=hashlib.sha256(data).hexdigest());break
except Exception as exc:result['error']=str(exc)
(ROOT/'work').mkdir(exist_ok=True);(ROOT/'work/live-source-probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
