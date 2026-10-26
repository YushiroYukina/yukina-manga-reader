import unittest
from datetime import datetime,date,timedelta
from pathlib import Path
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from test_reader import APP,temporary_directory,fixtures
from reader import Library
from reading_time import ReadingTracker
from reading_stats import period_days,summarize
from app import Window


class ReadingStatsTests(unittest.TestCase):
    def setUp(self):
        self.temp=temporary_directory(); self.root=Path(self.temp.name)
        self.library=Library(self.root/'library.json')

    def tearDown(self): self.temp.cleanup()

    def test_midnight_monotonic_sleep_and_history_persistence(self):
        owner={'id':'series','title':'合辑','reading_seconds':100}
        volume={'id':'v1','title':'第一卷'}
        mono=[0.0]; wall=[datetime(2026,10,11,23,59,59)]
        self.library.data['stats']['total_reading_seconds']=100
        tracker=ReadingTracker(self.library,lambda:mono[0],lambda:wall[0])
        tracker.select(owner,volume); tracker.update(True)
        mono[0]+=2; wall[0]+=timedelta(seconds=2); tracker.update(True)
        daily=self.library.data['stats']['daily']
        self.assertEqual(daily['2026-10-11']['seconds'],1)
        self.assertEqual(daily['2026-10-12']['seconds'],1)
        self.assertEqual(daily['2026-10-12']['books']['series']['volumes']['v1']['seconds'],1)
        self.assertEqual(self.library.data['stats']['total_reading_seconds'],102)
        mono[0]+=60; wall[0]+=timedelta(seconds=60); tracker.update(True)
        self.assertEqual(sum(d['seconds'] for d in daily.values()),2)
        mono[0]+=1; wall[0]=datetime(2026,10,9,12); tracker.update(False)
        self.assertEqual(daily['2026-10-09']['seconds'],1)
        tracker.flush(); self.library.data['books']=[]; self.library.save()
        saved=Library(self.library.path)
        self.assertEqual(saved.data['stats']['daily'],daily)
        self.assertEqual(saved.data['stats']['total_reading_seconds'],103)

    def test_calendar_periods_and_no_double_counting(self):
        self.assertEqual(len(period_days(date(2024,2,10),'month')),29)
        self.assertEqual(len(period_days(date(2024,2,10),'year')),366)
        days=period_days(date(2026,10,11),'week')
        self.assertEqual(days[0],date(2026,10,5)); self.assertEqual(days[-1],date(2026,10,11))
        daily={days[0].isoformat():{'seconds':10,'books':{'a':{'title':'漫画','seconds':10,'volumes':{'v':{'title':'卷1','seconds':10}}}}},days[1].isoformat():{'seconds':20,'books':{'a':{'title':'新书名','seconds':20}}}}
        values,books=summarize(daily,days)
        self.assertEqual(sum(values),30); self.assertEqual(len(books),1)
        self.assertEqual(books['a']['seconds'],30)

    def test_gui_entry_calendar_click_pause_and_return(self):
        paths=fixtures(self.root); self.library.add([paths[1]])
        day=date(2026,10,7)
        self.library.data['stats']['daily']={day.isoformat():{'seconds':3661,'books':{'a':{'title':'漫画甲','seconds':3661,'volumes':{'v':{'title':'第一卷','seconds':3661}}}}}}
        w=Window(self.library,runtime_root=self.root); w.show(); APP.processEvents()
        w.shelf.reading_total.click(); self.assertIs(w.pages.currentWidget(),w.stats_page)
        page=w.stats_page; page.select_day(day)
        self.assertEqual(page.metrics[0].text(),'01:01:01'); self.assertEqual(page.metrics[1].text(),'1 本')
        self.assertEqual(page.daily_books.topLevelItem(0).child(0).text(0),'第一卷')
        page.set_mode('month'); self.assertEqual(len(page.chart.days),31)
        r=page.chart.plot(); QTest.mouseClick(page.chart,Qt.MouseButton.LeftButton,pos=QPoint(int(r.left()),int(r.center().y())))
        self.assertEqual(page.anchor,date(2026,10,1)); self.assertEqual(page.daily_books.topLevelItem(0).text(0),'当天暂无阅读记录')
        w.escape(); self.assertIs(w.pages.currentWidget(),w.shelf)
        w.open_entry(self.library.data['books'][0]); w.reading_tracker.running=True
        w.reading_clock.click(); self.assertFalse(w.reading_tracker.running)
        w.escape(); self.assertIs(w.pages.currentWidget(),w.split)
        page.select_day(date(2024,2,29)); page.set_mode('year'); page.shift(1)
        self.assertEqual(page.anchor,date(2025,2,28)); w.close()

    def test_legacy_totals_are_not_fabricated_daily(self):
        self.library.data['stats']['total_reading_seconds']=5000; self.library.save()
        saved=Library(self.library.path)
        self.assertEqual(saved.data['stats']['total_reading_seconds'],5000)
        self.assertEqual(saved.data['stats'].get('daily',{}),{})
