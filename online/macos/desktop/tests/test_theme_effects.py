import hashlib
import unittest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton
from PySide6.QtTest import QTest
from reader import Library
from app import Window
from ui_theme import THEMES,theme_color
from test_reader import APP,fixtures,temporary_directory

class ThemeEffectTests(unittest.TestCase):
    def setUp(self):
        self.temp=temporary_directory(); self.root=Path(self.temp.name); self.paths=fixtures(self.root)
        self.library=Library(self.root/'data/library.json'); self.entry=self.library.add([self.paths[1]])[0]
        self.w=Window(self.library,runtime_root=self.root); self.w.show(); APP.processEvents(); self.w.open_entry(self.entry)
    def tearDown(self): self.w.close(); self.temp.cleanup()

    def test_theme_switch_sync_restore_and_original_page_colors(self):
        colors=[]
        for name in THEMES:
            self.w.shelf.theme_combo.setCurrentIndex(self.w.shelf.theme_combo.findData(name)); APP.processEvents()
            self.assertEqual(self.w.theme_combo.currentData(),name)
            self.assertEqual(self.w.library.data['settings'].get('theme','sage'),name)
            colors.append(self.w.canvas.background.name())
            self.assertEqual(self.w.canvas.background,theme_color('#101416',name))
            self.assertEqual(self.w.canvas.pages[0].pixelColor(20,20).name(),'#ff0000')
        self.assertEqual(len(set(colors)),len(THEMES))
        self.w.close()
        self.w=Window(Library(self.library.path),runtime_root=self.root)
        self.assertEqual(self.w.theme_combo.currentData(),'paper')
        self.assertEqual(self.w.shelf.theme_combo.currentData(),'paper')

    def test_reading_has_no_library_sidebar_management(self):
        self.assertFalse(self.w.split.findChildren(type(self.w.split),'readerSidebar'))
        labels=[b.text() for b in self.w.split.findChildren(QPushButton)]
        self.assertIn('书库  F6',labels)
        self.assertFalse(any('导入' in text or '移出' in text or '定位' in text for text in labels))
        self.w.library_button.click(); self.assertIs(self.w.pages.currentWidget(),self.w.shelf)
        self.assertTrue(self.w.shelf.search.isVisible())

    def test_effects_frames_directions_endpoints_and_memory_release(self):
        hashes={}
        for key in ('book','slide','cover','fade'):
            self.w.go(1); APP.processEvents()
            self.w.motion.setCurrentIndex(self.w.motion.findData(key)); self.w.turn(1)
            overlay=self.w.page_turn; self.assertEqual(overlay.effect,key); self.assertEqual(overlay.side,-1)
            overlay.animation.pause(); states=[]
            for value in (0,.25,.75,1):
                overlay.advance(value); image=overlay.grab().toImage(); states.append(hashlib.sha256(image.constBits()).hexdigest())
            self.assertGreater(len(set(states)),2)
            hashes[key]=states[1]
            self.w.turn(-1); self.assertEqual(overlay.side,1)
            self.w.direction.setCurrentIndex(1); self.w.turn(1); self.assertEqual(overlay.side,1)
            self.w.direction.setCurrentIndex(0)
            self.assertIsNone(overlay.old)
        self.assertEqual(len(set(hashes.values())),4)
        self.w.motion.setCurrentIndex(self.w.motion.findData('none')); self.w.turn(-1)
        self.assertIsNone(self.w.page_turn.old); self.assertFalse(self.w.speed.isEnabled())
        self.w.close()
        saved=Library(self.library.path); self.assertEqual(saved.data['settings']['motion'],1)

if __name__=='__main__': unittest.main()
