import os,sys,json,time,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'desktop'),str(ROOT/'tests')]
from PySide6.QtWidgets import QApplication,QPushButton,QComboBox,QMessageBox
from PySide6.QtCore import QTimer,Qt
APP=QApplication.instance() or QApplication([])
from app import Window
from reader import Library
import online_core as core
from online_downloads import DownloadsDialog
from online_ui import SourcesDialog
from fixture_server import Fixture

class WindowsWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.server=Fixture().start()
    @classmethod
    def tearDownClass(cls):cls.server.close()
    def setUp(self):
        (ROOT/'work').mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.root=Path(self.temp.name);self.library=Library(self.root/'data/library.json');self.w=Window(self.library,self.root);self.w.show();self.c=self.w.online_controller;self.dialogs=[]
        for source in self.c.service.sources.all:source['enabled']=False
        self.sources=[]
        for name in ('A','B','C'):
            s={'id':name,'name':'测试书源 '+name,'type':'catalog','base_url':self.server.url+'/catalog.json','enabled':True};s=self.c.service.sources.put(s);self.sources.append(s)
        self.c.refresh_sources();self.cover=self.root/'local-cover.png';self.cover.write_bytes(self.server.images[1])
    def tearDown(self):
        for d in self.dialogs:d.close()
        self.w.close();APP.processEvents();self.temp.cleanup()
    def wait(self,condition,timeout=15):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            APP.processEvents()
            if condition():return
            time.sleep(.01)
        self.fail('UI operation timed out')
    def book(self,index):
        source=self.sources[index];p=self.c.service.provider(source['id']);books,_=p.search('雪色');e=core.merge_entry(source,dict(books[0],title='书籍 '+source['id']),p.chapters('demo'));e['cover_path']=str(self.cover);self.library.data['books'].append(e);self.library.save();return e
    def dialog(self,owner=None,existing_only=False):
        d=DownloadsDialog(self.c,owner,existing_only);self.dialogs.append(d);d.show();return d
    def test_mixed_search_partial_results_disabled_sources_and_management(self):
        self.sources[2]['enabled']=False
        bad=dict(self.sources[2],id='bad',name='暂时失败的书源',enabled=True,base_url=self.server.url+'/missing');self.c.service.sources.put(bad);self.c.refresh_sources();p=self.c.service.provider('bad');entered=threading.Event();release=threading.Event()
        def delayed(term,page):entered.set();release.wait(4);raise core.OnlineError('合成失败')
        p.search=delayed;self.c.query.setText('雪色');self.c.show();self.c.search()
        try:
            self.wait(lambda:self.c.results.count()==2);self.assertTrue(entered.is_set());self.assertFalse(self.c.search_cache);self.assertEqual({b['source_id'] for b in self.c.rows},{'A','B'});self.assertFalse(self.c.discovery.findChildren(QComboBox));release.set();self.wait(lambda:bool(self.c.search_cache));self.assertIn('暂时失败的书源',self.c.note.text());self.assertIn('合成失败',self.c.note.text())
            manager=SourcesDialog(self.c);self.dialogs.append(manager)
            for i in range(manager.list.count()):
                if manager.list.item(i).data(Qt.ItemDataRole.UserRole)=='A':manager.list.setCurrentRow(i);break
            manager.toggle();self.assertFalse(self.sources[0]['enabled']);self.assertEqual(self.c.results.count(),0)
            self.c.service.sources.all[:]=[s for s in self.c.service.sources.all if s['id']!='bad'];self.c.refresh_sources();self.c.search();self.wait(lambda:bool(self.c.search_cache));self.assertEqual([b['source_id'] for b in self.c.rows],['B'])
        finally:release.set()
    def test_global_inventory_only_and_scoped_detail_entry(self):
        a=self.book(0);b=self.book(1);unused=self.book(2);self.c.service.sources.set_cache_root(self.root/'downloads');self.c.service.cache.download(dict(a['volumes'][0],_book_title=a['title']),self.c.service.provider('A'));self.c.service.cache.download(dict(b['volumes'][0],_book_title=b['title']),self.c.service.provider('B'))
        global_dialog=self.dialog();self.wait(lambda:global_dialog.list.count()==2);self.assertIsNone(global_dialog.download_button);self.assertIsNone(global_dialog.resume_button);self.assertEqual({i.data(Qt.ItemDataRole.UserRole)['title'] for i in [global_dialog.list.item(0),global_dialog.list.item(1)]},{a['title'],b['title']});before=len(self.server.requests);global_dialog.download();self.assertEqual(len(self.server.requests),before)
        scoped=self.dialog(a);self.wait(lambda:scoped.list.count()==2);self.assertIsNotNone(scoped.download_button);self.assertTrue(all(scoped.list.item(i).data(Qt.ItemDataRole.UserRole)['path'].startswith(a['path']+'/') for i in range(scoped.list.count())))
        self.w.show_library(a);captured={};timer=QTimer()
        def inspect():
            for widget in APP.topLevelWidgets():
                if isinstance(widget,DownloadsDialog) and widget not in self.dialogs and widget.isVisible():captured['owner']=widget.owner;widget.reject();timer.stop()
        timer.timeout.connect(inspect);timer.start(20);QTimer.singleShot(3000,timer.stop);self.w.shelf.online_download_btn.click();self.assertIs(captured.get('owner'),a)
        self.w.show_library(unused);self.assertFalse(self.w.shelf.online_download_btn.isHidden())
    def test_resume_and_cleanup_never_cross_book_boundaries(self):
        a=self.book(0);b=self.book(1);self.c.service.sources.set_cache_root(self.root/'downloads');queue=self.root/'data/online-download-queue.json';core.atomic_json(queue,[a['volumes'][0]['path'],b['volumes'][0]['path']]);self.c.resume_downloads(a);self.wait(lambda:not self.c.download_active)
        self.assertTrue(self.c.service.cache.manifest(a['volumes'][0]));self.assertIsNone(self.c.service.cache.manifest(b['volumes'][0]));self.assertEqual(json.loads(queue.read_text('utf-8')),[b['volumes'][0]['path']])
        self.c.download([b['volumes'][0]]);self.wait(lambda:not self.c.download_active);d=self.dialog(a);self.wait(lambda:d.list.count()==2);original=self.cover.read_bytes()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):d.clear_all()
        self.assertIsNone(self.c.service.cache.manifest(a['volumes'][0]));self.assertTrue(self.c.service.cache.manifest(b['volumes'][0]));self.assertEqual(self.cover.read_bytes(),original);self.assertEqual(len(self.library.data['books']),2)
    def test_reading_quality_only_in_reading_menu_and_immersive_overlay(self):
        e=self.book(0);self.w.show_library(e);self.assertFalse(any('画质' in b.text() for b in self.w.shelf.findChildren(QPushButton)));self.assertFalse(any('画质' in b.text() for b in self.c.discovery.findChildren(QPushButton)));self.assertTrue(self.c.reader_quality.isHidden());self.w.open_entry(e);self.wait(lambda:self.w.book is not None);self.assertFalse(self.c.reader_quality.isHidden());self.w.toggle_immersive();self.w.toggle_immersive_controls();self.w.settings_btn.click();self.assertTrue(self.w.immersive);self.assertTrue(self.c.reader_quality.isVisible());self.w.exit_immersive()
    def test_source_decoders_are_bounded_and_login_results_hidden(self):
        from source_comicabc import record_images,ComicabcProvider
        from source_goda import decode_images
        for value in ('bad','J7rwrongnQ'):
            with self.assertRaises(ValueError):decode_images(value)
        with self.assertRaises(ValueError):record_images('eval(unknown())','1')
        p=ComicabcProvider({'base_url':'https://example.invalid'},None);p.get=lambda _: '<a class="comicpic_col6" href="/html/1.html">不可直接阅读 (登入觀看)</a><a class="comicpic_col6" href="/html/2.html">公开作品</a>'
        rows,_=p.search('test',1);self.assertEqual([r['id'] for r in rows],['/html/2.html'])

if __name__=='__main__':unittest.main(verbosity=2)
