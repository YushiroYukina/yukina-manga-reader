"""Native UI acceptance for scoped downloads and incremental source mixing."""
import os,sys,json,time,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'));sys.path.insert(0,str(ROOT/'tests'))
from PySide6.QtWidgets import QApplication,QPushButton,QComboBox,QDialogButtonBox,QMessageBox
from PySide6.QtCore import Qt,QTimer
from PySide6.QtTest import QTest
APP=QApplication.instance() or QApplication([])
from app import Window
from reader import Library
from online_ui import DownloadsDialog,SourcesDialog
import online_core as core
from fixture_server import Fixture

class WorkflowTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.fixture=Fixture().start()
 @classmethod
 def tearDownClass(cls):cls.fixture.close()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.root=Path(self.tmp.name);self.lib=Library(self.root/'data/library.json');self.w=Window(self.lib,self.root);self.c=self.w.online_controller;self.dialogs=[]
  for source in self.c.service.sources.all:source['enabled']=False
  self.sources=[]
  for sid in ('first','second'):
   source={'id':sid,'name':'书源 '+sid,'type':'catalog','base_url':self.fixture.url+'/catalog.json','connection':'direct','enabled':True};self.c.service.sources.put(source);self.sources.append(source)
  self.c.refresh_sources()
 def tearDown(self):
  for dialog in self.dialogs:
   if isinstance(dialog,DownloadsDialog):dialog.cleanup()
   dialog.close()
  self.w.close();APP.processEvents();self.tmp.cleanup()
 def wait(self,predicate,seconds=12):
  until=time.monotonic()+seconds
  while time.monotonic()<until:
   APP.processEvents()
   if predicate():return
   QTest.qWait(15)
  self.fail('UI operation timed out')
 def book(self,index):
  source=self.sources[index];provider=core.Provider(source);rows,_=provider.search('雪色');entry=core.merge_entry(source,dict(rows[0],title='测试书 '+str(index+1)),provider.chapters(rows[0]['id']));self.lib.data['books'].append(entry);self.lib.save();self.w.refresh();return entry
 def cache(self,book,chapter=0):
  if not self.c.service.sources.data.get('cache_roots'):self.c.service.sources.set_cache_root(self.root/'offline')
  provider=self.c.service.provider(book['online']['source_id']);self.c.service.cache.download(book['volumes'][chapter],provider,book_title=book['title'])
 def dialog(self,owner=None,inventory_only=False):
  d=DownloadsDialog(self.c,owner,inventory_only);self.dialogs.append(d);return d
 def test_mixed_search_emits_fast_results_before_slow_source_and_preserves_selection(self):
  release=threading.Event()
  def search(provider,term,page=1):
   if provider.s['id']=='second':release.wait(4)
   return [{'id':'same','title':provider.s['name']+' '+term}],provider.s['id']=='second'
  try:
   with patch.object(core.Provider,'search',search):
    self.c.query.setText('雪');self.c.search();self.wait(lambda:len(self.c.rows)==1);self.assertEqual(self.c.rows[0]['source_id'],'first');self.assertIn('其余来源',self.c.note.text());self.c.results.setCurrentRow(0);release.set();self.wait(lambda:not self.c.search_pending);self.assertEqual(len(self.c.rows),2);self.assertEqual(self.c.results.currentItem().data(Qt.ItemDataRole.UserRole)['source_id'],'first');self.assertTrue(self.c.next.isEnabled())
  finally:release.set()
 def test_failed_source_does_not_discard_success_and_disabled_source_is_not_queried(self):
  calls=[]
  def search(provider,term,page=1):
   calls.append(provider.s['id'])
   if provider.s['id']=='second':raise core.OnlineError('测试失败')
   return [{'id':'a','title':'可用作品'}],False
  with patch.object(core.Provider,'search',search):
   self.c.search();self.wait(lambda:not self.c.search_pending);self.assertEqual(len(self.c.rows),1);self.assertIn('书源 second：测试失败',self.c.note.text())
   self.sources[1]['enabled']=False;self.c.service.sources.put(self.sources[1]);self.c.refresh_sources();calls.clear();self.c.search();self.wait(lambda:not self.c.search_pending);self.assertEqual(calls,['first'])
 def test_old_query_cannot_overwrite_new_query(self):
  release=threading.Event();started=threading.Event()
  def search(provider,term,page=1):
   if term=='旧':started.set();release.wait(4)
   return [{'id':term,'title':term}],False
  try:
   with patch.object(core.Provider,'search',search):
    self.c.query.setText('旧');self.c.search();self.wait(started.is_set);self.c.query.setText('新');self.c.search();self.wait(lambda:len(self.c.rows)==2 and not self.c.search_pending);release.set();QTest.qWait(150);self.assertTrue(all(book['title']=='新' for book in self.c.rows))
  finally:release.set()
 def test_search_is_not_blocked_by_background_cover_tasks(self):
  release=threading.Event()
  try:
   for _ in range(2):self.c.jobs.run(lambda:release.wait(4),lambda *_:None)
   with patch.object(core.Provider,'search',lambda *_:([{'id':'a','title':'立即返回'}],False)):
    self.c.search();self.wait(lambda:len(self.c.rows)==2,seconds=2)
  finally:release.set()
 def test_source_checkbox_persists_and_discovery_has_no_source_selector(self):
  self.assertEqual(self.c.discovery.findChildren(QComboBox),[]);self.assertFalse(hasattr(self.c,'quality_button'))
  dialog=SourcesDialog(self.c);self.dialogs.append(dialog)
  item=next(dialog.list.item(i) for i in range(dialog.list.count()) if dialog.list.item(i).data(Qt.ItemDataRole.UserRole)=='first');item.setCheckState(Qt.CheckState.Unchecked)
  stored=core.Sources(self.c.service.sources.path);self.assertFalse(next(s for s in stored.all if s['id']=='first')['enabled'])
 def test_library_inventory_lists_only_cached_books_and_cannot_start_downloads(self):
  first=self.book(0);self.book(1);self.cache(first);d=self.dialog();self.assertEqual(d.list.count(),1);self.assertFalse(d.allow_download);self.assertIn(first['title'],d.list.item(0).text())
  texts=[b.text() for b in d.findChildren(QPushButton)];self.assertNotIn('下载所选 / 继续',texts);self.assertFalse(any('继续' in t for t in texts))
  with patch.object(self.c,'download') as download:d.download();download.assert_not_called()
 def test_detail_downloads_only_show_owner_and_cleanup_does_not_touch_other_books(self):
  first=self.book(0);second=self.book(1);self.cache(first);self.cache(second);d=self.dialog(first);self.assertEqual(d.list.count(),2);self.assertTrue(all(ch['path'].startswith(first['path']+'/') for record in d.records.values() for ch in record['chapters']))
  with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):d.clear_all()
  self.assertIsNone(self.c.service.cache.manifest(first['volumes'][0]));self.assertIsNotNone(self.c.service.cache.manifest(second['volumes'][0]));self.assertEqual(len(self.lib.data['books']),2)
 def test_inventory_can_manage_removed_books_and_child_view_has_no_download_controls(self):
  first=self.book(0);self.cache(first);self.lib.data['books'].remove(first);d=self.dialog();self.assertEqual(d.list.count(),1);self.assertIn('已移出书库',d.list.item(0).text());d.list.setCurrentRow(0);owner=d.chosen_owner();self.assertEqual(owner['title'],first['title']);child=self.dialog(owner,True);self.assertEqual(child.list.count(),1);self.assertFalse(child.allow_download)
  with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):child.clear_all()
  self.assertEqual(d.list.count(),0)
 def test_book_resume_preserves_other_books_pending_queue(self):
  first=self.book(0);second=self.book(1);self.c.service.sources.set_cache_root(self.root/'offline');a=first['volumes'][0]['path'];b=second['volumes'][0]['path'];queue=self.root/'data/online-download-queue.json';core.atomic_json(queue,[b,a]);self.c.resume_downloads(first);self.wait(lambda:not self.c.download_active)
  self.assertEqual(json.loads(queue.read_text()),[b]);self.assertIsNotNone(self.c.service.cache.manifest(first['volumes'][0]));self.assertIsNone(self.c.service.cache.manifest(second['volumes'][0]))
 def test_partial_download_is_visible_in_global_and_book_management(self):
  first=self.book(0);self.c.service.sources.set_cache_root(self.root/'offline');cancel=threading.Event()
  with self.assertRaises(core.Cancelled):self.c.service.cache.download(first['volumes'][0],self.c.service.provider('first'),cancel,lambda *_:cancel.set(),book_title=first['title'])
  self.assertIsNone(self.c.service.cache.manifest(first['volumes'][0]));inventory=self.dialog();self.assertEqual(inventory.list.count(),1);detail=self.dialog(first);self.assertIn('部分下载',detail.list.item(0).text())
 def test_all_disabled_does_not_start_network_requests(self):
  for source in self.c.service.sources.all:source['enabled']=False
  self.c.refresh_sources()
  with patch.object(core.Provider,'search') as search:self.c.search();search.assert_not_called()
  self.assertIn('启用至少一个',self.c.note.text())
 def test_detail_download_button_opens_only_current_book(self):
  first=self.book(0);self.book(1);self.w.show_library(first);captured=[]
  def dismiss():
   dialog=APP.activeModalWidget();captured.append((dialog.owner['id'],dialog.allow_download,dialog.list.count()));dialog.reject()
  QTimer.singleShot(50,dismiss);self.w.shelf.downloads_btn.click();self.assertEqual(captured,[(first['id'],True,2)])
 def test_detail_entry_and_reading_quality_remain_available_in_immersive_overlay(self):
  first=self.book(0);self.w.show();self.w.show_library(first);self.assertFalse(self.w.shelf.downloads_btn.isHidden());self.w.open_entry(first);self.wait(lambda:self.w.book is not None);self.w.set_immersive(True);QTest.qWait(250);before=self.w.canvas.geometry();self.w.toggle_immersive_controls();self.w.settings_btn.setChecked(True);self.w.toggle_appearance(True);APP.processEvents();self.assertTrue(self.c.reader_quality.isVisible());self.assertEqual(self.w.canvas.geometry(),before)
  captured=[]
  def cancel():
   dialog=APP.activeModalWidget();captured.append(dialog.windowTitle());dialog.reject()
  QTimer.singleShot(50,cancel);self.c.reader_quality.click();self.assertEqual(captured,['在线画质与预加载']);self.assertTrue(self.w.immersive);self.assertEqual(self.w.canvas.geometry(),before)
  self.w.grab().save(str(ROOT/'work/workflow-immersive.png'))
  self.w.exit_immersive();self.w.show_library(first);self.w.grab().save(str(ROOT/'work/workflow-detail.png'))
if __name__=='__main__':unittest.main(verbosity=2)
