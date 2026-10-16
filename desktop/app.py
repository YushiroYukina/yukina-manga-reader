import os
import sys
import time
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QEvent, QRectF, QPoint, QLockFile
from PySide6.QtGui import QPainter, QColor, QKeySequence, QShortcut, QFont, QCursor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QLineEdit, QFileDialog, QMessageBox, QComboBox,
    QSpinBox, QCheckBox, QSplitter, QScrollArea, QStackedWidget, QDialog)
from reader import Book, Library, FORMATS, spread, volumes
from canvas import Canvas, PageTurn
from library_ui import LibraryPage, FolderImportDialog
from reading_time import ReadingTracker,duration
from batch_import import BatchImportDialog
from completion import CompletionPrompts
from reading_stats import ReadingStatsPage
from ui_theme import stylesheet,install_theme,button_role,icon,ElidedLabel,THEMES,themed_css,theme_color

ROOT = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent

class Window(QMainWindow):
    def __init__(self, library=None, runtime_root=None):
        super().__init__()
        self.library = library or Library(ROOT / 'data' / 'library.json')
        self.runtime_root=Path(runtime_root or ROOT).resolve()
        self.reading_tracker=ReadingTracker(self.library)
        self.book = self.entry = None
        self.active_book = None
        self.page = 0
        self.immersive = False
        self.immersive_controls = False
        self.was_fullscreen = False
        self._startup_placed = False
        self._startup_screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        self.setWindowTitle('yukina漫画阅读器')
        self.resize(1440, 960)
        self.setAcceptDrops(True)
        install_theme(QApplication.instance(),self.library.data['settings'].get('theme','sage'))
        self.setStyleSheet(stylesheet(self.library.data['settings'].get('theme','sage')))
        split = self.split = QWidget()
        self.pages = QStackedWidget(); self.setCentralWidget(self.pages); self.pages.addWidget(split)
        pane = split; layout = self.reader_layout = QVBoxLayout(pane)
        layout.setContentsMargins(18, 12, 18, 12); layout.setSpacing(12)
        self.header = QWidget(); header_layout = QHBoxLayout(self.header); header_layout.setContentsMargins(0,0,0,0)
        self.library_button=QPushButton('书库  F6'); self.library_button.clicked.connect(self.show_library); self.library_button.setIcon(icon('library')); button_role(self.library_button,'quiet'); header_layout.addWidget(self.library_button)
        self.heading = ElidedLabel('开始一段新的阅读'); self.heading.setStyleSheet('font-size:20px; font-weight:600;')
        self.heading.setWordWrap(False)
        header_layout.addWidget(self.heading,1)
        self.reading_clock=QPushButton('本书 00:00:00'); button_role(self.reading_clock,'quiet')
        self.reading_clock.setToolTip('查看每日阅读统计'); self.reading_clock.clicked.connect(self.show_stats)
        header_layout.addWidget(self.reading_clock)
        self.pause_timer=QPushButton('暂停计时'); self.pause_timer.setCheckable(True); self.pause_timer.toggled.connect(self.sync_reading_time)
        button_role(self.pause_timer,'quiet'); header_layout.addWidget(self.pause_timer)
        self.directory_btn=QPushButton('分卷目录'); self.directory_btn.clicked.connect(self.show_active_detail); self.directory_btn.setIcon(icon('book')); button_role(self.directory_btn,'quiet'); header_layout.addWidget(self.directory_btn)
        self.immersive_btn = QPushButton('沉浸阅读  Tab'); self.immersive_btn.clicked.connect(self.toggle_immersive)
        self.immersive_btn.setIcon(icon('focus','#1c392a')); button_role(self.immersive_btn,'primary'); header_layout.addWidget(self.immersive_btn)
        layout.addWidget(self.header)
        self.toolbar = QWidget(); self.toolbar.setObjectName("controlBar"); bar = QHBoxLayout(self.toolbar); bar.setContentsMargins(12,8,12,8); bar.setSpacing(12)
        self.direction = QComboBox(); self.direction.addItems(['日漫 · 右 → 左', '左 → 右'])
        self.double = QCheckBox('双页'); self.double.setChecked(True)
        self.cover = QCheckBox('封面单页'); self.cover.setChecked(True)
        self.fit = QComboBox(); self.fit.addItems(['适合窗口', '适合宽度', '原始大小'])
        self.zoom = QComboBox(); self.zoom.addItems(['75%', '100%', '125%', '150%', '200%']); self.zoom.setCurrentIndex(1)
        for widget in [self.direction, self.double, self.cover, self.fit, self.zoom]:
            bar.addWidget(widget)
        bar.addStretch()
        self.settings_btn = QPushButton('阅读外观'); self.settings_btn.setCheckable(True); self.settings_btn.clicked.connect(self.toggle_appearance); self.settings_btn.setIcon(icon('settings')); button_role(self.settings_btn,'quiet'); bar.addWidget(self.settings_btn)
        fullscreen = QPushButton('全屏 F11'); fullscreen.clicked.connect(self.fullscreen); bar.addWidget(fullscreen)
        layout.addWidget(self.toolbar)
        self.appearance = QWidget(); self.appearance.setObjectName("controlBar"); appearance = QHBoxLayout(self.appearance); appearance.setContentsMargins(14,8,14,8)
        appearance.addWidget(QLabel('页间距'))
        self.gap = QSpinBox(); self.gap.setRange(0,64); self.gap.setSingleStep(4); self.gap.setSuffix(' px'); self.gap.setValue(24)
        self.gap.setToolTip('双页之间的留白；0 px 可拼接跨页画面')
        appearance.addWidget(self.gap)
        appearance.addSpacing(16); appearance.addWidget(QLabel('翻页效果'))
        self.motion = QComboBox()
        for label,key in [('书籍翻页','book'),('无动画','none'),('平移','slide'),('覆盖','cover'),('淡入淡出','fade')]: self.motion.addItem(label,key)
        appearance.addWidget(self.motion)
        self.speed = QComboBox(); self.speed.addItem('轻快 · 260 ms',260); self.speed.addItem('自然 · 420 ms',420); self.speed.addItem('舒缓 · 650 ms',650); self.speed.setCurrentIndex(1)
        appearance.addWidget(self.speed); appearance.addStretch()
        appearance.addWidget(QLabel('主题'))
        self.theme_combo=QComboBox()
        for key,(title,_,__) in THEMES.items(): self.theme_combo.addItem(title,key)
        appearance.addWidget(self.theme_combo)
        layout.addWidget(self.appearance); self.appearance.hide()
        self.canvas = Canvas(); self.canvas.turn.connect(self.turn)
        self.canvas.exit_immersive.connect(self.exit_immersive)
        self.canvas.center_clicked.connect(self.toggle_immersive_controls)
        self.canvas.setMouseTracking(True); self.canvas.installEventFilter(self)
        self.scroll = QScrollArea(); self.scroll.setWidget(self.canvas); self.scroll.setWidgetResizable(True)
        self.reading_viewport = self.scroll.viewport()
        self.reading_viewport.installEventFilter(self)
        self.page_turn = PageTurn(self.reading_viewport)
        layout.addWidget(self.scroll, 1)
        self.navigation = QWidget(); nav = QHBoxLayout(self.navigation); nav.setContentsMargins(0,0,0,0)
        self.prev_volume=QPushButton('上一卷'); self.prev_volume.clicked.connect(lambda:self.change_volume(-1))
        self.next_volume=QPushButton('下一卷'); self.next_volume.clicked.connect(lambda:self.change_volume(1))
        self.next_btn = QPushButton('← 下一页'); self.next_btn.clicked.connect(lambda: self.turn(1))
        self.prev_btn = QPushButton('上一页 →'); self.prev_btn.clicked.connect(lambda: self.turn(-1))
        self.counter = QLabel('未打开图书')
        self.jump = QSpinBox(); self.jump.setRange(1, 1); self.jump.setPrefix('第 '); self.jump.setSuffix(' 页'); self.jump.editingFinished.connect(self.jump_page)
        button_role(self.next_btn,'primary'); button_role(self.prev_btn,'quiet'); button_role(self.prev_volume,'quiet'); button_role(self.next_volume,'quiet'); nav.addWidget(self.next_btn); nav.addWidget(self.next_volume); nav.addStretch(); nav.addWidget(self.counter); nav.addWidget(self.jump); nav.addStretch(); nav.addWidget(self.prev_volume); nav.addWidget(self.prev_btn)
        self.prev_volume.hide(); self.next_volume.hide()
        layout.addWidget(self.navigation)
        self.immersive_top=QWidget(self.split); self.immersive_top.setObjectName('controlBar')
        self.immersive_bottom=QWidget(self.split); self.immersive_bottom.setObjectName('controlBar')
        for panel in (self.immersive_top,self.immersive_bottom):
            panel_layout=QVBoxLayout(panel); panel_layout.setContentsMargins(14,12,14,12); panel_layout.setSpacing(10)
            panel.hide()
        self.statusBar().showMessage('← / → 翻页 · 空格 下一页 · Tab 沉浸阅读 · Esc / 右键退出沉浸 · F11 全屏')
        settings = self.library.data['settings']
        self.direction.setCurrentIndex(settings.get('direction', 0))
        self.double.setChecked(settings.get('double', True)); self.cover.setChecked(settings.get('cover', True))
        self.gap.setValue(settings.get('gap',24)); self.motion.setCurrentIndex(settings.get('motion',0)); self.speed.setCurrentIndex(settings.get('speed',1))
        self.fit.setCurrentIndex(settings.get('fit',0)); self.zoom.setCurrentIndex(settings.get('zoom',1))
        for widget in [self.direction, self.fit, self.zoom, self.motion, self.speed]: widget.currentIndexChanged.connect(self.options)
        self.gap.valueChanged.connect(self.options)
        for widget in [self.double, self.cover]: widget.toggled.connect(self.options)
        self.reader_shortcuts=[]
        for key, fn in [('Left', lambda: self.turn(1 if self.direction.currentIndex()==0 else -1)), ('Right', lambda: self.turn(-1 if self.direction.currentIndex()==0 else 1)), ('Space', lambda: self.turn(1)), ('Home', lambda: self.go(0)), ('End', lambda: self.go(len(self.book)-1) if self.book else None), ('F11', self.fullscreen), ('Escape', self.escape), ('Tab', self.toggle_immersive), ('Ctrl+O', self.import_files), ('F6',self.toggle_library)]:
            shortcut = QShortcut(QKeySequence(key), self); shortcut.activated.connect(fn)
            if key in ('Left','Right','Space','Home','End','Tab'): self.reader_shortcuts.append(shortcut)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.resize_canvas)
        self.cursor_timer = QTimer(self); self.cursor_timer.setSingleShot(True); self.cursor_timer.setInterval(1800)
        self.cursor_timer.timeout.connect(lambda: self.canvas.setCursor(Qt.CursorShape.BlankCursor) if self.immersive and not self.immersive_controls else None)
        self.shelf=LibraryPage(self.library,self.runtime_root)
        self.shelf.read_requested.connect(self.open_entry)
        self.shelf.theme_changed.connect(self.apply_color_scheme)
        self.theme_combo.currentIndexChanged.connect(lambda:self.apply_color_scheme(self.theme_combo.currentData()))
        self.shelf.import_files_requested.connect(self.import_files)
        self.shelf.import_folder_requested.connect(self.import_folder)
        self.shelf.batch_import_requested.connect(self.import_batch)
        self.shelf.resume_requested.connect(self.show_reader)
        self.shelf.changed.connect(self.refresh)
        self.completion=CompletionPrompts(self)
        self.shelf.changed.connect(self.completion.groups_changed)
        self.shelf.removing.connect(self.release_active)
        self.shelf.relocating.connect(self.release_active)
        self.pages.addWidget(self.shelf)
        self.stats_page=ReadingStatsPage(self.library); self.pages.addWidget(self.stats_page)
        self.stats_page.back_requested.connect(self.back_from_stats)
        self.shelf.stats_requested.connect(self.show_stats)
        self.stats_return=self.shelf
        self.reading_tick=QTimer(self); self.reading_tick.setInterval(1000); self.reading_tick.timeout.connect(self.sync_reading_time); self.reading_tick.start()
        QApplication.instance().applicationStateChanged.connect(self.sync_reading_time)
        self.apply_color_scheme(self.library.data['settings'].get('theme','sage'),save=False)
        self.speed.setEnabled(self.motion.currentData()!='none')
        self.refresh()
        self.show_library()

    def place_on_screen(self, screen=None, center=True):
        """Use one screen's logical work area, including its nonzero origin.

        Qt and Windows may use different monitor coordinates under DPI scaling;
        never mix native pixel rectangles with QWidget geometry here.
        """
        if self.isFullScreen() or self.isMaximized(): return
        screen = screen or self.screen() or QApplication.primaryScreen()
        if screen is None: return
        handle = self.windowHandle()
        if handle and handle.screen() is not screen: handle.setScreen(screen)
        available = screen.availableGeometry().adjusted(16,16,-16,-16)
        margins = handle.frameMargins() if handle else None
        frame_w = margins.left()+margins.right() if margins else 16
        frame_h = margins.top()+margins.bottom() if margins else 40
        self.resize(min(1440 if center else self.width(),max(200,available.width()-frame_w)),
                    min(960 if center else self.height(),max(200,available.height()-frame_h)))
        frame = self.frameGeometry()
        if center: frame.moveCenter(available.center())
        x = max(available.left(),min(frame.left(),available.right()-frame.width()+1))
        y = max(available.top(),min(frame.top(),available.bottom()-frame.height()+1))
        self.move(x,y)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._startup_placed:
            self._startup_placed = True
            self.place_on_screen(self._startup_screen)
            # Recheck once the native title bar and DPI transition settle.
            QTimer.singleShot(0,lambda: self.place_on_screen(self._startup_screen))

    def refresh(self):
        if hasattr(self,'shelf'): self.shelf.refresh()

    def apply_color_scheme(self,name,save=True):
        if name not in THEMES: name='sage'
        self.page_turn.finish()
        install_theme(QApplication.instance(),name)
        self.setStyleSheet(stylesheet(name))
        for widget in self.findChildren(QWidget):
            original=widget.property('migiOriginalStyle')
            if original is None and widget.styleSheet():
                original=widget.styleSheet(); widget.setProperty('migiOriginalStyle',original)
            if original: widget.setStyleSheet(themed_css(original,name))
        for combo in (self.theme_combo,self.shelf.theme_combo):
            combo.blockSignals(True); combo.setCurrentIndex(combo.findData(name)); combo.blockSignals(False)
        for widget,key in [(self.library_button,'library'),(self.directory_btn,'book'),(self.immersive_btn,'focus'),(self.settings_btn,'settings'),(self.shelf.continue_btn,'book')]:
            widget.setIcon(icon(key,'#1c392b' if widget.property('role')=='primary' else '#b9cdc1'))
        for widget in self.shelf.findChildren(QPushButton):
            if widget.text() in ('＋ 批量导入','＋ 独立图书','＋ 导入文件夹','返回阅读  F6'):
                widget.setIcon(icon('folder' if widget.text()=='＋ 导入文件夹' else 'book','#1c392b' if widget.property('role')=='primary' else '#b9cdc1'))
        for action in self.shelf.search.actions(): action.setIcon(icon('search'))
        self.canvas.background=theme_color('#101416'); self.canvas.update()
        self.shelf.covers.cache.clear(); self.shelf.grid.viewport().update()
        entry=self.shelf.current()
        if entry and self.shelf.stack.currentIndex()==1: self.shelf.cover_ready()
        if save:
            self.library.data['settings']['theme']=name; self.library.save()

    def show_library(self,entry=None):
        self.reading_tracker.update(False); self.reading_tracker.flush()
        if self.immersive: self.exit_immersive()
        self.page_turn.finish(); self.pages.setCurrentWidget(self.shelf)
        for shortcut in self.reader_shortcuts: shortcut.setEnabled(False)
        self.statusBar().showMessage('双击书籍进入详情 · 支持文件夹合辑与独立图书 · F6 返回阅读')
        if isinstance(entry,dict): self.shelf.show_detail(entry)
        else: self.shelf.show_grid()

    def show_reader(self):
        self.pages.setCurrentWidget(self.split)
        for shortcut in self.reader_shortcuts: shortcut.setEnabled(True)
        self.statusBar().showMessage('← / → 翻页 · 空格 下一页 · Tab 沉浸阅读 · Esc / 右键退出沉浸 · F6 书库')
        self.timer.start(0)
        self.sync_reading_time()

    def show_stats(self):
        if self.pages.currentWidget() is self.stats_page: return
        self.stats_return=self.pages.currentWidget()
        self.reading_tracker.update(False); self.reading_tracker.flush()
        if self.immersive: self.exit_immersive()
        self.page_turn.finish(); self.pages.setCurrentWidget(self.stats_page)
        for shortcut in self.reader_shortcuts: shortcut.setEnabled(False)
        self.stats_page.refresh()
        self.statusBar().showMessage('周／月／年切换 · 点击趋势图查看当天书籍 · Esc 返回')

    def back_from_stats(self):
        if self.stats_return is self.split: self.show_reader()
        else:
            self.pages.setCurrentWidget(self.shelf); self.shelf.update_stats()
            self.statusBar().showMessage('双击书籍进入详情 · F6 返回阅读')

    def reading_active(self):
        if not self.book or self.pages.currentWidget() is not self.split or self.pause_timer.isChecked():
            return False
        if self.immersive:
            return True
        return bool(not self.isMinimized() and self.isActiveWindow()
                    and QApplication.applicationState()==Qt.ApplicationState.ApplicationActive)

    def sync_reading_time(self,*args):
        if not hasattr(self,'shelf'): return
        self.reading_tracker.update(self.reading_active())
        seconds=self.active_book.get('reading_seconds',0) if self.active_book else 0
        state='计时中' if self.reading_tracker.running else '已暂停'
        self.reading_clock.setText(f'本书 {duration(seconds)} · {state}')
        self.pause_timer.setText('继续计时' if self.pause_timer.isChecked() else '暂停计时')
        self.pause_timer.setEnabled(self.book is not None)
        if self.pages.currentWidget() is self.shelf: self.shelf.update_stats()

    def toggle_library(self):
        self.show_library() if self.pages.currentWidget() is self.split else self.show_reader()

    def show_active_detail(self):
        self.show_library(self.active_book)

    def update_volume_buttons(self):
        grouped=bool(self.active_book and self.active_book.get('kind')=='folder')
        self.prev_volume.setVisible(grouped); self.next_volume.setVisible(grouped)
        if grouped:
            children=volumes(self.active_book)
            index=next((i for i,v in enumerate(children) if v is self.entry),0)
            self.prev_volume.setEnabled(index>0); self.next_volume.setEnabled(index<len(children)-1)

    def change_volume(self,step):
        if not self.active_book or self.active_book.get('kind')!='folder': return
        children=volumes(self.active_book)
        index=next((i for i,v in enumerate(children) if v is self.entry),-1)
        if index>=0 and 0<=index+step<len(children): self.open_entry(self.active_book,children[index+step]['path'])

    def release_active(self,entry_id):
        if self.active_book and self.active_book['id']==entry_id:
            self.reading_tracker.stop()
            self.page_turn.finish()
            if self.book: self.book.close()
            self.book=self.entry=self.active_book=None
            self.canvas.set_pages([],True,1,'适合窗口'); self.heading.setText('开始一段新的阅读')
            self.counter.setText('未打开图书'); self.update_volume_buttons()

    def import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, '批量选择图书（Ctrl / Shift 多选）', '', '漫画图书 (*.pdf *.epub *.mobi *.zip *.cbz *.rar *.cbr *.7z *.cb7 *.jpg *.jpeg *.png *.webp *.bmp *.gif)')
        if paths: self.library.add(paths); self.refresh()

    def import_batch(self,initial_paths=None):
        dialog=BatchImportDialog(self)
        if initial_paths: dialog.add_sources(initial_paths)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            report=self.library.import_batch(dialog.sources(),dialog.grouped.isChecked(),dialog.recursive.isChecked())
            self.refresh(); self.show_library()
        except Exception as error:
            QMessageBox.warning(self,'导入失败',str(error)); return
        finally: QApplication.restoreOverrideCursor()
        message=QMessageBox(self); message.setWindowTitle('批量导入完成')
        message.setText(f"新增 {report['added']} 本 · 更新 {report['updated']} 本合辑 · 跳过 {report['skipped']} 项")
        if report['errors']:
            message.setInformativeText(f"有 {len(report['errors'])} 项未能导入，其余已完成。展开详情可查看原因。")
            message.setDetailedText('\n'.join(report['errors']))
        message.exec()

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '选择要导入的图书文件夹')
        if folder: self.add_folder(folder); self.refresh()

    def add_folder(self, folder):
        dialog=FolderImportDialog(folder,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            added=self.library.import_folder(folder,dialog.grouped.isChecked(),dialog.recursive.isChecked(),dialog.title.text())
            self.refresh()
            self.show_library(added[0] if added and dialog.grouped.isChecked() else None)
        except Exception as error: QMessageBox.warning(self,'导入失败',str(error))
        finally: QApplication.restoreOverrideCursor()

    def open_entry(self, entry, volume_path=None):
        self.page_turn.finish()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            owner=entry
            if entry.get('kind')=='folder':
                children=volumes(entry)
                if not children: raise ValueError('该合辑还没有分卷，请扫描新增卷。')
                requested=volume_path or entry.get('current_volume')
                entry=next((v for v in children if v['path']==requested),children[0])
            book = Book(entry['path'])
            page = max(0, min(entry.get('page', 0), len(book)-1))
            # 先确认首页可渲染，失败时保留当前图书。
            book.render(page)
            if self.book: self.book.close()
            self.book, self.entry = book, entry
            self.active_book=owner
            self.reading_tracker.select(owner,entry)
            self.page = page
            if not entry.get('title_custom'): entry['title'] = book.title
            if owner.get('kind')=='folder': owner['current_volume']=entry['path']
            self.heading.setText((owner['title']+' / ' if owner.get('kind')=='folder' else '')+entry['title'])
            self.heading.setToolTip(str(book.path))
            self.jump.setRange(1, len(book))
            self.show_reader(); self.refresh(); self.display(); self.update_volume_buttons()
        except Exception as error:
            if 'book' in locals() and book is not self.book: book.close()
            QMessageBox.warning(self, '无法打开图书', str(error) + '\n\n原文件必须仍位于记录路径；移动后请使用「重新定位文件」。')
        finally: QApplication.restoreOverrideCursor()

    def display(self):
        if not self.book: return False
        indices = spread(self.page, len(self.book), self.double.isChecked(), self.cover.isChecked())
        try:
            images = [self.book.render(i, 1.5) for i in indices]
            self.canvas.set_pages(images, self.direction.currentIndex()==0, int(self.zoom.currentText()[:-1])/100, self.fit.currentText(), self.gap.value())
            self.counter.setText(f'{indices[0]+1}' + (f'–{indices[-1]+1}' if len(indices)>1 else '') + f' / {len(self.book)} 页')
            self.jump.setValue(self.page+1)
            self.entry.update(page=self.page,total=len(self.book),last_read=time.time())
            if self.active_book: self.active_book['last_read']=self.entry['last_read']
            self.library.save()
            self.next_btn.setEnabled(indices[-1] < len(self.book)-1); self.prev_btn.setEnabled(self.page>0)
            self.scroll.verticalScrollBar().setValue(0)
            self.completion.page_changed(self.entry,indices[-1]==len(self.book)-1)
            return True
        except Exception as error:
            QMessageBox.warning(self, '页面读取失败', str(error))
            return False

    def visible_page_bounds(self):
        rects = self.canvas.page_rects()
        if not rects: return QRectF(self.scroll.viewport().rect())
        bounds = QRectF(rects[0])
        for rect in rects[1:]: bounds = bounds.united(rect)
        origin = self.canvas.mapTo(self.scroll.viewport(), QPoint(0,0))
        bounds.translate(origin)
        return bounds.intersected(QRectF(self.scroll.viewport().rect()))

    def go(self, page, animate=False):
        if not self.book: return
        page = max(0, min(page, len(self.book)-1))
        if page == self.page: return
        self.page_turn.finish()
        previous = self.page
        animate = animate and self.motion.currentData()!='none' and bool(self.canvas.pages)
        if animate:
            old = self.scroll.viewport().grab().toImage()
            bounds = self.visible_page_bounds()
            old_count = len(self.canvas.pages)
        self.page = page
        if not self.display():
            self.page = previous
            return
        if animate:
            # Snapshot the visible viewport only, never a full zoomed document.
            self.scroll.widget().updateGeometry()
            new = self.scroll.viewport().grab().toImage()
            bounds = bounds.united(self.visible_page_bounds())
            side = -1 if (page>previous)==(self.direction.currentIndex()==0) else 1
            self.page_turn.start(old, new, bounds, side, self.speed.currentData(), old_count==1 and len(self.canvas.pages)==1,self.motion.currentData())

    def turn(self, step):
        if not self.book: return
        if step>0:
            current = spread(self.page, len(self.book), self.double.isChecked(), self.cover.isChecked())
            if current[-1] == len(self.book)-1: return
            self.go(current[-1]+1, animate=True)
        else:
            amount = 2 if self.double.isChecked() else 1
            self.go(max(0, self.page-amount), animate=True)

    def jump_page(self): self.go(self.jump.value()-1)

    def options(self, *args):
        self.page_turn.finish()
        self.library.data['settings'].update(direction=self.direction.currentIndex(), double=self.double.isChecked(), cover=self.cover.isChecked(), gap=self.gap.value(), motion=self.motion.currentIndex(), speed=self.speed.currentIndex(), fit=self.fit.currentIndex(), zoom=self.zoom.currentIndex())
        self.library.save()
        self.speed.setEnabled(self.motion.currentData()!='none')
        self.next_btn.setText('← 下一页' if self.direction.currentIndex()==0 else '下一页 →')
        self.prev_btn.setText('上一页 →' if self.direction.currentIndex()==0 else '← 上一页')
        self.display()

    def toggle_appearance(self, checked):
        self.appearance.setVisible(checked and (not self.immersive or self.immersive_controls))
        if self.immersive: self.layout_immersive_overlays()
        else: self.timer.start(0)

    def toggle_immersive(self):
        self.set_immersive(not self.immersive)

    def exit_immersive(self):
        if self.immersive: self.set_immersive(False)

    def toggle_immersive_controls(self):
        if not self.immersive: return
        self.immersive_controls=not self.immersive_controls
        for widget in [self.header,self.toolbar,self.navigation]:
            widget.setVisible(self.immersive_controls)
        self.appearance.setVisible(self.immersive_controls and self.settings_btn.isChecked())
        self.immersive_top.setVisible(self.immersive_controls)
        self.immersive_bottom.setVisible(self.immersive_controls)
        self.layout_immersive_overlays()
        self.canvas.unsetCursor()
        if self.immersive_controls: self.cursor_timer.stop()
        else: self.cursor_timer.start()
        self.canvas.setFocus()

    def layout_immersive_overlays(self):
        if not self.immersive or not self.immersive_controls: return
        width=max(1,self.split.width()-24)
        for panel in (self.immersive_top,self.immersive_bottom):
            panel.layout().activate()
            height=panel.sizeHint().height()
            panel.setGeometry(12,12 if panel is self.immersive_top else max(12,self.split.height()-height-12),width,height)
            panel.raise_()

    def place_immersive_controls(self,enabled):
        for index,widget in [(0,self.header),(1,self.toolbar),(2,self.appearance),(4,self.navigation)]:
            widget.hide()
            if enabled:
                self.reader_layout.removeWidget(widget)
                panel=self.immersive_bottom if widget is self.navigation else self.immersive_top
                widget.setParent(panel); panel.layout().addWidget(widget)
            else:
                widget.parentWidget().layout().removeWidget(widget)
                widget.setParent(self.split); self.reader_layout.insertWidget(index,widget)
        self.immersive_top.hide(); self.immersive_bottom.hide()

    def set_immersive(self, enabled):
        if enabled == self.immersive: return
        if enabled: self.show_reader()
        self.page_turn.finish()
        self.immersive = enabled
        self.immersive_controls = False
        if enabled:
            self.was_fullscreen = self.isFullScreen()
            self.was_maximized = self.isMaximized()
        self.place_immersive_controls(enabled)
        for widget in [self.header, self.toolbar, self.navigation, self.statusBar()]:
            widget.setVisible(not enabled)
        self.appearance.setVisible(not enabled and self.settings_btn.isChecked())
        self.reader_layout.setContentsMargins(*(0,0,0,0) if enabled else (18,12,18,12))
        self.reader_layout.setSpacing(0 if enabled else 12)
        self.canvas.margin = 12 if enabled else 28
        if enabled:
            self.showFullScreen()
            self.canvas.setFocus()
            self.cursor_timer.start()
        else:
            self.cursor_timer.stop(); self.canvas.unsetCursor()
            if self.was_fullscreen: self.showFullScreen()
            elif self.was_maximized: self.showMaximized()
            else: self.showNormal()
        self.timer.start(0)
        self.sync_reading_time()

    def escape(self):
        if self.immersive: self.exit_immersive()
        elif self.isFullScreen(): self.showNormal()
        elif self.pages.currentWidget() is self.shelf: self.shelf.show_grid()
        elif self.pages.currentWidget() is self.stats_page: self.back_from_stats()

    def fullscreen(self):
        if self.immersive: self.exit_immersive()
        else: self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def eventFilter(self, watched, event):
        if event.type()==QEvent.Type.Resize and watched is getattr(self,'reading_viewport',None):
            if hasattr(self,'page_turn'): self.page_turn.resize_viewport()
            if hasattr(self,'timer'): self.timer.start(0)
            if hasattr(self,'immersive_top'): self.layout_immersive_overlays()
        if event.type()==QEvent.Type.MouseMove and watched is self.canvas and self.immersive:
            self.canvas.unsetCursor()
            if not self.immersive_controls: self.cursor_timer.start()
        return super().eventFilter(watched,event)
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'timer'): self.timer.start(80)
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.ActivationChange,QEvent.Type.WindowStateChange): self.sync_reading_time()
    def resize_canvas(self): self.canvas.update_size(); self.canvas.update()
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self, event):
        paths=[url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if len(paths)>1: self.import_batch(paths)
        elif paths:
            p=Path(paths[0]); self.add_folder(str(p)) if p.is_dir() else self.library.add([str(p)])
        self.refresh()
    def closeEvent(self, event):
        self.completion.shutdown()
        self.reading_tick.stop(); self.reading_tracker.stop()
        self.shelf.covers.shutdown(); self.shelf.cover.clear()
        self.page_turn.finish()
        if self.book: self.book.close()
        self.library.save(); event.accept()

def activate_existing(pid):
    if sys.platform!='win32': return False
    import ctypes
    from ctypes import wintypes
    user32=ctypes.windll.user32; found=[]
    @ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
    def callback(hwnd,arg):
        owner=wintypes.DWORD(); handle=ctypes.c_void_p(hwnd)
        user32.GetWindowThreadProcessId(handle,ctypes.byref(owner))
        if owner.value==pid:
            title=ctypes.create_unicode_buffer(256); user32.GetWindowTextW(handle,title,256)
            if title.value in ('yukina漫画阅读器','右页 · 漫画阅读器'):
                if user32.IsIconic(handle): user32.ShowWindow(handle,9)
                user32.SetForegroundWindow(handle); found.append(hwnd)
        return True
    user32.EnumWindows(callback,0)
    return bool(found)

def main():
    app = QApplication(sys.argv)
    app.setApplicationDisplayName('yukina漫画阅读器')
    app.setFont(QFont('Microsoft YaHei UI', 10))
    (ROOT/'data').mkdir(exist_ok=True)
    lock=QLockFile(str(ROOT/'data'/'reader.lock')); lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        info=lock.getLockInfo()
        if info[0]<=0 or not activate_existing(info[0]): QMessageBox.information(None,'yukina漫画阅读器已在运行','请使用已经打开的阅读器窗口。')
        return 0
    try: window = Window()
    except Exception as error:
        QMessageBox.critical(None, '启动失败', str(error)); return 1
    window.show()
    try: return app.exec()
    finally: lock.unlock()

if __name__ == '__main__':
    if len(sys.argv)>2 and sys.argv[1]=='--thumbnail-worker':
        from thumbnail_worker import main as worker_main
        sys.exit(worker_main(sys.argv[2]))
    sys.exit(main())
