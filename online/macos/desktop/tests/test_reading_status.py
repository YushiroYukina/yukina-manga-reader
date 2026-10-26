import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from reader import Library,reading_status,READING_STATUSES
from app import Window
from test_reader import APP,fixtures,temporary_directory

class ReadingStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp=temporary_directory(); self.root=Path(self.temp.name); self.paths=fixtures(self.root)
        self.library=Library(self.root/'data/library.json'); self.books=self.library.add(self.paths)
        self.window=Window(self.library,runtime_root=self.root); self.window.show(); APP.processEvents()
    def tearDown(self): self.window.close(); self.temp.cleanup()

    def test_presets_custom_clear_reload_and_no_progress_changes(self):
        entry=self.books[0]; entry.update(page=3,reading_seconds=24)
        for status in READING_STATUSES:
            self.library.set_reading_status(entry,status)
            self.assertEqual(reading_status(Library(self.library.path).find(entry['id'])),status)
        self.library.set_reading_status(entry,'  待重读  ')
        self.assertEqual(reading_status(entry),'待重读'); self.assertEqual(entry['page'],3); self.assertEqual(entry['reading_seconds'],24)
        with self.assertRaises(ValueError): self.library.set_reading_status(entry,'字'*31)
        self.assertEqual(reading_status(entry),'待重读')
        self.library.set_reading_status(entry,'未标记'); self.assertNotIn('reading_status',entry)

    def test_detail_keyboard_save_filter_and_reading_preserves_mark(self):
        w=self.window; entry=self.books[1]; w.show_library(entry)
        w.shelf.status_combo.setEditText('已补完，待重读')
        QTest.keyClick(w.shelf.status_combo.lineEdit(),Qt.Key.Key_Return); APP.processEvents()
        self.assertEqual(reading_status(entry),'已补完，待重读')
        w.shelf.show_grid(); w.shelf.status_filter.setCurrentIndex(w.shelf.status_filter.findData('已补完，待重读'))
        self.assertEqual(w.shelf.grid.count(),1)
        self.assertEqual(w.shelf.grid.item(0).data(Qt.ItemDataRole.UserRole),entry['id'])
        w.open_entry(entry); w.go(3); self.assertEqual(reading_status(entry),'已补完，待重读')
        w.show_library(entry); self.assertEqual(w.shelf.status_combo.currentText(),'已补完，待重读')

    def test_grid_context_menu_marks_multiple_selected_books(self):
        shelf=self.window.shelf
        first=shelf.grid.item(0); second=shelf.grid.item(1)
        first.setSelected(True); second.setSelected(True)
        position=shelf.grid.visualItemRect(first).center()
        ids=[item.data(Qt.ItemDataRole.UserRole) for item in shelf.grid.selectedItems()]
        with patch.object(shelf,'status_menu') as menu:
            shelf.book_context_menu(position)
            self.assertEqual(len(menu.call_args.args[1]),2)
            menu.call_args.args[2]('已读')
        self.assertTrue(all(reading_status(self.library.find(i))=='已读' for i in ids))

    def test_volume_status_inheritance_independent_collection_and_rescan(self):
        folder=self.root/'series'; folder.mkdir(); volume=folder/'卷1.epub'; shutil.copyfile(self.paths[1],volume)
        single=self.library.add([volume])[0]; self.library.set_reading_status(single,'已读')
        group=self.library.import_folder(folder)[0]
        self.assertEqual(reading_status(group),'未标记'); self.assertEqual(reading_status(group['volumes'][0]),'已读')
        self.library.set_reading_status(group,'在读'); w=self.window; w.show_library(group)
        row=w.shelf.volume_list.topLevelItem(0)
        with patch.object(w.shelf,'status_menu') as menu:
            w.shelf.volume_context_menu(w.shelf.volume_list.visualItemRect(row).center())
            menu.call_args.args[2]('待重读')
        self.assertEqual(reading_status(group),'在读'); self.assertEqual(reading_status(group['volumes'][0]),'待重读')
        self.library.rescan(group); self.assertEqual(reading_status(group['volumes'][0]),'待重读')
        self.assertEqual(reading_status(single),'已读')

if __name__=='__main__': unittest.main()
