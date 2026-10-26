import os,sys,unittest,tempfile,time,json,threading
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'));sys.path.insert(0,str(ROOT/'tests'))
from PySide6.QtWidgets import QApplication
APP=QApplication.instance() or QApplication([])
import online_core as core
from reader import Library,Book
from fixture_server import Fixture

class OnlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.server=Fixture().start()
    @classmethod
    def tearDownClass(cls):cls.server.close()
    def setUp(self):
        self.server.at_home_prefix='';self.server.expired_prefix=''
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.root=Path(self.temp.name);self.library=Library(self.root/'data/library.json');self.service=core.OnlineService(self.root,self.library);core.SERVICE=self.service
        self.source={'id':'fixture','name':'本地合成测试','type':'catalog','base_url':self.server.url+'/catalog.json','enabled':True};self.service.sources.put(self.source);self.provider=self.service.provider('fixture')
    def tearDown(self):self.temp.cleanup()
    def add(self):
        books,_=self.provider.search('雪色',1);entry=core.merge_entry(self.source,books[0],self.provider.chapters(books[0]['id']));self.library.data['books'].append(entry);self.library.save();return entry
    def test_builtin_sources_merge_once_and_keep_user_preferences(self):
        path=self.root/'preset-test.json'
        old={'version':1,'sources':[{'id':'mangadex-zh','name':'My name','type':'mangadex','base_url':'https://api.mangadex.org','enabled':False,'token':'keep'}],'cache_roots':['D:/chosen']}
        core.atomic_json(path,old);s=core.Sources(path)
        self.assertEqual({x['type'] for x in s.all},{'mangadex','manhuagui','mangapill','goda','comicabc','mangakatana'})
        self.assertEqual(s.all[0]['name'],'My name');self.assertFalse(s.all[0]['enabled']);self.assertEqual(s.all[0]['token'],'keep');self.assertEqual(s.data['cache_roots'],['D:/chosen'])
        s.all.pop();s.save();self.assertEqual(len(core.Sources(path).all),5)
    def test_html_provider_protocols_and_public_chapters_only(self):
        for kind,bid in [('mangapill','/manga/7/snow'),('manhuagui','/comic/7/')]:
            p=core.Provider(dict(self.source,type=kind,base_url=self.server.url));rows,more=p.search('snow')
            self.assertEqual(len(rows),1);self.assertTrue(more);self.assertIn('&',rows[0]['title']);self.assertEqual(rows[0]['id'],bid)
            ch=p.chapters(bid);self.assertEqual(len(ch),2);self.assertIn('1',ch[0]['title'])
            pages=p.pages(bid,ch[0]);self.assertEqual(len(pages),2)
            if kind=='mangapill':self.assertFalse(pages[0].startswith('https://ads'));self.assertTrue(p.http.read(pages[0]).startswith(b'\x89PNG'))
            else:self.assertIn('/synthetic/01.webp?e=123&m=test',pages[0])
            self.assertEqual(self.server.requests[-1][1].get('Referer'),self.server.url+'/')
    def test_bounded_literal_unpacking_and_lz_known_vectors(self):
        from source_html import lz_base64,unpack_images
        from html_fixtures import packed_manifest
        self.assertEqual(lz_base64('BIUwNmD2AEDukCcwBMg='),'Hello world')
        compressed="x}('"+'{"files":["0.webp"],"path":"/test/"}'+"',36,1,'BIUwNmD2Q==='['split']('|'),0,{})"
        self.assertEqual(unpack_images(compressed)['files'],['Hello.webp'])
        self.assertEqual(unpack_images(packed_manifest())['files'],['01.webp','02.webp'])
        for raw in ["eval(fetch('https://invalid'))", "x}('payload',999,1,'a')"]:
            with self.assertRaises(ValueError):unpack_images(raw)
        with self.assertRaises(ValueError):lz_base64('A')

    def test_unicode_image_urls_are_encoded_once_and_renderable(self):
        raw=self.server.url+'/unicode/水星 完全版/%E7%AC%AC01页.png?签名=a%2Fb&name=标题'
        url=core.checked_url(raw);self.assertTrue(url.isascii());self.assertIn('%20',url);self.assertIn('%E7%AC%AC01',url);self.assertNotIn('%25E7',url)
        self.assertEqual(core.checked_url(url),url);data=self.provider.http.read(raw)
        from PySide6.QtGui import QImage
        self.assertFalse(QImage.fromData(data).isNull());self.assertIn('%E6%B0%B4',self.server.requests[-1][0])
        self.assertEqual(core.checked_url('https://例子.测试/漫画'),'https://xn--fsqu00a.xn--0zwm56d/%E6%BC%AB%E7%94%BB')

    def test_memory_reopen_reuses_manifest_and_page_without_network(self):
        e=self.add();book=Book(e['volumes'][0]['path']);book.render(0);book.close();before=len(self.server.requests)
        again=Book(e['volumes'][0]['path']);again.render(0);self.assertEqual(len(self.server.requests),before);again.close();self.assertFalse(list(self.root.rglob('*.img')))
    def test_page_loads_coalesce_without_blocking_other_page(self):
        e=self.add();book=Book(e['volumes'][0]['path']);p=book.provider;original=p.http.read;started=threading.Event();release=threading.Event();calls=[];results=[]
        def slow(url,limit=core.PAGE_LIMIT):
            calls.append(url)
            if url.endswith('/1.png'):started.set();release.wait(3)
            return original(url,limit)
        p.http.read=slow
        threads=[threading.Thread(target=lambda:results.append(book.render(0))) for _ in range(2)]
        for t in threads:t.start()
        self.assertTrue(started.wait(1));self.assertFalse(book.render(1).isNull());release.set()
        for t in threads:t.join(4)
        self.assertEqual(len(results),2);self.assertEqual(sum(u.endswith('/1.png') for u in calls),1);book.close()
    def test_quality_presets_original_dimensions_and_memory_budgets(self):
        from online_memory import decode_page,quality_profile,MemoryLru
        from PySide6.QtGui import QImage,QColor
        from PySide6.QtCore import QBuffer,QIODevice
        image=QImage(2400,3600,QImage.Format.Format_RGB32);image.fill(QColor('#dfcdeb'));out=QBuffer();out.open(QIODevice.OpenModeFlag.WriteOnly);image.save(out,'PNG');data=bytes(out.data())
        for quality,edge in [('low',1280),('smooth',2000),('original',3600)]:
            result,packed=decode_page(data,quality);self.assertEqual(max(result.width(),result.height()),edge)
            if quality=='original':self.assertIsNone(packed);self.assertEqual(result.pixelColor(0,0).name(),'#dfcdeb')
            else:self.assertTrue(packed.startswith(b'\xff\xd8'))
        self.assertEqual(quality_profile('smooth',5*1024*1024,1),(1600,78))
        cache=MemoryLru(10);cache.put('a',b'a'*8,8);cache.put('b',b'b'*8,8);self.assertLessEqual(cache.bytes,10);self.assertIsNone(cache.get('a'));cache.put('big',b'x'*11,11);self.assertIsNone(cache.get('big'))
    def test_native_prefetch_toggle_and_reopen_warm_page(self):
        from app import Window
        e=self.add();self.library.data['settings']['online_preload']=False;w=Window(self.library,self.root);c=w.online_controller
        try:
            w.open_entry(e);self.wait_ui(lambda:w.book is not None and bool(e.get('online_cover')));before=len(self.server.requests);self.wait_ui(lambda:True);APP.processEvents();self.assertIsNone(c.prefetch_job)
            self.library.data['settings']['online_preload']=True;c.warm();self.wait_ui(lambda:all(w.book.ready(i) for i in (1,2)));pending=c.prefetch_job;self.library.data['settings']['online_preload']=False;c.warm();pending.result(3);before=len(self.server.requests);w.go(1,False);self.assertEqual(w.page,1);self.assertEqual(len(self.server.requests),before)
        finally:w.close();APP.processEvents()

    def test_original_uses_upstream_original_and_bad_responses_do_not_poison_ram(self):
        self.server.md_original=True
        try:
            s=dict(self.source,type='mangadex',base_url=self.server.url);ch={'id':'chapter-1'}
            original=core.Provider(dict(s,_quality='original')).pages('demo',ch);saver=core.Provider(dict(s,_quality='smooth')).pages('demo',ch)
            self.assertIn('/data/',original[0]);self.assertIn('/data-saver/',saver[0])
        finally:self.server.md_original=False
        e=self.add();book=Book(e['volumes'][0]['path']);p=book.provider;fetch=p.http.read;calls=[0]
        def flaky(url,limit=core.PAGE_LIMIT):
            calls[0]+=1
            return b'<html>temporary error</html>' if calls[0]==1 else fetch(url,limit)
        p.http.read=flaky
        with self.assertRaises(core.OnlineError):book.render(0)
        self.assertFalse(book.render(0).isNull());self.assertEqual(calls[0],2);book.close()

    def test_01_search_and_pagination(self):
        rows,more=self.provider.search('雪色');self.assertEqual(len(rows),1);self.assertFalse(more);self.assertEqual(self.provider.search('missing')[0],[])
    def test_02_online_render_never_creates_page_disk_cache(self):
        e=self.add();book=Book(e['volumes'][0]['path']);self.assertEqual(len(book),4);self.assertFalse(book.render(0).isNull());self.assertEqual(list(self.root.rglob('*.img')),[]);self.assertFalse((self.root/'cache').exists());book.close()
    def test_03_all_provider_api_contracts(self):
        for kind in ('mangadex','komga','suwayomi'):
            with self.subTest(kind=kind):
                s=dict(self.source,type=kind,base_url=self.server.url,source_id='1234567890123456789');p=core.Provider(s);rows,more=p.search('雪色');self.assertEqual(rows[0]['id'],'demo');self.assertFalse(more);chapters=p.chapters('demo');self.assertEqual(len(chapters),1);urls=p.pages('demo',chapters[0]);self.assertEqual(len(urls),4);self.assertTrue(p.http.read(urls[0]).startswith(b'\x89PNG'))
    def test_04_download_requires_explicit_directory(self):
        e=self.add()
        with self.assertRaisesRegex(core.OnlineError,'先选择'):self.service.cache.download(e['volumes'][0],self.provider)
    def test_05_download_and_offline_without_source(self):
        e=self.add();v=e['volumes'][0];self.service.sources.set_cache_root(self.root/'downloads');self.service.cache.download(v,self.provider);self.service.sources.all.clear();self.service.sources.save();book=Book(v['path']);self.assertTrue(book.offline);self.assertFalse(book.render(3).isNull());self.assertEqual(len(book),4);book.close()
    def test_06_resume_completed_pages(self):
        e=self.add();v=e['volumes'][0];self.service.sources.set_cache_root(self.root/'downloads');cancel=threading.Event()
        def tick(n,total):
            if n==2:cancel.set()
        with self.assertRaises(core.Cancelled):self.service.cache.download(v,self.provider,cancel,tick)
        self.assertIsNone(self.service.cache.manifest(v));before=len([u for u,h in self.server.requests if u.startswith('/page/')]);self.service.cache.download(v,self.provider);after=len([u for u,h in self.server.requests if u.startswith('/page/')]);self.assertEqual(after-before,2)
    def test_07_corruption_is_detected_and_repaired(self):
        e=self.add();v=e['volumes'][0];self.service.sources.set_cache_root(self.root/'downloads');folder=self.service.cache.download(v,self.provider);(folder/'000001.img').write_bytes(b'broken');book=Book(v['path'])
        with self.assertRaisesRegex(core.OnlineError,'校验'):book.render(0)
        self.service.cache.download(v,self.provider);book=Book(v['path']);self.assertFalse(book.render(0).isNull());book.close()
    def test_08_refresh_retains_progress_status_and_removed_chapters(self):
        e=self.add();old=e['volumes'][0];old.update(page=3,reading_seconds=12,reading_status='已读');e['reading_status']='自定义';core.merge_entry(self.source,{'id':'demo','title':'新书名'},[{'id':'chapter-2','title':'第二话更新'}],e);kept=next(v for v in e['volumes'] if v['path']==old['path']);self.assertIs(old,kept);self.assertEqual(kept['page'],3);self.assertEqual(kept['reading_status'],'已读');self.assertEqual(e['reading_status'],'自定义');self.assertEqual(len(e['volumes']),2)
    def test_09_switch_directory_keeps_old_offline_chapter(self):
        e=self.add();v=e['volumes'][0];self.service.sources.set_cache_root(self.root/'one');folder=self.service.cache.download(v,self.provider);self.service.sources.set_cache_root(self.root/'two');self.assertEqual(self.service.cache.manifest(v)[0],folder)
    def test_10_removal_from_library_does_not_delete_downloads(self):
        e=self.add();v=e['volumes'][0];self.service.sources.set_cache_root(self.root/'cache');folder=self.service.cache.download(v,self.provider);self.library.data['books'].remove(e);self.library.save();self.assertTrue((folder/'000001.img').exists())
    def test_11_explicit_cache_cleanup_preserves_library_and_user_files(self):
        e=self.add();v=e['volumes'][0];root=self.service.sources.set_cache_root(self.root/'cache');self.service.cache.download(v,self.provider);original=root.parent/'original.png';original.write_bytes(b'original');self.service.cache.remove(v);self.assertEqual(len(self.library.data['books']),1);self.assertEqual(original.read_bytes(),b'original');self.assertIsNone(self.service.cache.manifest(v))
    def test_12_import_batch_validates_before_mutation_and_strips_secrets(self):
        before=len(self.service.sources.all)
        with self.assertRaises(core.OnlineError):self.service.sources.import_configs({'sources':[dict(self.source,id='new'),{'type':'script','base_url':'file:///x'}]})
        self.assertEqual(len(self.service.sources.all),before);self.service.sources.import_configs({'sources':[dict(self.source,id='new',token='secret',password='secret')]});s=self.service.sources.get('new');self.assertNotIn('token',s);self.assertNotIn('password',s)
    def test_13_invalid_source_schemes_and_url_credentials(self):
        for u in ('file:///x','javascript:alert(1)','https://user:password@example.com'):
            with self.assertRaises(core.OnlineError):core.checked_url(u)
    def test_14_unmarked_cache_directory_is_not_adopted(self):
        root=self.root/'cache/yukina-online-downloads';root.mkdir(parents=True);(root/'book').write_bytes(b'keep')
        with self.assertRaises(core.OnlineError):self.service.sources.set_cache_root(root.parent)
        self.assertEqual((root/'book').read_bytes(),b'keep')
    def test_15_cross_origin_redirect_does_not_forward_authentication(self):
        other=Fixture().start()
        try:
            self.server.redirect=other.url+'/headers';s=dict(self.source,base_url=self.server.url,username='demo',password='secret',api_key='secret');headers=core.Http(s).json(self.server.url+'/redirect');self.assertNotIn('Authorization',headers);self.assertNotIn('X-Api-Key',headers);self.assertNotIn('X-api-key',headers)
        finally:other.close()
    def test_16_cached_manifest_rejects_traversal(self):
        e=self.add();v=e['volumes'][0];self.service.sources.set_cache_root(self.root/'cache');folder=self.service.cache.download(v,self.provider);manifest=json.loads((folder/'chapter.json').read_text('utf-8'));manifest['pages'][0]['file']='../../user-book';core.atomic_json(folder/'chapter.json',manifest);self.assertIsNone(self.service.cache.manifest(v))
    def test_17_restart_preserves_sources_book_progress_and_offline(self):
        e=self.add();v=e['volumes'][0];v['page']=2;v['reading_status']='已读';self.service.sources.set_cache_root(self.root/'cache');self.service.cache.download(v,self.provider);self.library.save();lib=Library(self.library.path);service=core.OnlineService(self.root,lib);core.SERVICE=service;book=Book(v['path']);self.assertTrue(book.offline);self.assertEqual(lib.data['books'][0]['volumes'][0]['page'],2);self.assertFalse(book.render(2).isNull());book.close()
    def test_18_source_toggle_keeps_offline_reading(self):
        e=self.add();v=e['volumes'][0];self.service.sources.set_cache_root(self.root/'cache');self.service.cache.download(v,self.provider);self.service.sources.get('fixture')['enabled']=False;self.service.sources.save();book=Book(v['path']);self.assertTrue(book.offline);book.close()
    def test_19_window_discovery_add_async_turn_and_independent_storage(self):
        from app import Window
        w=Window(self.library,self.root);c=w.online_controller;c.service.sources.put(self.source);
        for src in c.service.sources.all:src['enabled']=src['id']=='fixture'
        c.refresh_sources();c.show();c.query.setText('雪色');c.search()
        def wait(fn,timeout=12):
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                APP.processEvents();time.sleep(.015)
                if fn():return
            self.fail('UI async operation timed out')
        try:
            wait(lambda:c.results.count()==1);c.results.setCurrentRow(0);c.add_selected();wait(lambda:len(w.library.data['books'])==1);e=w.library.data['books'][0];w.open_entry(e);wait(lambda:w.book is not None);self.assertTrue(w.book.online);self.assertEqual(w.page,0);start=time.monotonic();w.go(2,False);self.assertLess(time.monotonic()-start,.1);wait(lambda:w.page==2);self.assertEqual(w.entry['page'],2);self.assertFalse((self.root/'cache/yukina-online-downloads').exists());self.assertIn('在线版',w.windowTitle());w.show_library(e);self.assertNotIn('文件缺失',w.shelf.volume_list.topLevelItem(0).text(2));w.show();APP.processEvents();w.grab().save(str(ROOT/'work/desktop-library.png'));c.show();w.grab().save(str(ROOT/'work/desktop-discovery.png'))
        finally:w.close();APP.processEvents()
    def wait_ui(self,fn,timeout=18):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            APP.processEvents();time.sleep(.015)
            if fn():return
        self.fail('UI completion timed out')
    def test_20_select_chapter_first_page_cover_without_page_cache(self):
        from app import Window
        from PySide6.QtGui import QImage
        e=self.add();w=Window(self.library,self.root);c=w.online_controller
        try:
            c.set_cover(e,e['volumes'][1]['path']);self.wait_ui(lambda:bool(e.get('online_cover')));image=QImage(e['online_cover']);self.assertEqual(image.pixelColor(0,0).name(),'#dfcdeb');self.assertLessEqual(image.width(),420);self.assertLessEqual(image.height(),600);self.assertEqual(e['cover_volume'],e['volumes'][1]['path']);self.assertEqual(list(self.root.rglob('*.img')),[])
        finally:w.close();APP.processEvents()
    def test_21_persistent_queue_pause_then_resume_after_window_restart(self):
        from app import Window
        e=self.add();w=Window(self.library,self.root);c=w.online_controller;c.service.sources.set_cache_root(self.root/'queue-cache')
        def pause(title,n,total):
            if n==1:c.cancel_downloads()
        c.jobs.progress.connect(pause)
        try:
            c.download(e['volumes']);self.wait_ui(lambda:not c.download_active);queue=json.loads((self.root/'data/online-download-queue.json').read_text('utf-8'));self.assertTrue(queue)
        finally:w.close();APP.processEvents()
        restored=Library(self.library.path);w2=Window(restored,self.root);c2=w2.online_controller
        try:
            c2.resume_downloads(restored.data['books'][0]);self.wait_ui(lambda:not c2.download_active);self.assertEqual(json.loads((self.root/'data/online-download-queue.json').read_text('utf-8')),[]);self.assertTrue(all(c2.service.cache.manifest(v) for v in restored.data['books'][0]['volumes']))
        finally:w2.close();APP.processEvents()
    def test_22_mangadex_delivery_token_refreshes_during_reading(self):
        source=dict(self.source,type='mangadex',base_url=self.server.url,language='zh');self.service.sources.put(source);provider=self.service.provider('fixture');self.server.at_home_prefix='/token-v1';chapters=provider.chapters('demo');e=core.merge_entry(source,{'id':'demo','title':'MD 合成测试'},chapters);self.library.data['books'].append(e);book=Book(e['volumes'][0]['path']);self.server.at_home_prefix='/token-v2';self.server.expired_prefix='/token-v1/'
        self.assertFalse(book.render(0).isNull());self.assertIn('/token-v2/',book.urls[0]);self.assertEqual(list(self.root.rglob('*.img')),[]);book.close()
    def test_23_mangadex_resume_reuses_pages_after_cdn_token_rotation(self):
        source=dict(self.source,type='mangadex',base_url=self.server.url,language='zh');self.service.sources.put(source);provider=self.service.provider('fixture');self.server.at_home_prefix='/token-v1';e=core.merge_entry(source,{'id':'demo','title':'MD 合成测试'},provider.chapters('demo'));self.library.data['books'].append(e);v=e['volumes'][0];self.service.sources.set_cache_root(self.root/'cache');cancel=threading.Event()
        def pause(n,total):
            if n==2:cancel.set()
        with self.assertRaises(core.Cancelled):self.service.cache.download(v,provider,cancel,pause)
        self.server.at_home_prefix='/token-v2';self.server.expired_prefix='/token-v1/';before=len([u for u,h in self.server.requests if '/data-saver/' in u]);self.service.cache.download(v,provider);after=len([u for u,h in self.server.requests if '/data-saver/' in u]);self.assertEqual(after-before,2);self.assertIsNotNone(self.service.cache.manifest(v))
    def test_24_cache_inventory_can_clean_removed_book_without_touching_originals(self):
        e=self.add();v=e['volumes'][0];self.service.sources.set_cache_root(self.root/'cache');self.service.cache.download(v,self.provider);self.library.data['books'].remove(e);original=self.root/'cache'/'my-original.cbz';original.write_bytes(b'original');inventory=self.service.cache.all_volumes();self.assertEqual(len(inventory),1);self.assertEqual(inventory[0]['path'],v['path']);self.service.cache.remove(inventory[0]);self.assertIsNone(self.service.cache.manifest(v));self.assertEqual(original.read_bytes(),b'original')
    def test_25_navigation_cancels_pending_open_without_late_reader_jump(self):
        from app import Window
        e=self.add();w=Window(self.library,self.root);c=w.online_controller;p=c.service.provider('fixture','smooth');original=p.http.read;started=threading.Event();release=threading.Event();finished=threading.Event()
        def delayed(url,limit=core.PAGE_LIMIT):started.set();release.wait(2);data=original(url,limit);finished.set();return data
        p.http.read=delayed
        try:
            w.open_entry(e);self.assertTrue(started.wait(2));w.show_library();release.set();self.wait_ui(finished.is_set);APP.processEvents();time.sleep(.05);APP.processEvents();self.assertIsNone(w.book);self.assertIs(w.pages.currentWidget(),w.shelf)
        finally:release.set();w.close();APP.processEvents()
    def test_26_close_does_not_wait_for_a_blocked_network_read(self):
        e=self.add();book=Book(e['volumes'][0]['path']);p=book.provider;original=p.http.read;started=threading.Event();release=threading.Event();errors=[]
        def delayed(url,limit=core.PAGE_LIMIT):started.set();release.wait(2);return original(url,limit)
        p.http.read=delayed
        def work():
            try:book.render(0)
            except core.OnlineError as e:errors.append(str(e))
        thread=threading.Thread(target=work);thread.start();self.assertTrue(started.wait(2));before=time.monotonic();book.close();self.assertLess(time.monotonic()-before,.1);release.set();thread.join(3);self.assertTrue(errors);self.assertEqual(len(book.images),0)

if __name__=='__main__':
    (ROOT/'work').mkdir(exist_ok=True);unittest.main(verbosity=2)
