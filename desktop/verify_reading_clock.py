"""Verify live native timer activation/pause with temporary sample books."""
import os
os.environ['QT_QPA_PLATFORM']='windows'
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'tests'))
from test_reader import APP,fixtures,temporary_directory
from PySide6.QtTest import QTest
from reader import Library
from app import Window

with temporary_directory() as directory:
    root=Path(directory); paths=fixtures(root); library=Library(root/'data'/'library.json'); entry=library.add([paths[1]])[0]
    window=Window(library,runtime_root=root)
    window.show(); window.raise_(); window.activateWindow(); QTest.qWait(200); window.open_entry(entry)
    QTest.qWait(2200)
    assert entry.get('reading_seconds',0)>=1, (window.isActiveWindow(),window.reading_clock.text())
    window.show_library(); saved=entry['reading_seconds']; QTest.qWait(1200)
    assert entry['reading_seconds']==saved
    assert library.data['stats']['total_reading_seconds']==saved
    window.close()
    assert Library(library.path).data['stats']['total_reading_seconds']==saved
    print('Native reading clock counted, paused in library and persisted: PASS')
