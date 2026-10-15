"""Native visual checks for multiple color schemes and the focused reader."""
import os
os.environ['QT_QPA_PLATFORM']='windows'
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'tests'))
from test_reader import APP,fixtures,temporary_directory
from PySide6.QtTest import QTest
from reader import Library
from app import Window
from ui_theme import THEMES

with temporary_directory() as directory:
    root=Path(directory); files=fixtures(root); library=Library(root/'data/library.json'); books=library.add(files)
    window=Window(library,runtime_root=root); window._startup_screen=APP.primaryScreen(); window.show(); window.open_entry(books[1]); window.go(1)
    window.settings_btn.setChecked(True); window.toggle_appearance(True)
    for name in THEMES:
        window.apply_color_scheme(name); QTest.qWait(100)
        window.grab().save(f'theme-reader-{name}.png')
    window.show_library(); window.apply_color_scheme('paper'); QTest.qWait(300); window.grab().save('theme-library-paper.png')
    window.apply_color_scheme('ocean'); QTest.qWait(100); window.grab().save('theme-library-ocean.png')
    window.open_entry(books[1]); window.go(1); window.motion.setCurrentIndex(window.motion.findData('slide')); window.turn(1)
    window.page_turn.animation.pause(); window.page_turn.advance(.4); window.grab().save('theme-slide-preview.png')
    window.page_turn.finish(); window.go(1); window.motion.setCurrentIndex(window.motion.findData('cover')); window.turn(1)
    window.page_turn.animation.pause(); window.page_turn.advance(.4); window.grab().save('theme-cover-preview.png')
    window.close()
