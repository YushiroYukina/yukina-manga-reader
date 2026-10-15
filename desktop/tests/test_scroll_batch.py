import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QPoint,QPointF,Qt,QItemSelectionModel
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QListView,QDialogButtonBox
from PySide6.QtTest import QTest
from app import Window
from reader import Library
from batch_import import BatchImportDialog,MultiFolderDialog
from test_reader import APP,fixtures,temporary_directory

class ScrollBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=temporary_directory(); self.root=Path(self.temp.name).resolve(); self.paths=fixtures(self.root)
        self.library=Library(self.root/'data/library.json'); self.window=None
    def tearDown(self):
        if self.window: self.window.close()
        self.temp.cleanup()

    def wheel(self,view,angle=0,pixel=0):
        point=QPointF(50,50)
        event=QWheelEvent(point,QPointF(view.viewport().mapToGlobal(QPoint(50,50))),QPoint(0,pixel),QPoint(0,angle),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
        APP.sendEvent(view.viewport(),event)
        return event

    def test_grid_wheel_small_smooth_steps_touchpad_and_boundaries(self):
        for i in range(48): self.library.data['books'].append({'id':str(i),'kind':'file','title':f'书 {i}','path':str(self.root/f'{i}.pdf'),'page':0})
        self.window=Window(self.library,runtime_root=self.root); self.window.show(); APP.processEvents()
        grid=self.window.shelf.grid; bar=grid.verticalScrollBar(); self.assertGreater(bar.maximum(),200)
        self.wheel(grid,angle=-120); self.assertEqual(bar.value(),0)
        QTest.qWait(70); middle=bar.value(); self.assertGreater(middle,0); self.assertLess(middle,64)
        QTest.qWait(180); self.assertEqual(bar.value(),64)
        self.wheel(grid,pixel=-12); self.assertEqual(bar.value(),76)
        self.wheel(grid,pixel=5); self.assertEqual(bar.value(),71)
        self.wheel(grid,angle=120); QTest.qWait(220); self.assertEqual(bar.value(),7)
        self.wheel(grid,angle=120); QTest.qWait(220); self.assertEqual(bar.value(),0)
        for _ in range(3): self.wheel(grid,angle=-120)
        QTest.qWait(220); self.assertEqual(bar.value(),192)
        self.wheel(grid,angle=-120); bar.sliderPressed.emit(); stopped=bar.value(); QTest.qWait(220); self.assertEqual(bar.value(),stopped)

    def test_batch_mixed_sources_dedupe_partial_errors_and_single_save(self):
        a=self.root/'漫画甲'; b=self.root/'漫画乙'; empty=self.root/'空文件夹'
        for folder in (a,b,empty): folder.mkdir()
        for folder in (a,b):
            shutil.copyfile(self.paths[1],folder/'卷1.epub'); shutil.copyfile(self.paths[0],folder/'卷2.pdf')
        with patch.object(self.library,'save',wraps=self.library.save) as save:
            report=self.library.import_batch([*self.paths,a,b,a,empty])
            self.assertEqual(save.call_count,1)
        self.assertEqual(report['added'],5); self.assertEqual(report['skipped'],1); self.assertEqual(len(report['errors']),1)
        self.assertEqual(len(Library(self.library.path).data['books']),5)
        group=next(e for e in self.library.data['books'] if e.get('kind')=='folder')
        group['volumes'][0].update(page=3,reading_status='已读')
        report=self.library.import_batch([a]); self.assertEqual(report['updated'],1)
        self.assertEqual(group['volumes'][0]['page'],3); self.assertEqual(group['volumes'][0]['reading_status'],'已读')
        report=self.library.import_batch([b],grouped=False); self.assertEqual(report['added'],2)

    def test_batch_review_add_remove_and_multi_folder_picker(self):
        a=self.root/'目录甲'; b=self.root/'目录乙'; a.mkdir(); b.mkdir()
        dialog=BatchImportDialog(); dialog.add_sources([self.paths[0],a,b,a])
        self.assertEqual(len(dialog.sources()),3)
        self.assertTrue(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        dialog.items.item(0).setSelected(True); dialog.remove_selected(); self.assertEqual(len(dialog.sources()),2)
        dialog.close()
        picker=MultiFolderDialog(); picker.setDirectory(str(self.root)); picker.show(); QTest.qWait(200)
        view=picker.findChild(QListView,'listView'); self.assertIsNotNone(view)
        model=view.model(); selected=view.selectionModel(); selected.clearSelection()
        for folder in (a,b):
            index=model.index(str(folder)); self.assertTrue(index.isValid())
            selected.select(index,QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows)
        picker.accept(); self.assertEqual(set(picker.folders),{str(a),str(b)}); picker.close()

    def test_loaded_cover_repaint_uses_memory(self):
        entry=self.library.add([self.paths[1]])[0]
        self.window=Window(self.library,runtime_root=self.root); self.window.show(); self.window.show_library(entry)
        covers=self.window.shelf.covers
        for _ in range(150):
            if covers.thumbnails.request(entry) and covers.thumbnails.identity(entry)[0] not in covers.thumbnails.pending: break
            QTest.qWait(30)
        covers.get(entry)
        with patch('pathlib.Path.stat',side_effect=AssertionError('repaint should not access filesystem')):
            covers.get(entry)

if __name__=='__main__': unittest.main()
