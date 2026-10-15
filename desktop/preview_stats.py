"""Native statistics preview using temporary sample data, never user history."""
import os,sys
os.environ['QT_QPA_PLATFORM']='windows'
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).parent/'tests'))
from test_reader import APP,temporary_directory
from PySide6.QtTest import QTest
from PySide6.QtGui import QFont
from app import Window
from reader import Library
APP.setFont(QFont('Microsoft YaHei UI',10))
with temporary_directory() as directory:
    root=Path(directory); library=Library(root/'library.json'); anchor=date(2026,10,11)
    for i,total in enumerate([6300,14200,3900,7600,2000,9100,1600]):
        day=anchor-timedelta(days=6-i)
        library.data['stats'].setdefault('daily',{})[day.isoformat()]={'seconds':total,'books':{
            'a':{'title':'雨后的街角','seconds':total*.6,'volumes':{'v':{'title':'第 03 卷','seconds':total*.6}}},
            'b':{'title':'海边散步','seconds':total*.4,'volumes':{}}}}
    library.data['stats']['daily_started']='2026-10-05'
    library.data['stats']['total_reading_seconds']=sum(d['seconds'] for d in library.data['stats']['daily'].values())
    window=Window(library,runtime_root=root); window.show(); window.show_stats(); window.stats_page.select_day(anchor)
    for name in ('sage','paper'):
        window.apply_color_scheme(name); QTest.qWait(150)
        window.grab().save(f'reading-stats-{name}-preview.png')
    window.stats_page.set_mode('year'); QTest.qWait(100); window.grab().save('reading-stats-year-preview.png')
    window.close()
