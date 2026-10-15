import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton
from reader import Library, volumes
from app import Window
from library_ui import FolderImportDialog
from test_reader import APP, fixtures, png, temporary_directory


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=temporary_directory(); self.root=Path(self.temp.name)
        self.source=self.root/'多卷漫画'; self.source.mkdir()
        epub=fixtures(self.root)[1]
        for number in (10,2,1): shutil.copyfile(epub,self.source/f'卷{number}.epub')
        self.lib=Library(self.root/'records'/'library.json'); self.windows=[]

    def tearDown(self):
        for w in self.windows: w.close()
        self.temp.cleanup()

    def window(self):
        w=Window(self.lib,runtime_root=self.root); self.windows.append(w); w.show(); APP.processEvents(); return w

    def test_folder_group_and_independent_import(self):
        group=self.lib.import_folder(self.source)[0]
        self.assertEqual(len(self.lib.data['books']),1)
        self.assertEqual([Path(v['path']).name for v in volumes(group)],['卷1.epub','卷2.epub','卷10.epub'])
        self.assertEqual(self.lib.import_folder(self.source)[0]['id'],group['id'])
        singles=self.lib.import_folder(self.source,grouped=False)
        self.assertEqual(len(singles),3); self.assertTrue(all(e['kind']=='file' for e in singles))
        self.assertEqual(self.lib.import_folder(self.source,grouped=False),[])

    def test_legacy_progress_migration_and_regroup(self):
        path=self.source/'卷2.epub'
        self.lib.path.parent.mkdir()
        self.lib.path.write_text(json.dumps({'books':[{'path':str(path),'title':'已有标题','page':14}], 'settings':{'gap':8}}),encoding='utf-8')
        migrated=Library(self.lib.path)
        self.assertEqual(migrated.data['books'][0]['page'],14)
        self.assertEqual(migrated.data['settings']['gap'],8)
        group=migrated.import_folder(self.source)[0]
        self.assertEqual(group['volumes'][1]['page'],14)
        self.assertEqual(len(migrated.data['books']),2)
        reread=Library(self.lib.path)
        self.assertEqual(reread.data['books'][0]['id'],migrated.data['books'][0]['id'])

    def test_rescan_relocate_preserves_order_progress_and_missing(self):
        group=self.lib.import_folder(self.source)[0]
        group['volumes'][1]['page']=3; group['current_volume']=group['volumes'][1]['path']
        shutil.copyfile(self.source/'卷1.epub',self.source/'卷3.epub')
        self.assertEqual(self.lib.rescan(group),1)
        self.assertEqual([Path(v['path']).name for v in volumes(group)],['卷1.epub','卷2.epub','卷3.epub','卷10.epub'])
        new=self.root/'移动后的漫画'; shutil.copytree(self.source,new)
        self.lib.rescan(group,new)
        self.assertEqual(group['volumes'][1]['page'],3)
        self.assertEqual(group['current_volume'],str((new/'卷2.epub').resolve()))
        (new/'卷2.epub').unlink(); self.lib.rescan(group)
        self.assertEqual(len(group['volumes']),4); self.assertEqual(group['volumes'][1]['page'],3)

    def test_custom_cover_only_stores_source_path(self):
        group=self.lib.import_folder(self.source)[0]
        cover=self.root/'自定义封面.png'; cover.write_bytes(png('red'))
        before={p.relative_to(self.root) for p in self.root.rglob('*')}
        self.lib.set_cover(group,cover)
        self.assertEqual(group['cover_path'],str(cover.resolve()))
        self.assertEqual(before,{p.relative_to(self.root) for p in self.root.rglob('*')})
        w=self.window(); w.show_library(group)
        for _ in range(100):
            engine=w.shelf.covers.thumbnails
            if engine.request(group) and engine.identity(group)[0] not in engine.pending: break
            QTest.qWait(50)
        self.assertEqual(w.shelf.covers.get(group).toImage().pixelColor(100,150).name(),'#ff0000')
        self.lib.set_cover(group); self.assertNotIn('cover_path',group)
        self.assertEqual(cover.read_bytes(),png('red'))

    def test_volume_read_resume_manual_order_and_remove(self):
        group=self.lib.import_folder(self.source)[0]; w=self.window()
        self.assertIs(w.pages.currentWidget(),w.shelf)
        w.show_library(group); w.shelf.volume_list.setCurrentItem(w.shelf.volume_list.topLevelItem(1)); w.shelf.read_selected()
        self.assertIs(w.entry,group['volumes'][1]); self.assertIs(w.pages.currentWidget(),w.split)
        w.go(3); w.change_volume(1); self.assertEqual(w.page,0)
        w.change_volume(-1); self.assertEqual(w.page,3)
        w.show_library(group); w.shelf.move_volume(-1)
        self.assertTrue(group['manual_order']); self.assertEqual(Path(group['volumes'][0]['path']).name,'卷2.epub')
        w.shelf.read_current(); self.assertEqual(w.page,3)
        w.show_library(group); w.shelf.remove_entry()
        self.assertIsNone(w.book); self.assertTrue((self.source/'卷2.epub').exists())
        self.assertEqual(len(self.lib.data['books']),0)

    def test_large_library_pagination_search_and_cover_memory_limit(self):
        for i in range(125):
            self.lib.data['books'].append({'id':str(i),'kind':'file','title':f'漫画 {i}','path':str(self.root/f'{i}.pdf'),'page':0})
        w=self.window(); self.assertEqual(w.shelf.grid.count(),48)
        w.shelf.navigate(1); self.assertEqual(w.shelf.grid.count(),48)
        w.shelf.navigate(1); self.assertEqual(w.shelf.grid.count(),29)
        w.shelf.search.setText('漫画 124'); self.assertEqual(w.shelf.grid.count(),1)
        for entry in self.lib.data['books']: w.shelf.covers.get(entry)
        self.assertLessEqual(len(w.shelf.covers.cache),48)
        self.assertTrue(all(not shortcut.isEnabled() for shortcut in w.reader_shortcuts))

    def test_folder_import_mode_switch(self):
        dialog=FolderImportDialog(self.source)
        self.assertTrue(dialog.grouped.isChecked()); self.assertTrue(dialog.title.isEnabled())
        dialog.separate.setChecked(True)
        self.assertFalse(dialog.grouped.isChecked()); self.assertFalse(dialog.title.isEnabled())
        dialog.close()

    def test_library_header_import_actions(self):
        w=self.window()
        with patch('app.QFileDialog.getOpenFileNames',return_value=([],'')) as files:
            next(b for b in w.shelf.findChildren(QPushButton) if b.text()=='＋ 独立图书').click()
            files.assert_called_once()
        with patch('app.QFileDialog.getExistingDirectory',return_value='') as folder:
            next(b for b in w.shelf.findChildren(QPushButton) if b.text()=='＋ 导入文件夹').click()
            folder.assert_called_once()
        next(b for b in w.shelf.findChildren(QPushButton) if b.text()=='返回阅读  F6').click()
        self.assertIs(w.pages.currentWidget(),w.split)

if __name__=='__main__': unittest.main()
