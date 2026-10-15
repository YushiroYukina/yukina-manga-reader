"""Native visual QA using generated sample pages, without importing user books."""
import os
os.environ['QT_QPA_PLATFORM'] = 'windows'
import tempfile
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'tests'))
from test_reader import APP, fixtures, temporary_directory
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from reader import Library
from app import Window
APP.setFont(QFont('Microsoft YaHei UI',10))
with temporary_directory() as directory:
    paths=fixtures(directory)
    lib=Library(Path(directory)/'library.json'); lib.add([paths[1]])
    w=Window(lib,runtime_root=Path(directory)); w.show(); APP.processEvents(); w.open_entry(lib.data['books'][0])
    w.go(1); w.settings_btn.click(); QTest.qWait(100)
    w.grab().save('preview.png')
    w.turn(1); w.page_turn.animation.pause(); w.page_turn.advance(.3)
    w.grab().save('preview-turn.png')
    w.page_turn.finish(); w.set_immersive(True); QTest.qWait(100)
    w.grab().save('preview-immersive.png')
    w.exit_immersive(); w.close()
