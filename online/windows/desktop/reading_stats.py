"""Calendar reading statistics, rendered locally without new disk caches."""
import calendar
from datetime import date,timedelta
from PySide6.QtCore import Qt,Signal,QRectF,QPointF,QDate,QSize
from PySide6.QtGui import QPainter,QPen,QPainterPath,QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QButtonGroup,QScrollArea,QDateEdit,QTreeWidget,QTreeWidgetItem,QFrame,QToolTip,QStyledItemDelegate)
from reading_time import duration
from ui_theme import theme_color,button_role
from smooth_scroll import SmoothScroll


def chart_color():
    return theme_color('#1c392b' if theme_color('#181e20').lightness()>160 else '#a2c9b1')


class TimeBars(QStyledItemDelegate):
    def sizeHint(self,option,index): return QSize(120,44)

    def paint(self,painter,option,index):
        ratio=index.data(Qt.ItemDataRole.UserRole)
        if ratio is None:
            super().paint(painter,option,index); return
        painter.save()
        painter.setPen(theme_color('#e7ebe5'))
        r=QRectF(option.rect).adjusted(8,3,-14,-4)
        painter.drawText(r.adjusted(0,0,0,-10),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,index.data())
        track=QRectF(r.left(),r.bottom()-5,r.width(),4)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(theme_color('#3a484a')); painter.drawRoundedRect(track,2,2)
        painter.setBrush(chart_color()); track.setWidth(track.width()*ratio); painter.drawRoundedRect(track,2,2)
        painter.restore()


def period_days(anchor,mode):
    if mode=='week':
        start=anchor-timedelta(days=anchor.weekday()); count=7
    elif mode=='month':
        start=anchor.replace(day=1); count=calendar.monthrange(anchor.year,anchor.month)[1]
    else:
        start=date(anchor.year,1,1); count=366 if calendar.isleap(anchor.year) else 365
    return [start+timedelta(days=i) for i in range(count)]


def summarize(daily,days):
    values=[]; books={}
    for day in days:
        bucket=daily.get(day.isoformat(),{}); values.append(bucket.get('seconds',0))
        for key,record in bucket.get('books',{}).items():
            target=books.setdefault(key,{'title':record['title'],'seconds':0})
            target['title']=record['title']; target['seconds']+=record['seconds']
    return values,books


class TrendChart(QWidget):
    day_selected=Signal(object)
    def __init__(self):
        super().__init__(); self.setMinimumHeight(285); self.setMouseTracking(True)
        self.days=[]; self.values=[]; self.selected=None

    def plot(self): return QRectF(72,20,max(1,self.width()-96),self.height()-64)

    def nearest(self,x):
        r=self.plot()
        return max(0,min(len(self.days)-1,round((x-r.left())/r.width()*max(1,len(self.days)-1))))

    def mouseReleaseEvent(self,event):
        if self.days and event.button()==Qt.MouseButton.LeftButton and self.plot().contains(event.position()):
            self.day_selected.emit(self.days[self.nearest(event.position().x())])

    def mouseMoveEvent(self,event):
        if self.days and self.plot().contains(event.position()):
            i=self.nearest(event.position().x())
            QToolTip.showText(event.globalPosition().toPoint(),f'{self.days[i]:%Y-%m-%d}  ·  {duration(self.values[i])}',self)

    def paintEvent(self,event):
        if not self.days: return
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=self.plot(); peak=max(60,max(self.values,default=0)*1.15)
        text=theme_color('#e7ebe5'); muted=theme_color('#97a7a8'); accent=chart_color()
        for i in range(5):
            y=r.bottom()-r.height()*i/4
            p.setPen(QPen(theme_color('#3a484a'),1)); p.drawLine(QPointF(r.left(),y),QPointF(r.right(),y))
            p.setPen(muted); seconds=peak*i/4
            label=f'{seconds/3600:.1f} h' if peak>=3600 else f'{seconds/60:.0f} min'
            p.drawText(QRectF(0,y-10,62,20),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,label)
        points=[QPointF(r.left()+r.width()*i/max(1,len(self.days)-1),r.bottom()-r.height()*v/peak) for i,v in enumerate(self.values)]
        path=QPainterPath(points[0])
        for point in points[1:]: path.lineTo(point)
        area=QPainterPath(path); area.lineTo(r.bottomRight()); area.lineTo(r.bottomLeft()); area.closeSubpath()
        fill=QColor(accent); fill.setAlpha(26); p.fillPath(area,fill)
        p.setPen(QPen(accent,2.5)); p.drawPath(path)
        for i,(day,point) in enumerate(zip(self.days,points)):
            if len(self.days)<=31 or day==self.selected:
                p.setBrush(accent if day==self.selected else theme_color('#222c2e'))
                p.drawEllipse(point,5 if day==self.selected else 3,5 if day==self.selected else 3)
            show=len(self.days)==7 or (len(self.days)<=31 and (i%5==0 or i==len(self.days)-1)) or (len(self.days)>31 and day.day==1)
            if show:
                p.setPen(text if day==self.selected else muted)
                label=f'{day.month}月' if len(self.days)>31 else day.strftime('%m-%d')
                p.drawText(QRectF(point.x()-27,r.bottom()+14,54,22),Qt.AlignmentFlag.AlignCenter,label)
                p.setPen(QPen(accent,2.5))


class ReadingStatsPage(QWidget):
    back_requested=Signal()
    def __init__(self,library):
        super().__init__(); self.library=library; self.mode='week'; self.anchor=date.today()
        outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame); self.scroll.verticalScrollBar().setSingleStep(24)
        body=QWidget(); layout=QVBoxLayout(body); layout.setContentsMargins(32,26,32,24); layout.setSpacing(18)
        self.scroll.setWidget(body); outer.addWidget(self.scroll)
        top=QHBoxLayout(); brand=QVBoxLayout()
        eyebrow=QLabel('MIGI  /  阅读统计'); eyebrow.setObjectName('eyebrow'); brand.addWidget(eyebrow)
        title=QLabel('把阅读留在日历里'); title.setStyleSheet('font-size:28px; font-weight:600;'); brand.addWidget(title)
        hint=QLabel('回顾阅读投入与每日变化 · 点击趋势图查看当天书籍'); hint.setObjectName('muted'); brand.addWidget(hint)
        top.addLayout(brand); top.addStretch()
        back=QPushButton('返回'); button_role(back,'quiet'); back.clicked.connect(self.back_requested); top.addWidget(back)
        layout.addLayout(top)
        controls=QHBoxLayout(); group=QButtonGroup(self)
        for name,key in [('周','week'),('月','month'),('年','year')]:
            button=QPushButton(name); button.setCheckable(True); button.setChecked(key==self.mode)
            group.addButton(button); controls.addWidget(button)
            button.clicked.connect(lambda checked=False,key=key:self.set_mode(key))
        previous=QPushButton('‹ 上一期'); previous.clicked.connect(lambda:self.shift(-1)); controls.addWidget(previous)
        following=QPushButton('下一期 ›'); following.clicked.connect(lambda:self.shift(1)); controls.addWidget(following)
        today=QPushButton('今天'); today.clicked.connect(lambda:self.select_day(date.today())); controls.addWidget(today)
        controls.addStretch(); self.range_label=QLabel(); self.range_label.setObjectName('muted'); controls.addWidget(self.range_label)
        layout.addLayout(controls)
        row=QHBoxLayout(); self.metrics=[]
        for name in ('阅读时长','阅读书籍','活跃天数','活跃日均'):
            card=QFrame(); card.setObjectName('controlBar'); box=QVBoxLayout(card); box.setContentsMargins(20,16,20,16)
            label=QLabel(name); label.setObjectName('muted'); box.addWidget(label)
            value=QLabel('—'); value.setStyleSheet('font-size:25px; font-weight:600;'); box.addWidget(value)
            self.metrics.append(value); row.addWidget(card,1)
        layout.addLayout(row)
        trend=QFrame(); trend.setObjectName('controlBar'); box=QVBoxLayout(trend); box.setContentsMargins(18,16,18,12)
        label=QLabel('每日阅读时长趋势'); label.setStyleSheet('font-size:18px; font-weight:600;'); box.addWidget(label)
        self.chart=TrendChart(); self.chart.day_selected.connect(self.select_day); box.addWidget(self.chart); layout.addWidget(trend)
        lower=QHBoxLayout(); lower.setSpacing(18)
        rank=QFrame(); rank.setObjectName('controlBar'); box=QVBoxLayout(rank); box.setContentsMargins(18,16,18,16)
        label=QLabel('本期阅读 Top 10'); label.setStyleSheet('font-size:18px; font-weight:600;'); box.addWidget(label)
        self.ranking=self.table(['书籍','阅读时长']); box.addWidget(self.ranking); lower.addWidget(rank,1)
        self.ranking.setItemDelegateForColumn(1,TimeBars(self.ranking))
        daily=QFrame(); daily.setObjectName('controlBar'); box=QVBoxLayout(daily); box.setContentsMargins(18,16,18,16)
        head=QHBoxLayout(); self.day_title=QLabel('当天阅读'); self.day_title.setStyleSheet('font-size:18px; font-weight:600;'); head.addWidget(self.day_title)
        head.addStretch(); self.day_picker=QDateEdit(); self.day_picker.setCalendarPopup(True); self.day_picker.setDisplayFormat('yyyy-MM-dd')
        self.day_picker.dateChanged.connect(lambda q:self.select_day(date(q.year(),q.month(),q.day()))); head.addWidget(self.day_picker); box.addLayout(head)
        self.daily_books=self.table(['当天书籍 / 分卷','阅读时长']); box.addWidget(self.daily_books); lower.addWidget(daily,1)
        layout.addLayout(lower)
        self.note=QLabel(); self.note.setWordWrap(True); self.note.setObjectName('muted'); layout.addWidget(self.note)
        layout.addStretch(); self.refresh()

    def table(self,headers):
        table=QTreeWidget(); table.setHeaderLabels(headers); table.setMinimumHeight(220)
        table.setAlternatingRowColors(True); table.setColumnWidth(0,300); table.setUniformRowHeights(True)
        table.scroll_motion=SmoothScroll(table)
        return table

    def set_mode(self,mode): self.mode=mode; self.refresh()

    def shift(self,amount):
        if self.mode=='week': self.anchor+=timedelta(days=amount*7)
        elif self.mode=='month':
            index=self.anchor.year*12+self.anchor.month-1+amount
            year,month=divmod(index,12); month+=1
            self.anchor=date(year,month,min(self.anchor.day,calendar.monthrange(year,month)[1]))
        else: self.anchor=self.anchor.replace(year=self.anchor.year+amount,day=min(self.anchor.day,calendar.monthrange(self.anchor.year+amount,self.anchor.month)[1]))
        self.refresh()

    def select_day(self,day): self.anchor=day; self.refresh()

    def refresh(self):
        stats=self.library.data.get('stats',{}); daily=stats.get('daily',{})
        days=period_days(self.anchor,self.mode); values,books=summarize(daily,days)
        total=sum(values); active=sum(v>0 for v in values)
        for label,value in zip(self.metrics,[duration(total),f'{len(books)} 本',f'{active} 天',duration(total/active if active else 0)]): label.setText(value)
        self.range_label.setText(f'{days[0]:%Y-%m-%d} — {days[-1]:%Y-%m-%d}')
        self.chart.days=days; self.chart.values=values; self.chart.selected=self.anchor; self.chart.update()
        self.ranking.clear()
        ranked=sorted(books.values(),key=lambda r:r['seconds'],reverse=True)[:10]
        maximum=max((record['seconds'] for record in ranked),default=1) or 1
        for i,record in enumerate(ranked,1):
            item=QTreeWidgetItem([f'{i:02}  {record["title"]}',duration(record['seconds'])]); item.setToolTip(0,record['title'])
            item.setData(1,Qt.ItemDataRole.UserRole,record['seconds']/maximum); self.ranking.addTopLevelItem(item)
        if not books: self.ranking.addTopLevelItem(QTreeWidgetItem(['本期暂无阅读记录','—']))
        self.day_picker.blockSignals(True); self.day_picker.setDate(QDate(self.anchor.year,self.anchor.month,self.anchor.day)); self.day_picker.blockSignals(False)
        bucket=daily.get(self.anchor.isoformat(),{}); self.day_title.setText('当天阅读 · '+duration(bucket.get('seconds',0)))
        self.daily_books.clear()
        for record in sorted(bucket.get('books',{}).values(),key=lambda r:r['seconds'],reverse=True):
            item=QTreeWidgetItem([record['title'],duration(record['seconds'])]); item.setToolTip(0,record['title']); self.daily_books.addTopLevelItem(item)
            for volume in sorted(record.get('volumes',{}).values(),key=lambda r:r['seconds'],reverse=True):
                child=QTreeWidgetItem([volume['title'],duration(volume['seconds'])]); child.setToolTip(0,volume['title']); item.addChild(child)
            item.setExpanded(True)
        if not bucket.get('books'): self.daily_books.addTopLevelItem(QTreeWidgetItem(['当天暂无阅读记录','—']))
        started=stats.get('daily_started') or '首次阅读后'
        self.note.setText(f'累计阅读 {duration(stats.get("total_reading_seconds",0))}  ·  按日记录开始：{started}。更新前累计时长保留，但无法还原到具体日期。合辑按整本计入，分卷可展开查看；删除书库条目仍保留阅读历史。')
