import shutil,unittest
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
from test_reader import APP,temporary_directory,fixtures
from reader import Library,reading_status,volumes
from app import Window


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp=temporary_directory(); self.root=Path(self.temp.name)
        self.paths=fixtures(self.root); self.library=Library(self.root/'library.json')
        self.library.add([self.paths[1]])
        self.window=Window(self.library,runtime_root=self.root)
        self.window.show(); self.window.open_entry(self.library.data['books'][0]); APP.processEvents()

    def tearDown(self):
        self.window.close(); APP.processEvents(); self.temp.cleanup()

    def answer(self,yes):
        prompts=self.window.completion; prompts.timer.stop(); prompts.show_next()
        self.assertIsNotNone(prompts.dialog)
        prompts.dialog.button(QMessageBox.StandardButton.Yes if yes else QMessageBox.StandardButton.No).click()
        prompts.timer.stop()

    def test_last_visible_page_confirm_decline_rearm_and_persist(self):
        w=self.window; entry=w.entry
        w.go(1); self.assertFalse(w.completion.pending)
        w.go(3); self.assertEqual(reading_status(entry),'未标记')
        self.answer(False); self.assertEqual(reading_status(entry),'未标记')
        w.display(); w.completion.show_next(); self.assertIsNone(w.completion.dialog)
        w.go(1); w.go(3); self.answer(True)
        self.assertEqual(reading_status(entry),'已读')
        self.assertEqual(Library(self.library.path).data['books'][0]['reading_status'],'已读')
        w.display(); w.completion.show_next(); self.assertIsNone(w.completion.dialog)

    def test_volume_then_collection_confirmation_and_manual_status(self):
        w=self.window; folder=self.root/'合辑'; folder.mkdir()
        for i in range(2): shutil.copyfile(self.paths[1],folder/f'{i}.epub')
        owner=self.library.import_folder(folder)[0]; children=volumes(owner)
        self.library.set_reading_status(children[0],'已读')
        w.completion.groups_changed(); self.assertFalse(w.completion.pending)
        w.open_entry(owner,children[1]['path']); w.go(3)
        self.answer(True)
        self.assertEqual(reading_status(children[1]),'已读')
        self.assertEqual(reading_status(owner),'未标记')
        self.answer(False); w.completion.groups_changed(); self.assertFalse(w.completion.pending)
        self.library.set_reading_status(children[0],'搁置'); w.shelf.changed.emit()
        self.library.set_reading_status(children[0],'已读'); w.shelf.changed.emit()
        self.answer(True); self.assertEqual(reading_status(owner),'已读')

    def test_stale_queue_navigation_and_status_changes(self):
        w=self.window; w.go(3); w.go(1)
        w.completion.show_next(); self.assertIsNone(w.completion.dialog)

    def test_confirmation_waits_for_animation(self):
        w=self.window; w.go(1); w.turn(1)
        w.page_turn.animation.pause()
        w.completion.show_next()
        self.assertIsNone(w.completion.dialog)
        self.assertIsNotNone(w.page_turn.old)
        w.page_turn.finish(); self.answer(False)
        w.go(3); self.library.set_reading_status(w.entry,'已读')
        w.completion.show_next(); self.assertIsNone(w.completion.dialog)

    def test_single_page_and_immersive_confirmation_keeps_mode(self):
        w=self.window; w.double.setChecked(False); w.set_immersive(True)
        w.go(3); self.assertFalse(w.completion.pending)
        w.go(4); self.answer(True)
        self.assertTrue(w.immersive); self.assertTrue(w.isFullScreen())
        self.assertEqual(reading_status(w.entry),'已读')
