"""Synthetic public metadata; no copied manga pages or remote script execution."""
import sys,unittest,json,os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'));sys.path.insert(0,str(ROOT/'tests'))
from PySide6.QtWidgets import QApplication
APP=QApplication.instance() or QApplication([])
import online_core as core
from source_dm5 import Dm5Provider
from fixture_server import Fixture

BASE='https://dm5.invalid'
SEARCH='<a href="/manhua-list/">导航</a><h2 class="title"><a href="/manhua-snow-handbook/">雪日手册</a></h2><p class="title"><a href="/manhua-snow/">雪日</a></p><p class="title"><a href="/manhua-other/">无关作品</a></p><p class="title"><a href="https://ads.invalid/manhua-snow/">AD</a></p><a href="/search?title=snow&page=2">Next</a>'
CHAPTERS='<a href="/m999/">广告</a><div id="chapterlistload"><ul id="detail-list-select-1"><li><a href="/m20/">第2话</a></li><li><a href="/m10/">第1话</a></li><li><a href="/m30/">付费<span class="detail-lock"></span></a></li></ul><ul id="detail-list-select-3"><li><a href="/m40/">番外</a></li></ul></div>'
VIEW='var DM5_CID=10;var DM5_MID=1;var DM5_IMAGE_COUNT=90;var DM5_VIEWSIGN="token";var DM5_VIEWSIGN_DT="2026-10-26 00:00:00";'
def packed():
 payload='var pix="https://cdn.invalid/comic";var pvalue=["/1.jpg","/2.jpg"];for(var i=0;i<pvalue.length;i++){pvalue[i]=pix+pvalue[i]+\'?cid=10&key=token\'}'
 return 'eval(function(p,a,c,k,e,d){throw new Error("never execute");}('+repr(payload)+",36,0,''.split('|'),0,{}))"
class FakeHttp:
 def __init__(self):self.requests=[];self.view=VIEW;self.script=packed()
 def read(self,url,*args):
  self.requests.append(url)
  if 'chapterfun.ashx' in url:return self.script.encode()
  if '/search?' in url:return SEARCH.encode()
  if '/manhua-snow/' in url:return CHAPTERS.encode()
  if '/m10/' in url:return self.view.encode()
  if url.startswith('https://cdn.invalid'):return getattr(self,'image',b'image bytes')
  raise AssertionError(url)
class Dm5Tests(unittest.TestCase):
 def setUp(self):self.http=FakeHttp();self.source={'id':'test','name':'Test','type':'dm5','base_url':BASE,'connection':'direct'};self.p=Dm5Provider(self.source,self.http)
 def test_search_keeps_matching_titles_and_does_not_relabel_handbook(self):
  rows,more=self.p.search('雪日',1);self.assertEqual([b['title'] for b in rows],['雪日','雪日手册']);self.assertTrue(more)
 def test_chapters_keep_primary_group_first_and_skip_locked_and_unrelated(self):
  self.assertEqual([c['id'] for c in self.p.chapters('/manhua-snow/')],['/m10/','/m20/','/m40/'])
 def test_large_chapter_does_not_fetch_each_resolver_until_requested(self):
  urls=self.p.pages({'id':'/m10/'});self.assertEqual(len(urls),90);self.assertEqual(len(self.http.requests),1)
  p=core.Provider(self.source);p.http=self.http;self.assertEqual(p.page_bytes('test',{'id':'/m10/'},1,urls),b'image bytes');self.assertEqual(len(self.http.requests),3)
  self.assertIn('page=2',self.http.requests[1]);self.assertTrue(self.http.requests[2].endswith('?cid=10&key=token'))
 def test_resolver_uses_literals_only(self):
  u=self.p.pages({'id':'/m10/'})[0];self.assertEqual(self.p.image_url(u),'https://cdn.invalid/comic/1.jpg?cid=10&key=token')
 def test_cross_origin_or_nonchapter_resolver_rejected(self):
  for u in ('https://ads.invalid/m10/chapterfun.ashx',BASE+'/account/chapterfun.ashx'):
   with self.assertRaises(ValueError):self.p.image_url(u)
  self.assertEqual(self.http.requests,[])
 def test_missing_public_token_and_invalid_counts_fail(self):
  self.http.view=VIEW.replace('var DM5_VIEWSIGN="token";','')
  with self.assertRaises(ValueError):self.p.pages({'id':'/m10/'})
  self.http.view=VIEW.replace('COUNT=90','COUNT=10001')
  with self.assertRaises(ValueError):self.p.pages({'id':'/m10/'})
 def test_arbitrary_remote_script_is_not_accepted(self):
  self.http.script='fetch("https://attacker.invalid/execute")'
  with self.assertRaises(ValueError):self.p.image_url(BASE+'/m10/chapterfun.ashx')
 def test_http_sets_chapter_referer_for_resolver_and_image(self):
  f=Fixture().start()
  try:
   h=core.Http(dict(self.source,base_url=f.url));headers=h.json(f.url+'/headers?cid=10');self.assertEqual(headers['Referer'],f.url+'/m10/')
   h.read(f.url+'/page/1.png?cid=20');self.assertEqual(f.requests[-1][1]['Referer'],f.url+'/m20/')
  finally:f.close()
 def test_download_identity_ignores_expiring_signature_but_keeps_page(self):
  first=BASE+'/m10/chapterfun.ashx?page=1&_dt=old&_sign=one'
  fresh=BASE+'/m10/chapterfun.ashx?page=1&_dt=new&_sign=two'
  self.assertEqual(core.page_identity(self.source,first),core.page_identity(self.source,fresh))
  self.assertNotEqual(core.page_identity(self.source,first),core.page_identity(self.source,fresh.replace('page=1','page=2')))
 def test_explicit_download_reuses_verified_pages_after_token_changes(self):
  import tempfile
  from fixture_server import image
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);sources=core.Sources(root/'sources.json');sources.set_cache_root(root/'chosen');cache=core.Cache(sources)
   self.http.view=VIEW.replace('COUNT=90','COUNT=2');self.http.image=image(1);provider=core.Provider(self.source);provider.http=self.http
   volume=core.merge_entry(self.source,{'id':'snow','title':'雪日'},[{'id':'/m10/','title':'第一话'}])['volumes'][0]
   folder=cache.download(volume,provider);self.assertEqual(len(list(folder.glob('*.img'))),2)
   before=len(self.http.requests);self.http.view=self.http.view.replace('00:00:00','01:00:00');cache.download(volume,provider)
   self.assertEqual(len(self.http.requests)-before,1);self.assertTrue(cache.manifest(volume)[1]['complete'])

if __name__=='__main__':unittest.main(verbosity=2)
