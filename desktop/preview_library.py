"""Native library visual QA with generated, temporary sample data."""
import os
os.environ['QT_QPA_PLATFORM']='windows'
import tempfile
import shutil
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'tests'))
from test_reader import APP, fixtures, temporary_directory
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPixmap,QPainter,QColor,QFont
from PySide6.QtTest import QTest
from reader import Library
from app import Window
from library_ui import FolderImportDialog
APP.setFont(QFont('Microsoft YaHei UI',10))
with temporary_directory() as directory:
    root=Path(directory); files=fixtures(root); folder=root/'远行日记'; folder.mkdir()
    for i in range(1,13): shutil.copyfile(files[1],folder/f'远行日记 第{i:02}卷.epub')
    library=Library(root/'library.json'); group=library.import_folder(folder)[0]
    pix=QPixmap(420,600); pix.fill(QColor('#b5cec8')); painter=QPainter(pix)
    painter.fillRect(36,40,348,520,QColor('#e9e9d7'))
    painter.fillRect(62,75,296,145,QColor('#426a6c'))
    painter.setPen(QColor('#294f55')); painter.setFont(QFont('Microsoft YaHei UI',28,QFont.Weight.Bold))
    painter.drawText(QRectF(62,245,296,160),Qt.AlignmentFlag.AlignCenter,'远行日记\n01—12')
    painter.setFont(QFont('Microsoft YaHei UI',11)); painter.drawText(QRectF(62,485,296,40),Qt.AlignmentFlag.AlignCenter,'界面验收 · 示例封面'); painter.end()
    cover=root/'封面.png'; pix.save(str(cover)); library.set_cover(group,cover)
    titles=['雨后的街角','慢慢走过四季','放学后的约定','小镇便利店','夏日回声','旧书与咖啡','夜空观测日记','三个人的周末','森林邮差','风中的书页','海边散步','旅途中的我们']
    for i in range(65):
        library.data['books'].append({'id':f'sample{i}','kind':'file','path':str(root/f'样本{i}.epub'),'title':titles[i%len(titles)]+f' {i+1:02}','page':0})
    w=Window(library,runtime_root=root); w._startup_screen=APP.primaryScreen(); w.show(); w.shelf.sort.setCurrentIndex(2); QTest.qWait(500)
    w.grab().save('library-preview.png')
    w.show_library(group); QTest.qWait(100); w.grab().save('library-detail-preview.png')
    dialog=FolderImportDialog(folder,w); dialog.show(); QTest.qWait(100); dialog.grab().save('library-import-preview.png')
    dialog.close(); w.close()
