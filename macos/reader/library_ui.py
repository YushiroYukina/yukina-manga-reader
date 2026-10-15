from mac_accessibility import BookGrid
from platform_support import MULTI_FILE_TITLE, restore_after_native_dialog
import sys
from platform_support import FONT_FAMILY
"""Paged library and volume details. Cover files stay at their original paths."""
from collections import OrderedDict
from pathlib import Path
import math
from PySide6.QtCore import Qt, QSize, QRectF, Signal
from PySide6.QtGui import (QPainter, QPixmap, QColor, QFont, QLinearGradient, QImageReader,QPainterPath)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QListWidget, QListWidgetItem, QListView, QStyledItemDelegate,
    QStyle, QStackedWidget, QTreeWidget, QTreeWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QDialog, QDialogButtonBox, QRadioButton, QCheckBox,QMenu,QInputDialog,QAbstractItemView)
from reader import natural_key, volumes,READING_STATUSES,reading_status
from cover_cache import ThumbnailCache,cover_source
from reading_time import duration
from ui_theme import button_role,icon,ElidedLabel,THEMES,theme_color
from smooth_scroll import SmoothScroll


class FolderImportDialog(QDialog):
    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.setWindowTitle('导入文件夹'); self.resize(610,410)
        layout=QVBoxLayout(self); layout.setContentsMargins(26,24,26,24); layout.setSpacing(16)
        name=QLabel(Path(folder).name); name.setStyleSheet('font-size:22px; font-weight:600;')
        layout.addWidget(name)
        path=QLabel(str(folder)); path.setWordWrap(True); path.setStyleSheet('color:#9aaeb3;'); layout.addWidget(path)
        self.grouped=QRadioButton('合为一本书 · 文件夹中的文件作为各卷'); self.grouped.setChecked(True)
        self.separate=QRadioButton('每个文件独立建书 · 适合单卷或完结本')
        layout.addWidget(self.grouped); layout.addWidget(self.separate)
        self.title=QLineEdit(Path(folder).name); self.title.setPlaceholderText('合辑书名')
        layout.addWidget(self.title); self.grouped.toggled.connect(self.title.setEnabled)
        self.recursive=QCheckBox('包含子文件夹中的图书'); self.recursive.setChecked(True); layout.addWidget(self.recursive)
        hint=QLabel('图书和封面仅连接原路径。已有独立书籍不会自动移除；合辑会继承已记录的分卷进度。')
        hint.setWordWrap(True); hint.setStyleSheet('color:#9aaeb3; font-size:12px;'); layout.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('导入')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        button_role(buttons.button(QDialogButtonBox.StandardButton.Ok),'primary')
        button_role(buttons.button(QDialogButtonBox.StandardButton.Cancel),'quiet')
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)


class Covers:
    """48 RAM previews backed by reader-local, first-page disk thumbnails."""
    def __init__(self,runtime_root,parent=None):
        self.cache=OrderedDict(); self.waiting={}; self.thumbnails=ThumbnailCache(runtime_root,parent)
        self.thumbnails.ready.connect(self.invalidate)
        self.connected=True

    def shutdown(self):
        self.thumbnails.stop()
        if self.connected:
            self.thumbnails.ready.disconnect(self.invalidate); self.connected=False
        self.cache.clear(); self.waiting.clear()

    def invalidate(self,key=''):
        if not key: self.cache.clear(); self.waiting.clear()
        else:
            for cache_key in self.waiting.pop(key,set()): self.cache.pop(cache_key,None)

    def get(self, entry):
        cover,kind=cover_source(entry)
        key=(entry['id'],entry['title'],cover,kind,len(volumes(entry)))
        if key in self.cache:
            self.cache.move_to_end(key); return self.cache[key]
        try: stamp=Path(cover).stat().st_mtime_ns if cover else 0
        except OSError: stamp=0
        thumbnail=self.thumbnails.request(entry)
        identity=self.thumbnails.identity(entry)[0] if not thumbnail else None
        if identity in self.thumbnails.pending: self.waiting.setdefault(identity,set()).add(key)
        pix=QPixmap(210,300); pix.fill(theme_color('#29373d'))
        image=None
        if thumbnail:
            reader=QImageReader(str(thumbnail)); image=reader.read()
        painter=QPainter(pix); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if image is not None and not image.isNull():
            size=image.size().scaled(pix.size(),Qt.AspectRatioMode.KeepAspectRatio)
            target=QRectF((pix.width()-size.width())/2,(pix.height()-size.height())/2,size.width(),size.height())
            painter.drawImage(target,image)
        else:
            gradient=QLinearGradient(0,0,210,300)
            gradient.setColorAt(0,theme_color('#38585a' if entry.get('kind')=='folder' else '#354556'))
            gradient.setColorAt(1,theme_color('#1c292f')); painter.fillRect(pix.rect(),gradient)
            painter.setPen(theme_color('#789d9d')); painter.drawRect(13,13,183,273)
            painter.setFont(QFont(FONT_FAMILY,9)); painter.setPen(theme_color('#a5c7c3'))
            painter.drawText(QRectF(24,30,162,25),Qt.AlignmentFlag.AlignLeft,'MIGI  /  右页')
            painter.setFont(QFont(FONT_FAMILY,16,QFont.Weight.DemiBold)); painter.setPen(theme_color('#edf4f1'))
            title=entry['title']; title=title if len(title)<35 else title[:34]+'…'
            painter.drawText(QRectF(25,70,160,135),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,title)
            painter.setFont(QFont(FONT_FAMILY,10)); painter.setPen(theme_color('#bdd0ce'))
            label=f"多卷合辑 · {len(volumes(entry))} 卷" if entry.get('kind')=='folder' else Path(entry['path']).suffix[1:].upper()
            painter.drawText(QRectF(24,230,162,25),Qt.AlignmentFlag.AlignCenter,label)
            painter.setFont(QFont(FONT_FAMILY,8))
            state='正在提取第一页…' if stamp else '封面源文件缺失'
            if identity in self.thumbnails.failed: state='封面提取失败'
            if not self.thumbnails.enabled: state='C 盘缓存已禁用'
            painter.drawText(QRectF(15,265,180,18),Qt.AlignmentFlag.AlignCenter,state)
        painter.end(); self.cache[key]=pix
        while len(self.cache)>48: self.cache.popitem(last=False)
        return pix


class BookCard(QStyledItemDelegate):
    def __init__(self, shelf): super().__init__(shelf); self.shelf=shelf
    def sizeHint(self, option, index): return QSize(206,344)
    def paint(self,painter,option,index):
        entry=self.shelf.catalog.get(index.data(Qt.ItemDataRole.UserRole))
        if not entry: return
        painter.save(); painter.setRenderHint(QPainter.RenderHint.Antialiasing); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect=QRectF(option.rect).adjusted(6,6,-6,-6)
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        hovered=bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(0,0,0,36))
        painter.drawRoundedRect(rect.translated(0,4),14,14)
        painter.setPen(theme_color('#90b69e') if selected else theme_color('#3e5049' if hovered else '#303d3c'))
        painter.setBrush(theme_color('#2c4036') if selected else theme_color('#293735' if hovered else '#222d2f'))
        painter.drawRoundedRect(rect,14,14)
        cover=QRectF(rect.left()+12,rect.top()+12,rect.width()-24,230)
        clip=QPainterPath(); clip.addRoundedRect(cover,8,8); painter.save(); painter.setClipPath(clip)
        painter.drawPixmap(cover,self.shelf.covers.get(entry),QRectF(0,0,210,300))
        painter.restore()
        badge=f"{len(volumes(entry))} 卷" if entry.get('kind')=='folder' else Path(entry['path']).suffix[1:].upper()
        painter.setFont(QFont(FONT_FAMILY,8))
        bw=painter.fontMetrics().horizontalAdvance(badge)+18
        badge_rect=QRectF(cover.left()+8,cover.top()+8,bw,23)
        badge_color=theme_color('#17211d'); badge_color.setAlpha(222)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(badge_color); painter.drawRoundedRect(badge_rect,6,6)
        painter.setPen(theme_color('#e2eadc')); painter.drawText(badge_rect,Qt.AlignmentFlag.AlignCenter,badge)
        painter.setPen(theme_color('#e3e9df')); painter.setFont(QFont(FONT_FAMILY,10,QFont.Weight.DemiBold))
        title=entry['title']; title=title if len(title)<45 else title[:44]+'…'
        painter.drawText(QRectF(rect.left()+12,cover.bottom()+10,rect.width()-24,43),Qt.TextFlag.TextWordWrap,title)
        painter.setFont(QFont(FONT_FAMILY,8)); painter.setPen(theme_color('#9bad9f'))
        label=reading_status(entry)
        if entry.get('reading_seconds',0)>0: label+='  ·  '+duration(entry['reading_seconds'])
        label=painter.fontMetrics().elidedText(label,Qt.TextElideMode.ElideRight,int(rect.width()-24))
        painter.drawText(QRectF(rect.left()+12,rect.bottom()-31,rect.width()-24,20),Qt.AlignmentFlag.AlignLeft,label)
        children=volumes(entry)
        total=sum(v.get('total',0) for v in children) if all(v.get('total') for v in children) else 0
        read=sum(min(v.get('page',0)+1,v.get('total',0)) for v in children if v.get('last_read'))
        if total:
            bar=QRectF(rect.left()+12,rect.bottom()-9,rect.width()-24,3)
            painter.fillRect(bar,theme_color('#3c4b45'))
            painter.fillRect(QRectF(bar.left(),bar.top(),bar.width()*min(1,read/total),3),theme_color('#9cc3aa'))
        painter.restore()


class LibraryPage(QWidget):
    read_requested=Signal(object,object)
    import_files_requested=Signal()
    import_folder_requested=Signal()
    batch_import_requested=Signal()
    resume_requested=Signal()
    changed=Signal()
    removing=Signal(str)
    relocating=Signal(str)
    theme_changed=Signal(str)
    stats_requested=Signal()
    PAGE_SIZE=48

    def __init__(self, library, runtime_root, parent=None):
        super().__init__(parent)
        self.library=library; self.covers=Covers(runtime_root,self); self.catalog={}; self.page=0; self.detail_id=None
        layout=QVBoxLayout(self); layout.setContentsMargins(32,26,32,20); layout.setSpacing(18)
        header=QHBoxLayout()
        brand=QVBoxLayout(); brand.setSpacing(5)
        eyebrow=QLabel('MIGI  /  右页'); eyebrow.setObjectName('eyebrow'); brand.addWidget(eyebrow)
        heading=QLabel('我的书库'); heading.setStyleSheet('font-size:28px; font-weight:600; color:#e6eddf;'); brand.addWidget(heading)
        header.addLayout(brand); header.addStretch(); header.setSpacing(12)
        self.theme_combo=QComboBox()
        for key,(title,_,__) in THEMES.items(): self.theme_combo.addItem(title,key)
        self.theme_combo.setToolTip('切换整个阅读器配色')
        self.theme_combo.currentIndexChanged.connect(lambda:self.theme_changed.emit(self.theme_combo.currentData()))
        header.addWidget(self.theme_combo)
        for text,signal in [('＋ 批量导入',self.batch_import_requested),('＋ 独立图书',self.import_files_requested),('＋ 导入文件夹',self.import_folder_requested),('返回阅读  F6',self.resume_requested)]:
            button=QPushButton(text); button.clicked.connect(lambda checked=False,target=signal:target.emit())
            primary=text=='＋ 批量导入'
            button_role(button,'primary' if primary else 'quiet')
            button.setIcon(icon('folder' if text=='＋ 导入文件夹' else 'book','#1c392b' if primary else '#b9cdc1'))
            if text=='＋ 独立图书': button.setToolTip('可用 Command / Shift 一次选择多个图书文件' if sys.platform=='darwin' else '可用 Ctrl / Shift 一次选择多个图书文件')
            header.addWidget(button)
        layout.addLayout(header)
        stats=QHBoxLayout(); self.reading_total=QPushButton(); self.reading_total.setObjectName('metric')
        self.reading_total.setToolTip('查看每日阅读统计'); self.reading_total.clicked.connect(self.stats_requested)
        stats.addWidget(self.reading_total); stats.addStretch()
        self.cache_info=QLabel(); self.cache_info.setObjectName('muted'); stats.addWidget(self.cache_info)
        clear_cache=QPushButton('清理封面缓存'); button_role(clear_cache,'quiet'); clear_cache.clicked.connect(self.clear_cache); stats.addWidget(clear_cache)
        layout.addLayout(stats)
        self.stack=QStackedWidget(); layout.addWidget(self.stack,1)
        browse=QWidget(); bl=QVBoxLayout(browse); bl.setContentsMargins(0,0,0,0); bl.setSpacing(14)
        filters=QHBoxLayout()
        self.search=QLineEdit(); self.search.setPlaceholderText('搜索书名、分卷或路径…'); self.search.textChanged.connect(self.reset_page)
        self.search.addAction(icon('search'),QLineEdit.ActionPosition.LeadingPosition)
        self.kind=QComboBox(); self.kind.addItems(['全部书籍','多卷合辑','独立图书']); self.kind.currentIndexChanged.connect(self.reset_page)
        self.status_filter=QComboBox(); self.status_filter.addItem('全部状态',None)
        self.status_filter.currentIndexChanged.connect(self.reset_page)
        self.sort=QComboBox(); self.sort.addItems(['最近阅读','书名顺序','最近导入']); self.sort.currentIndexChanged.connect(self.reset_page)
        filters.addWidget(self.search,1); filters.addWidget(self.kind); filters.addWidget(self.status_filter); filters.addWidget(self.sort); bl.addLayout(filters)
        self.summary=QLabel(); self.summary.setObjectName('muted'); bl.addWidget(self.summary)
        self.grid=BookGrid(); self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setResizeMode(QListView.ResizeMode.Adjust); self.grid.setMovement(QListView.Movement.Static)
        self.grid.setWrapping(True); self.grid.setSpacing(12); self.grid.setGridSize(QSize(214,352)); self.grid.setMouseTracking(True)
        self.grid.setUniformItemSizes(True); self.grid.setItemDelegate(BookCard(self))
        self.grid.scroll_motion=SmoothScroll(self.grid)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.grid.customContextMenuRequested.connect(self.book_context_menu)
        self.grid.setStyleSheet('QListWidget {background:transparent; border:0;} QListWidget::item {padding:0; margin:0; border:0;}')
        self.grid.itemDoubleClicked.connect(self.open_item); self.grid.itemActivated.connect(self.open_item); bl.addWidget(self.grid,1)
        self.empty=QLabel('书库还没有图书。导入独立文件，或将多卷文件夹合为一本书。')
        self.empty.setWordWrap(True); bl.addWidget(self.empty)
        footer=QHBoxLayout()
        self.prev=QPushButton('上一页'); self.prev.clicked.connect(lambda:self.navigate(-1))
        self.next=QPushButton('下一页'); self.next.clicked.connect(lambda:self.navigate(1))
        self.paging=QLabel(); details=QPushButton('查看所选书籍'); details.clicked.connect(lambda:self.open_item(self.grid.currentItem()))
        footer.addWidget(self.prev); footer.addWidget(self.paging); footer.addWidget(self.next); footer.addStretch(); footer.addWidget(details)
        bl.addLayout(footer); self.stack.addWidget(browse)
        detail=QWidget(); dl=QVBoxLayout(detail); dl.setContentsMargins(0,0,0,0); dl.setSpacing(16)
        back=QPushButton('← 返回全部书籍'); button_role(back,'quiet'); back.clicked.connect(self.show_grid); back.setMaximumWidth(180); dl.addWidget(back)
        top=QHBoxLayout(); top.setSpacing(26)
        self.cover=QLabel(); self.cover.setFixedSize(196,280); top.addWidget(self.cover,0,Qt.AlignmentFlag.AlignTop)
        info=QVBoxLayout(); info.setSpacing(12)
        self.title=QLineEdit(); self.title.setStyleSheet('QLineEdit {font-size:26px; font-weight:600; background:transparent; border:1px solid transparent; padding:5px 8px;} QLineEdit:hover {border-color:#41514a;} QLineEdit:focus {background:#26342f; border-color:#91b79e;}'); self.title.editingFinished.connect(self.rename)
        info.addWidget(self.title)
        self.description=QLabel(); info.addWidget(self.description)
        status_row=QHBoxLayout(); status_row.addWidget(QLabel('阅读状态'))
        self.status_combo=QComboBox(); self.status_combo.setEditable(True); self.status_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.status_combo.lineEdit().setMaxLength(30); self.status_combo.setMinimumWidth(180)
        self.status_combo.setToolTip('可选择预设，或输入自定义状态后按 Enter 保存；不随阅读进度自动改变')
        self.status_combo.textActivated.connect(self.set_detail_status)
        self.status_combo.lineEdit().editingFinished.connect(lambda:self.set_detail_status(self.status_combo.currentText()))
        status_row.addWidget(self.status_combo); status_row.addStretch(); info.addLayout(status_row)
        self.book_time=QPushButton(); self.book_time.setObjectName('metric'); self.book_time.clicked.connect(self.stats_requested)
        self.book_time.setToolTip('查看每日阅读统计'); info.addWidget(self.book_time,0,Qt.AlignmentFlag.AlignLeft)
        self.path=ElidedLabel(); self.path.setObjectName('muted'); self.path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); info.addWidget(self.path)
        actions=QHBoxLayout()
        self.continue_btn=QPushButton('继续阅读'); self.continue_btn.setIcon(icon('book','#1c392b')); button_role(self.continue_btn,'primary'); self.continue_btn.clicked.connect(self.read_current); actions.addWidget(self.continue_btn)
        change=QPushButton('更换封面'); change.clicked.connect(self.choose_cover); actions.addWidget(change)
        reset=QPushButton('重置封面'); reset.clicked.connect(self.reset_cover); actions.addWidget(reset); actions.addStretch(); info.addLayout(actions)
        actions2=QHBoxLayout()
        self.rescan_btn=QPushButton('扫描新增卷'); button_role(self.rescan_btn,'quiet'); self.rescan_btn.clicked.connect(self.rescan); actions2.addWidget(self.rescan_btn)
        location=QPushButton('重新定位'); button_role(location,'quiet'); location.clicked.connect(self.relocate); actions2.addWidget(location)
        remove=QPushButton('移出书库'); button_role(remove,'danger'); remove.clicked.connect(self.remove_entry); actions2.addWidget(remove); actions2.addStretch(); info.addLayout(actions2)
        self.cover_note=ElidedLabel(); self.cover_note.setObjectName('muted'); info.addWidget(self.cover_note)
        info.addStretch(); top.addLayout(info,1); dl.addLayout(top)
        row=QHBoxLayout(); row.addWidget(QLabel('分卷目录'))
        self.volume_search=QLineEdit(); self.volume_search.setPlaceholderText('筛选分卷…'); self.volume_search.textChanged.connect(self.filter_volumes); row.addWidget(self.volume_search,1)
        self.up=QPushButton('上移'); self.up.clicked.connect(lambda:self.move_volume(-1)); row.addWidget(self.up)
        self.down=QPushButton('下移'); self.down.clicked.connect(lambda:self.move_volume(1)); row.addWidget(self.down)
        self.use_volume_cover=QPushButton('所选卷设为封面'); self.use_volume_cover.clicked.connect(self.choose_volume_cover); row.addWidget(self.use_volume_cover)
        open_volume=QPushButton('阅读所选卷'); open_volume.clicked.connect(self.read_selected); row.addWidget(open_volume); dl.addLayout(row)
        self.volume_list=QTreeWidget(); self.volume_list.setColumnCount(5); self.volume_list.setHeaderLabels(['卷名','格式','阅读进度','阅读时长','阅读状态'])
        self.volume_list.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.volume_list.setColumnWidth(1,90); self.volume_list.setColumnWidth(2,170)
        self.volume_list.setColumnWidth(3,115)
        self.volume_list.setColumnWidth(4,120)
        self.volume_list.setRootIsDecorated(False); self.volume_list.setUniformRowHeights(True)
        self.volume_list.setAlternatingRowColors(True)
        self.volume_list.scroll_motion=SmoothScroll(self.volume_list)
        self.volume_list.itemDoubleClicked.connect(lambda *args:self.read_selected()); dl.addWidget(self.volume_list,1)
        self.volume_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.volume_list.customContextMenuRequested.connect(self.volume_context_menu)
        self.stack.addWidget(detail)
        self.covers.thumbnails.ready.connect(self.cover_ready)
        self.refresh()

    def cover_ready(self):
        self.grid.viewport().update()
        entry=self.current()
        if entry and self.stack.currentIndex()==1:
            self.cover.setPixmap(self.covers.get(entry).scaled(self.cover.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.update_stats()

    def update_stats(self):
        total=self.library.data.get('stats',{}).get('total_reading_seconds',0)
        self.reading_total.setText('累计阅读  '+duration(total))
        entry=self.current()
        if entry: self.book_time.setText('本书累计阅读  '+duration(entry.get('reading_seconds',0)))
        root=self.covers.thumbnails.root
        self.cache_info.setText(f'封面缓存 · {self.covers.thumbnails.size()/1048576:.1f} MB' if self.covers.thumbnails.enabled else 'C 盘缓存已禁用')
        self.cache_info.setToolTip('缓存目录：'+str(root))

    def clear_cache(self):
        try:
            self.covers.thumbnails.clear(); self.covers.cache.clear()
            self.grid.viewport().update(); self.update_stats()
        except OSError as error: QMessageBox.warning(self,'清理失败',str(error))

    def reset_page(self,*args): self.page=0; self.refresh()
    def navigate(self,step): self.page+=step; self.refresh()

    def refresh(self):
        self.grid.scroll_motion.stop(); self.covers.invalidate()
        self.catalog={b['id']:b for b in self.library.data['books']}
        previous=self.status_filter.currentData()
        self.status_filter.blockSignals(True); self.status_filter.clear(); self.status_filter.addItem('全部状态',None)
        for status in self.status_labels(): self.status_filter.addItem(status,status)
        index=self.status_filter.findData(previous)
        self.status_filter.setCurrentIndex(index if index>=0 else 0); self.status_filter.blockSignals(False)
        term=self.search.text().strip().casefold(); kind=self.kind.currentIndex()
        entries=[]
        for entry in self.catalog.values():
            grouped=entry.get('kind')=='folder'
            if (kind==1 and not grouped) or (kind==2 and grouped): continue
            if self.status_filter.currentData() and reading_status(entry)!=self.status_filter.currentData(): continue
            if term and term not in (entry['title']+' '+entry['path']+' '+' '.join(v['title'] for v in volumes(entry))).casefold(): continue
            entries.append(entry)
        if self.sort.currentIndex()==1: entries.sort(key=lambda e:natural_key(e['title']))
        else:
            field='last_read' if self.sort.currentIndex()==0 else 'added'
            entries.sort(key=lambda e:(-e.get(field,0),natural_key(e['title'])))
        pages=max(1,math.ceil(len(entries)/self.PAGE_SIZE)); self.page=max(0,min(self.page,pages-1))
        desired=entries[self.page*self.PAGE_SIZE:(self.page+1)*self.PAGE_SIZE]
        current_ids=[self.grid.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.grid.count())]
        desired_ids=[entry['id'] for entry in desired]
        if current_ids!=desired_ids:
            # Remove rows through model notifications instead of resetting the
            # entire native accessibility table, whose Cocoa cells may be cached.
            while self.grid.count(): self.grid.takeItem(self.grid.count()-1)
            for entry in desired:
                item=QListWidgetItem(entry['title']); item.setData(Qt.ItemDataRole.UserRole,entry['id']); self.grid.addItem(item)
        for i,entry in enumerate(desired):
            item=self.grid.item(i); item.setText(entry['title']); item.setData(Qt.ItemDataRole.UserRole,entry['id']); item.setToolTip(entry['title']+'\n阅读状态：'+reading_status(entry)+'\n'+entry['path'])
            item.setSizeHint(QSize(206,344))
        total=len(self.catalog); files=sum(len(volumes(e)) for e in self.catalog.values())
        self.summary.setText(f'{total} 本书 · {files} 个卷文件    /    当前筛选 {len(entries)} 本')
        self.empty.setVisible(not entries)
        self.empty.setText('没有匹配的书籍，请调整搜索或筛选。' if total else '书库还没有图书。导入独立文件，或将多卷文件夹合为一本书。')
        self.paging.setText(f'{self.page+1} / {pages} 页 · 每页 {self.PAGE_SIZE} 本')
        self.prev.setEnabled(self.page>0); self.next.setEnabled(self.page+1<pages)
        self.update_stats()
        if self.detail_id and self.detail_id in self.catalog and self.stack.currentIndex()==1: self.show_detail(self.catalog[self.detail_id])

    def show_grid(self): self.stack.setCurrentIndex(0); self.refresh()
    def open_item(self,item):
        if item:
            entry=self.library.find(item.data(Qt.ItemDataRole.UserRole))
            if entry: self.show_detail(entry)

    def current(self): return self.library.find(self.detail_id)
    def show_detail(self,entry):
        switching=self.detail_id!=entry['id']
        if switching: self.volume_search.clear()
        selected=(None if switching else self.selected_volume_path()) or entry.get('current_volume')
        self.detail_id=entry['id']; self.stack.setCurrentIndex(1)
        self.title.setText(entry['title']); self.path.setText(entry['path']); self.path.setToolTip(entry['path'])
        self.status_combo.blockSignals(True); self.status_combo.clear(); self.status_combo.addItems(self.status_labels())
        self.status_combo.setCurrentText(reading_status(entry)); self.status_combo.blockSignals(False)
        self.cover.setPixmap(self.covers.get(entry).scaled(self.cover.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        grouped=entry.get('kind')=='folder'; self.rescan_btn.setVisible(grouped); self.up.setVisible(grouped); self.down.setVisible(grouped); self.use_volume_cover.setVisible(grouped)
        self.description.setText(f"多卷合辑 · {len(volumes(entry))} 卷 · 每卷独立记忆进度" if grouped else '独立图书 · 单个文件')
        source,kind=cover_source(entry)
        self.cover_note.setText(('自选图片：' if kind=='image' else '第一页封面来源：')+source+('（源文件缺失）' if not source or not Path(source).is_file() else ''))
        self.cover_note.setToolTip(self.cover_note.text())
        self.update_stats()
        self.volume_list.clear()
        for volume in volumes(entry):
            missing=not Path(volume['path']).is_file()
            progress=f"第 {volume.get('page',0)+1} 页" if volume.get('last_read') or volume.get('page',0)>0 else '未开始'
            if volume.get('total'): progress+=f" / {volume['total']} 页"
            item=QTreeWidgetItem([('⚠ ' if missing else '')+volume['title'],Path(volume['path']).suffix[1:].upper(),'文件缺失' if missing else progress,duration(volume.get('reading_seconds',0)),reading_status(volume)])
            item.setToolTip(4,reading_status(volume)+'（右键可修改）')
            item.setData(0,Qt.ItemDataRole.UserRole,volume['path']); item.setToolTip(0,volume['path']); self.volume_list.addTopLevelItem(item)
            if volume['path']==selected: self.volume_list.setCurrentItem(item)
        if not self.volume_list.currentItem() and self.volume_list.topLevelItemCount(): self.volume_list.setCurrentItem(self.volume_list.topLevelItem(0))
        self.filter_volumes()

    def filter_volumes(self,*args):
        term=self.volume_search.text().casefold()
        visible=[]
        for i in range(self.volume_list.topLevelItemCount()):
            item=self.volume_list.topLevelItem(i); item.setHidden(term not in item.text(0).casefold())
            if not item.isHidden(): visible.append(item)
        selected=self.volume_list.currentItem()
        if selected and selected.isHidden(): self.volume_list.setCurrentItem(visible[0] if visible else None)

    def selected_volume_path(self):
        item=self.volume_list.currentItem()
        return item.data(0,Qt.ItemDataRole.UserRole) if item else None

    def read_selected(self):
        entry=self.current(); path=self.selected_volume_path()
        if entry and path: self.read_requested.emit(entry,path)

    def read_current(self):
        entry=self.current()
        if entry: self.read_requested.emit(entry,None)

    def status_labels(self):
        custom={reading_status(item) for book in self.library.data['books'] for item in [book]+volumes(book)}
        return list(READING_STATUSES)+sorted(custom-set(READING_STATUSES),key=natural_key)

    def set_detail_status(self,status):
        entry=self.current()
        if not entry or reading_status(entry)==(status.strip() or '未标记'): return
        try: self.library.set_reading_status(entry,status); self.changed.emit()
        except ValueError as error: QMessageBox.warning(self,'状态保存失败',str(error))

    def mark_books(self,entry_ids,status):
        entries=[self.library.find(entry_id) for entry_id in entry_ids]
        entries=[entry for entry in entries if entry]
        try:
            for entry in entries: self.library.set_reading_status(entry,status,save=False)
            if entries: self.library.save(); self.changed.emit()
        except ValueError as error: QMessageBox.warning(self,'状态保存失败',str(error))

    def status_menu(self,position,entries,apply):
        menu=QMenu(self); menu.setTitle('标记阅读状态')
        for status in READING_STATUSES:
            action=menu.addAction(status); action.setCheckable(True)
            action.setChecked(all(reading_status(entry)==status for entry in entries))
            action.triggered.connect(lambda checked=False,value=status:apply(value))
        menu.addSeparator(); custom=menu.addAction('自定义状态…')
        def choose_custom():
            value,ok=QInputDialog.getText(self,'自定义阅读状态','状态名称（最多 30 个字）：',text=reading_status(entries[0]) if len(entries)==1 else '')
            if ok: apply(value)
        custom.triggered.connect(choose_custom)
        menu.exec(position)

    def book_context_menu(self,position):
        item=self.grid.itemAt(position)
        if not item: return
        if not item.isSelected(): self.grid.clearSelection(); item.setSelected(True)
        ids=[item.data(Qt.ItemDataRole.UserRole) for item in self.grid.selectedItems()]
        entries=[self.library.find(entry_id) for entry_id in ids]
        self.status_menu(self.grid.viewport().mapToGlobal(position),entries,lambda value:self.mark_books(ids,value))

    def volume_context_menu(self,position):
        owner=self.current(); item=self.volume_list.itemAt(position)
        if not owner or not item: return
        self.volume_list.setCurrentItem(item)
        entry=next((v for v in volumes(owner) if v['path']==item.data(0,Qt.ItemDataRole.UserRole)),None)
        if not entry: return
        def apply(value):
            try: self.library.set_reading_status(entry,value); self.changed.emit()
            except ValueError as error: QMessageBox.warning(self,'状态保存失败',str(error))
        self.status_menu(self.volume_list.viewport().mapToGlobal(position),[entry],apply)

    def rename(self):
        entry=self.current(); title=self.title.text().strip()
        if entry and title and title!=entry['title']:
            entry['title']=title; entry['title_custom']=True; self.library.save(); self.changed.emit()

    def choose_cover(self):
        entry=self.current()
        if not entry: return
        path,_=QFileDialog.getOpenFileName(self,'选择本地封面图片','','图片 (*.jpg *.jpeg *.png *.webp *.bmp *.gif)')
        restore_after_native_dialog(self)
        if path:
            try: self.library.set_cover(entry,path); self.show_detail(entry); self.changed.emit()
            except Exception as error: QMessageBox.warning(self,'封面设置失败',str(error))

    def reset_cover(self):
        entry=self.current()
        if entry: self.library.set_cover(entry); self.show_detail(entry); self.changed.emit()

    def choose_volume_cover(self):
        entry=self.current(); path=self.selected_volume_path()
        if entry and path:
            self.library.set_cover_volume(entry,path); self.show_detail(entry); self.changed.emit()

    def rescan(self):
        entry=self.current()
        if not entry: return
        try:
            count=self.library.rescan(entry); self.show_detail(entry); self.changed.emit()
            QMessageBox.information(self,'扫描完成',f'新增 {count} 卷。已有顺序和阅读进度保留；缺失文件仍保留记录。')
        except Exception as error: QMessageBox.warning(self,'扫描失败',str(error))

    def move_volume(self,step):
        entry=self.current(); path=self.selected_volume_path()
        if not entry or entry.get('kind')!='folder' or not path: return
        children=entry['volumes']; index=next((i for i,v in enumerate(children) if v['path']==path),-1)
        other=index+step
        if index>=0 and 0<=other<len(children):
            children[index],children[other]=children[other],children[index]
            entry['manual_order']=True; self.library.save(); self.show_detail(entry); self.changed.emit()

    def relocate(self):
        entry=self.current()
        if not entry: return
        path=QFileDialog.getExistingDirectory(self,'重新定位合辑文件夹') if entry.get('kind')=='folder' else QFileDialog.getOpenFileName(self,'重新定位图书','','图书 (*.pdf *.epub *.mobi)')[0]
        restore_after_native_dialog(self)
        if not path: return
        try:
            resolved=str(Path(path).resolve())
            if any(b['id']!=entry['id'] and b.get('kind')==entry.get('kind') and str(Path(b['path']).resolve()).casefold()==resolved.casefold() for b in self.library.data['books']):
                raise ValueError('该路径已存在同类型书库记录，请选择其他位置。')
            self.relocating.emit(entry['id'])
            if entry.get('kind')=='folder': self.library.rescan(entry,path)
            else: entry['path']=str(Path(path).resolve()); self.library.save()
            self.show_detail(entry); self.changed.emit()
        except Exception as error: QMessageBox.warning(self,'定位失败',str(error))

    def remove_entry(self):
        entry=self.current()
        if not entry: return
        self.removing.emit(entry['id'])
        self.library.data['books'].remove(entry); self.library.save(); self.detail_id=None
        self.show_grid(); self.changed.emit()
