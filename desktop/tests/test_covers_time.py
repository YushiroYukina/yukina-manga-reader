import hashlib
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from reader import Library
from reading_time import ReadingTracker,duration
from thumbnail_worker import render_thumbnail
from cover_cache import ThumbnailCache,cover_source
from app import Window
from test_reader import APP,fixtures,temporary_directory

class CoverTimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=temporary_directory(); self.root=Path(self.temp.name).resolve()
        self.paths=fixtures(self.root); self.library=Library(self.root/'data'/'library.json'); self.windows=[]; self.engines=[]
    def tearDown(self):
        for w in self.windows: w.close()
        for engine in self.engines: engine.stop()
        self.temp.cleanup()

    def wait_cover(self,engine,entry):
        for _ in range(150):
            path=engine.request(entry)
            if path: return path
            QTest.qWait(30)
        self.fail(str(engine.failed))

    def test_first_page_each_format_and_source_integrity(self):
        root=self.root/'cache'/'covers'
        for i,path in enumerate(self.paths):
            before=hashlib.sha256(path.read_bytes()).digest()
            target=root/f'{i}.png'; render_thumbnail(path,'book',target,root)
            image=QImage(str(target)); self.assertEqual((image.width(),image.height()),(420,600))
            self.assertEqual(image.pixelColor(210,300).name(),'#ff0000')
            self.assertEqual(before,hashlib.sha256(path.read_bytes()).digest())

    def test_async_cache_reuse_invalidation_clear_and_non_c_location(self):
        entry=self.library.add([self.paths[1]])[0]
        engine=ThumbnailCache(self.root); self.engines.append(engine)
        target=self.wait_cover(engine,entry); self.assertEqual(target.parent,self.root/'cache'/'covers')
        self.assertNotEqual(target.drive.casefold(),'c:')
        self.assertEqual(engine.process.processEnvironment().value('TEMP'),str(self.root/'cache'/'worker-temp'))
        stamp=target.stat().st_mtime_ns
        engine.stop(); engine.stopping=False
        self.assertEqual(engine.request(entry),target); self.assertEqual(target.stat().st_mtime_ns,stamp)
        source=self.paths[1]; source.touch(); changed=self.wait_cover(engine,entry)
        self.assertNotEqual(target,changed)
        marker=engine.root/'keep.txt'; marker.write_text('keep')
        engine.clear(); self.assertFalse(list(engine.root.glob('*.png'))); self.assertTrue(marker.exists())
        forbidden=self.root/'outside.png'
        with self.assertRaises(ValueError): render_thumbnail(source,'book',forbidden,engine.root)
        self.assertFalse(forbidden.exists())
        c_root=Path('C:/migi-cache-forbidden-test')
        existed=c_root.exists(); denied=ThumbnailCache(c_root); self.engines.append(denied)
        self.assertFalse(denied.enabled); self.assertIsNone(denied.request(entry)); self.assertEqual(c_root.exists(),existed)
        with self.assertRaises(ValueError): render_thumbnail(source,'book',c_root/'cache'/'covers'/'x.png',c_root/'cache'/'covers')

    def test_selected_volume_cover_survives_reload_and_relocation(self):
        folder=self.root/'series'; folder.mkdir()
        shutil.copyfile(self.paths[1],folder/'卷1.epub'); shutil.copyfile(self.paths[0],folder/'卷2.pdf')
        group=self.library.import_folder(folder)[0]
        self.assertEqual(cover_source(group)[0],group['volumes'][0]['path'])
        self.library.set_cover_volume(group,group['volumes'][1]['path'])
        reread=Library(self.library.path).find(group['id'])
        self.assertEqual(cover_source(reread),(group['volumes'][1]['path'],'book'))
        moved=self.root/'moved'; shutil.copytree(folder,moved); self.library.rescan(group,moved)
        self.assertEqual(group['cover_volume'],str(moved/'卷2.pdf'))
        self.library.set_cover(group); self.assertEqual(cover_source(group)[0],group['volumes'][0]['path'])

    def test_tracker_pause_switch_sleep_persistence_and_global_total(self):
        books=self.library.add(self.paths[:2]); now=[0.0]
        clock=ReadingTracker(self.library,lambda:now[0]); clock.select(books[0],books[0]); clock.update(True)
        now[0]=2; clock.update(False)
        now[0]=100; clock.update(False); self.assertEqual(books[0]['reading_seconds'],2)
        clock.select(books[1],books[1]); clock.update(True); now[0]=103; clock.update(True)
        now[0]=500; clock.update(True)  # sleep interval ignored
        now[0]=501; clock.stop()
        self.assertEqual(books[1]['reading_seconds'],4)
        self.assertEqual(self.library.data['stats']['total_reading_seconds'],6)
        self.library.data['books'].remove(books[0]); self.library.save()
        loaded=Library(self.library.path); self.assertEqual(loaded.data['stats']['total_reading_seconds'],6)
        self.assertEqual(duration(3661),'01:01:01')

    def test_folder_time_not_double_counted_and_gui_pause(self):
        folder=self.root/'series'; folder.mkdir(); shutil.copyfile(self.paths[1],folder/'卷1.epub')
        group=self.library.import_folder(folder)[0]
        w=Window(self.library,runtime_root=self.root); self.windows.append(w); w.show(); APP.processEvents(); w.open_entry(group)
        now=[0.0]; w.reading_tracker.now=lambda:now[0]; w.reading_tracker.last=0; w.reading_tracker.running=False
        with patch.object(w,'isActiveWindow',return_value=True),patch('app.QApplication.applicationState',return_value=Qt.ApplicationState.ApplicationActive):
            w.sync_reading_time(); now[0]=2; w.sync_reading_time()
            w.pause_timer.setChecked(True); now[0]=4; w.sync_reading_time()
            self.assertEqual(group['reading_seconds'],2)
            self.assertEqual(group['volumes'][0]['reading_seconds'],2)
            self.assertEqual(self.library.data['stats']['total_reading_seconds'],2)
            w.pause_timer.setChecked(False); now[0]=5; w.show_library(group)
            now[0]=7; w.sync_reading_time()
            self.assertEqual(group['reading_seconds'],3)
            self.assertIn('00:00:03',w.shelf.reading_total.text())
            self.assertIn('00:00:03',w.shelf.book_time.text())

    def test_immersive_keeps_time_when_inactive_until_manual_pause(self):
        self.library.add([self.paths[1]])
        entry=self.library.data['books'][0]
        w=Window(self.library,runtime_root=self.root); self.windows.append(w)
        w.show(); w.open_entry(entry)
        now=[0.0]; w.reading_tracker.now=lambda:now[0]
        w.reading_tracker.last=0; w.reading_tracker.running=False
        entry['reading_seconds']=0; self.library.data['stats']['total_reading_seconds']=0
        self.library.data['stats'].pop('daily',None)
        with patch.object(w,'isActiveWindow',return_value=False),patch.object(w,'isMinimized',return_value=True),patch('app.QApplication.applicationState',return_value=Qt.ApplicationState.ApplicationInactive):
            w.sync_reading_time(); self.assertFalse(w.reading_tracker.running)
            w.set_immersive(True); self.assertTrue(w.reading_tracker.running)
            now[0]=2; w.sync_reading_time(); self.assertEqual(entry['reading_seconds'],2)
            w.pause_timer.setChecked(True); now[0]=4; w.sync_reading_time()
            self.assertEqual(entry['reading_seconds'],2); self.assertFalse(w.reading_tracker.running)
            w.pause_timer.setChecked(False); now[0]=5; w.sync_reading_time()
            self.assertEqual(entry['reading_seconds'],3)
            w.exit_immersive(); self.assertFalse(w.reading_tracker.running)
            now[0]=7; w.sync_reading_time(); self.assertEqual(entry['reading_seconds'],3)
            w.set_immersive(True); now[0]=8; w.show_stats()
            self.assertEqual(entry['reading_seconds'],4); self.assertFalse(w.reading_tracker.running)
            now[0]=10; w.sync_reading_time(); self.assertEqual(entry['reading_seconds'],4)
            self.assertEqual(self.library.data['stats']['total_reading_seconds'],4)
            self.assertEqual(sum(day['seconds'] for day in self.library.data['stats']['daily'].values()),4)

if __name__=='__main__': unittest.main()
