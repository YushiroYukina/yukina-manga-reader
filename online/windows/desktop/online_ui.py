"""Qt online discovery, source management and explicit download queue."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import threading
import time
import uuid
from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,
    QComboBox,QListWidget,QListWidgetItem,QDialog,QFormLayout,QDialogButtonBox,
    QFileDialog,QMessageBox,QCheckBox,QProgressBar,QAbstractItemView)
import online_core as core
from reader import volumes,spread
from ui_theme import button_role
from smooth_scroll import SmoothScroll

class Jobs(QObject):
    finished=Signal(object,object,object)
    progress=Signal(str,int,int)
    def __init__(self,parent):
        super().__init__(parent);self.pool=ThreadPoolExecutor(2,thread_name_prefix='online');self.downloads=ThreadPoolExecutor(1,thread_name_prefix='download');self.preloads=ThreadPoolExecutor(2,thread_name_prefix='preload');self.searches=ThreadPoolExecutor(3,thread_name_prefix='search');self.closed=False
        self.finished.connect(self.deliver)
    def run(self,work,done,download=False,search=False):
        def execute():
            try: result=work();error=None
            except Exception as exc: result=None;error=str(exc)
            if not self.closed:self.finished.emit(done,result,error)
        return (self.searches if search else self.downloads if download else self.pool).submit(execute)
    def deliver(self,done,result,error):
        if not self.closed:
            try: done(result,error)
            except RuntimeError: pass  # A closed transient dialog no longer owns its callback.
            except Exception as exc: QMessageBox.warning(self.parent(),'操作未完成',str(exc))
    def shutdown(self):
        self.closed=True;self.pool.shutdown(wait=False,cancel_futures=True);self.downloads.shutdown(wait=False,cancel_futures=True);self.preloads.shutdown(wait=False,cancel_futures=True);self.searches.shutdown(wait=False,cancel_futures=True)

class SourceEditor(QDialog):
    def __init__(self,parent,source=None):
        super().__init__(parent);self.original=source or {};self.setWindowTitle('配置书源');self.resize(640,420)
        lay=QVBoxLayout(self);form=QFormLayout();lay.addLayout(form)
        self.name=QLineEdit(self.original.get('name',''));form.addRow('显示名称',self.name)
        self.kind=QComboBox();self.kind.addItems(core.KINDS);self.kind.setCurrentText(self.original.get('type','komga'));form.addRow('接口类型',self.kind)
        self.base=QLineEdit(self.original.get('base_url',''));self.base.setPlaceholderText('https://…（Komga / Suwayomi 填服务器根地址）');form.addRow('服务地址',self.base)
        self.lang=QComboBox();self.lang.addItems(['zh','ja','en','zh-hk','ko','fr','es']);self.lang.setCurrentText(self.original.get('language','zh'));form.addRow('MangaDex 章节语言',self.lang)
        self.sid=QLineEdit(str(self.original.get('source_id','')));self.sid.setPlaceholderText('Suwayomi 扩展书源 ID，可通过服务端列表选择');form.addRow('扩展书源 ID',self.sid)
        self.user=QLineEdit(self.original.get('username',''));form.addRow('用户名（可选）',self.user)
        self.password=QLineEdit(self.original.get('password',''));self.password.setEchoMode(QLineEdit.EchoMode.Password);form.addRow('密码（可选）',self.password)
        self.token=QLineEdit(self.original.get('api_key') or self.original.get('token',''));self.token.setEchoMode(QLineEdit.EchoMode.Password);form.addRow('API Key / 访问令牌',self.token)
        self.enabled=QCheckBox('启用此书源');self.enabled.setChecked(self.original.get('enabled',True));form.addRow(self.enabled)
        hint=QLabel('内置漫画柜、MangaDex、MangaPill，另支持 Komga / Suwayomi 服务和 JSON 目录。\nSuwayomi 的扩展需先在服务端安装。本程序不运行陌生脚本或 APK。');hint.setWordWrap(True);lay.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);lay.addWidget(buttons)
    def source(self):
        kind=self.kind.currentText();s={'id':self.original.get('id') or uuid.uuid4().hex,'name':self.name.text().strip(),'type':kind,'base_url':self.base.text().strip(),'language':self.lang.currentText(),'source_id':self.sid.text().strip(),'username':self.user.text(),'password':self.password.text(),'enabled':self.enabled.isChecked()}
        s['api_key' if kind=='komga' else 'token']=self.token.text().strip()
        return core.normalize_source(s)

class SourcesDialog(QDialog):
    def __init__(self,controller):
        super().__init__(controller.w);self.c=controller;self.setWindowTitle('书源管理');self.resize(820,550)
        lay=QVBoxLayout(self);lay.addWidget(QLabel('可同时保存多个书源 · 配置保存在独立在线版书库'))
        self.list=QListWidget();lay.addWidget(self.list,1);row=QHBoxLayout();lay.addLayout(row)
        for title,fn in [('添加',self.add),('编辑',self.edit),('启用 / 停用',self.toggle),('移除',self.remove),('选择 Suwayomi 扩展',self.extensions)]:
            b=QPushButton(title);b.clicked.connect(fn);row.addWidget(b)
        row2=QHBoxLayout();lay.addLayout(row2)
        for title,fn in [('导入书源 JSON',self.import_file),('从链接导入',self.import_url),('导出配置（不含认证）',self.export)]:
            b=QPushButton(title);b.clicked.connect(fn);row2.addWidget(b)
        self.note=QLabel('启用的书源都会参与混合搜索；停用后不再搜索该来源。自建服务需填写可访问的地址。');self.note.setWordWrap(True);lay.addWidget(self.note)
        close=QPushButton('完成');close.clicked.connect(self.accept);lay.addWidget(close);self.refresh()
    def refresh(self):
        self.list.clear()
        for s in self.c.service.sources.all:
            i=QListWidgetItem(f"{'●' if s.get('enabled',True) else '○'}  {s['name']}  ·  {s['type']}\n{s['base_url']}");i.setData(Qt.ItemDataRole.UserRole,s['id']);self.list.addItem(i)
        self.c.refresh_sources()
    def selected(self):
        i=self.list.currentItem()
        return next((s for s in self.c.service.sources.all if i and s['id']==i.data(Qt.ItemDataRole.UserRole)),None)
    def edit(self,source=None):
        s=source or self.selected()
        if not s:return
        d=SourceEditor(self,s)
        if d.exec():
            try:self.c.service.sources.put(d.source());self.refresh()
            except Exception as e:self.note.setText(str(e))
    def add(self):
        d=SourceEditor(self)
        if d.exec():
            try:self.c.service.sources.put(d.source());self.refresh()
            except Exception as e:self.note.setText(str(e))
    def toggle(self):
        s=self.selected()
        if s:s['enabled']=not s.get('enabled',True);self.c.service.sources.save();self.refresh()
    def remove(self):
        s=self.selected()
        if not s:return
        self.c.service.sources.all.remove(s);self.c.service.sources.save();self.refresh()
    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,'导入 Yukina 书源包','','书源 (*.json)')
        if path:
            try:
                if Path(path).stat().st_size>core.JSON_LIMIT:raise core.OnlineError('配置过大')
                n=self.c.service.sources.import_configs(json.loads(Path(path).read_text('utf-8-sig')));self.refresh();self.note.setText(f'已添加 {n} 个新书源')
            except Exception as e:self.note.setText(str(e))
    def import_url(self):
        from PySide6.QtWidgets import QInputDialog
        url,ok=QInputDialog.getText(self,'导入书源','书源包 JSON 地址')
        if ok and url:
            try:url=core.checked_url(url)
            except Exception as e:self.note.setText(str(e));return
            self.note.setText('正在读取配置…')
            def done(result,error):
                if error:self.note.setText(error);return
                try:n=self.c.service.sources.import_configs(result);self.refresh();self.note.setText(f'已添加 {n} 个新书源')
                except Exception as e:self.note.setText(str(e))
            self.c.jobs.run(lambda:core.Http({'base_url':url}).json(url),done)
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'导出无认证的书源配置','yukina-sources.json','JSON (*.json)')
        if path:
            configs=[{k:v for k,v in s.items() if k not in ('username','password','api_key','token')} for s in self.c.service.sources.all]
            core.atomic_json(Path(path),{'version':1,'sources':configs});self.note.setText('已导出，认证信息未包含在文件中')
    def extensions(self):
        s=self.selected()
        if not s or s['type']!='suwayomi':self.note.setText('请先添加并选中一个 Suwayomi 服务');return
        def done(rows,error):
            if error:self.note.setText(error);return
            d=QDialog(self);d.setWindowTitle('选择已安装扩展');lay=QVBoxLayout(d);items=QListWidget();lay.addWidget(items)
            for r in rows:
                i=QListWidgetItem(f"{r.get('name','')} · {r.get('lang','')} · {r['id']}");i.setData(Qt.ItemDataRole.UserRole,r);items.addItem(i)
            b=QPushButton('将所选扩展另存为书源');lay.addWidget(b)
            def choose():
                i=items.currentItem()
                if not i:return
                r=i.data(Qt.ItemDataRole.UserRole);copy=dict(s,id=uuid.uuid4().hex,source_id=str(r['id']),name=r.get('name','扩展书源')+' · '+r.get('lang',''));self.c.service.sources.put(copy);self.refresh();d.accept()
            b.clicked.connect(choose);d.resize(580,500);d.exec()
        self.c.jobs.run(lambda:core.Provider(s).extension_sources(),done)

from online_downloads import DownloadsDialog

class OnlineController(QObject):
    def __init__(self,w):
        super().__init__(w);self.w=w;self.service=core.OnlineService(w.runtime_root,w.library);core.SERVICE=self.service;self.jobs=Jobs(w);self.serial=0;self.search_serial=0;self.result_page=1;self.rows=[];self.cancel=threading.Event();self.download_active=False;self.download_message='选择章节后下载，可多选。';self.closed=False
        self.search_futures=[];self.search_cache={};self.source_more={};self.enabled_signature=None;self.last_search_term=None;self.add_busy=False
        self.discovery=QWidget();lay=QVBoxLayout(self.discovery);lay.setContentsMargins(32,26,32,20);lay.setSpacing(16)
        heading=QHBoxLayout();title=QLabel('发现在线漫画');title.setStyleSheet('font-size:28px;font-weight:600');heading.addWidget(title);heading.addStretch();back=QPushButton('返回书库');back.clicked.connect(w.show_library);heading.addWidget(back);lay.addLayout(heading)
        bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('输入作品名称，留空浏览热门');self.query.returnPressed.connect(self.search);bar.addWidget(self.query,1)
        search=QPushButton('搜索');button_role(search,'primary');search.clicked.connect(lambda:self.search());bar.addWidget(search);manage=QPushButton('管理书源');manage.clicked.connect(self.manage_sources);bar.addWidget(manage);lay.addLayout(bar)
        self.note=QLabel('搜索所有已启用的书源；可在书源管理中启用或停用。');self.note.setWordWrap(True);self.note.setTextFormat(Qt.TextFormat.PlainText);lay.addWidget(self.note)
        self.results=QListWidget();self.results.scroll_motion=SmoothScroll(self.results);self.results.setSpacing(8);self.results.itemDoubleClicked.connect(lambda _:self.add_selected());lay.addWidget(self.results,1)
        footer=QHBoxLayout();self.prev=QPushButton('上一页');self.prev.clicked.connect(lambda:self.search_page(-1));footer.addWidget(self.prev);self.next=QPushButton('下一页');self.next.clicked.connect(lambda:self.search_page(1));footer.addWidget(self.next);footer.addStretch();self.add=QPushButton('加入书库并查看章节');button_role(self.add,'primary');self.add.clicked.connect(self.add_selected);footer.addWidget(self.add);lay.addLayout(footer);w.pages.addWidget(self.discovery)
        actions=QHBoxLayout()
        self.prefetch_serial=0;self.prefetch_job=None;self.prefetch_jobs=[];self.preload_errors=[]
        for name,fn in [('在线发现',self.show),('书源管理',self.manage_sources),('下载与缓存',lambda:DownloadsDialog(self).exec()),('刷新在线目录',self.refresh_current)]:
            b=QPushButton(name);b.clicked.connect(fn);actions.addWidget(b)
        actions.addStretch();w.shelf.layout().insertLayout(1,actions)
        self.reader_quality=QPushButton('在线画质 / 预加载');self.reader_quality.setVisible(False);self.reader_quality.clicked.connect(self.reading_settings);w.appearance.layout().insertWidget(0,self.reader_quality)
        w.shelf.online_download_requested.connect(lambda owner:DownloadsDialog(self,owner).exec());w.shelf.online_source_requested.connect(self.manage_sources);w.shelf.online_refresh_requested.connect(self.refresh_entry);w.shelf.online_cover_requested.connect(self.set_cover);self.refresh_sources();w.setWindowTitle('yukina漫画阅读器 · 在线版')
        self.cover_repairs=iter([e for e in w.library.data['books'] if e.get('online') and not e.get('cover_path') and (not e.get('online_cover') or not Path(e['online_cover']).is_file())])
        QTimer.singleShot(300,self.repair_next_cover)
    def repair_next_cover(self):
        if self.closed:return
        entry=next(self.cover_repairs,None)
        while entry and entry not in self.w.library.data['books']:entry=next(self.cover_repairs,None)
        if entry:
            self.set_cover(entry,entry.get('cover_volume') or volumes(entry)[0]['path'],self.repair_next_cover)
    def reading_settings(self):
        settings=self.w.library.data['settings'];d=QDialog(self.w);d.setWindowTitle('在线画质与预加载');form=QFormLayout(d)
        quality=QComboBox();quality.addItem('流畅（默认 · 自适应压缩）','smooth');quality.addItem('低（节省内存）','low');quality.addItem('原（原图 · 不压缩）','original');quality.setCurrentIndex(max(0,quality.findData(settings.get('online_quality','smooth'))));form.addRow('画质',quality)
        preload=QCheckBox('后台预加载后续页面（仅保留在内存）');preload.setChecked(settings.get('online_preload',True));form.addRow(preload)
        count=QComboBox()
        for n in (2,4,6):count.addItem(f'提前 {n} 页',n)
        count.setCurrentIndex(max(0,count.findData(settings.get('online_preload_pages',4))));form.addRow('预加载范围',count)
        hint=QLabel('支持省流图片的书源优先读取较小版本；其他书源下载后再压缩。\n同次运行中重新进入章节会复用已加载页面，关闭程序后释放。');hint.setWordWrap(True);form.addRow(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);form.addRow(buttons)
        if d.exec()!=QDialog.DialogCode.Accepted:return
        changed=settings.get('online_quality','smooth')!=quality.currentData();settings.update(online_quality=quality.currentData(),online_preload=preload.isChecked(),online_preload_pages=count.currentData());self.w.library.save();self.prefetch_serial+=1
        for job in self.prefetch_jobs:job.cancel()
        if self.w.book and getattr(self.w.book,'online',False):
            if changed:self.open(self.w.active_book,self.w.entry['path'])
            else:self.warm()
    def warm(self):
        self.prefetch_serial+=1;token=self.prefetch_serial
        for job in self.prefetch_jobs:job.cancel()
        settings=self.w.library.data['settings'];book=self.w.book
        if self.closed or self.w.pages.currentWidget() is not self.w.split or not book or not getattr(book,'online',False) or book.offline or not settings.get('online_preload',True):return
        visible=spread(self.w.page,len(book),self.w.double.isChecked(),self.w.cover.isChecked());count=max(2,min(6,int(settings.get('online_preload_pages',4))))
        indices=list(range(visible[-1]+1,min(len(book),visible[-1]+1+count)))+([visible[0]-1] if visible[0]>0 else [])
        def work(batch):
            core.BACKGROUND.active=True
            try:
                for index in batch:
                    if self.closed or token!=self.prefetch_serial or book.closed or self.w.book is not book:return
                    for attempt in range(2 if index in indices[:2] else 1):
                        try:
                            if not book.ready(index):book.render(index)
                            break
                        except Exception as error:
                            self.preload_errors=(self.preload_errors+[str(error)])[-5:]
                            if self.closed or token!=self.prefetch_serial or book.closed:return
            finally:core.BACKGROUND.active=False
        self.prefetch_jobs=[self.jobs.preloads.submit(work,indices[offset::2]) for offset in range(min(2,len(indices)))];self.prefetch_job=self.prefetch_jobs[0] if self.prefetch_jobs else None
    def show(self):
        self.prefetch_serial+=1
        self.serial+=1;self.w.reading_tracker.stop();self.w.pages.setCurrentWidget(self.discovery);self.w.sync_reading_time()
    def manage_sources(self):SourcesDialog(self).exec()
    def refresh_sources(self):
        enabled=[s for s in self.service.sources.all if s.get('enabled',True)];signature=core.hashlib.sha256(json.dumps(enabled,sort_keys=True).encode()).hexdigest()
        if signature!=self.enabled_signature:
            self.search_serial+=1
            for future in self.search_futures:future.cancel()
            self.result_page=1;self.search_cache.clear();self.source_more.clear();self.rows=[];self.results.clear();self.prev.setEnabled(False);self.next.setEnabled(False)
            self.note.setText(f'已启用 {len(enabled)} 个书源，搜索将使用这些来源。可在书源管理中调整。' if enabled else '还没有启用的书源，请进入书源管理。')
        self.enabled_signature=signature
    def search_page(self,step):self.result_page=max(1,self.result_page+step);self.search(reset=False)
    def render_search_rows(self,rows):
        selected=self.results.currentItem();old=selected.data(Qt.ItemDataRole.UserRole) if selected else {};key=(old.get('source_id'),old.get('id'));self.results.clear();self.rows=rows
        for book in rows:
            item=QListWidgetItem(book['title']+'\n'+book['source_name']);item.setData(Qt.ItemDataRole.UserRole,book);self.results.addItem(item)
            if (book['source_id'],book['id'])==key:self.results.setCurrentItem(item)
        self.add.setEnabled(bool(rows) and not self.add_busy)
    def search(self,reset=True):
        enabled=[dict(s) for s in self.service.sources.all if s.get('enabled',True)]
        self.search_serial+=1;token=self.search_serial
        for future in self.search_futures:future.cancel()
        self.search_futures=[]
        term=self.query.text().strip()
        if term!=self.last_search_term:reset=True
        self.last_search_term=term
        if reset:self.result_page=1;self.search_cache.clear();self.source_more.clear()
        page=self.result_page
        if not enabled:self.render_search_rows([]);self.note.setText('还没有启用的书源，请进入书源管理。');self.prev.setEnabled(False);self.next.setEnabled(False);return
        if page in self.search_cache:
            cached=self.search_cache[page];self.render_search_rows(cached['rows']);self.source_more=dict(cached['more']);self.note.setText(cached['note']);self.prev.setEnabled(page>1);self.next.setEnabled(any(self.source_more.values()));return
        targets=[s for s in enabled if page==1 or self.source_more.get(s['id'],False)];state={'rows':{},'more':{},'errors':[],'finished':0};self.render_search_rows([]);self.prev.setEnabled(page>1);self.next.setEnabled(False)
        self.note.setText(f'正在混合搜索 {len(targets)} 个已启用书源…')
        if not targets:self.note.setText('没有更多搜索结果');self.prev.setEnabled(page>1);return
        for source in targets:
            sid=source['id']
            def work(source_id=sid):
                core.BACKGROUND.search=True
                try:return self.service.provider(source_id).search(term,page)
                finally:core.BACKGROUND.search=False
            def done(result,error,s=source):
                if token!=self.search_serial:return
                state['finished']+=1
                if error:state['errors'].append(s['name']+'：'+error)
                else:
                    books,more=result;seen=set();rows=[]
                    for book in books:
                        if str(book['id']) in seen:continue
                        seen.add(str(book['id']));rows.append(dict(book,source_id=s['id'],source_name=s['name']))
                    state['rows'][s['id']]=rows;state['more'][s['id']]=bool(more)
                rows=[b for src in targets for b in state['rows'].get(src['id'],[])];self.render_search_rows(rows)
                note=f"第 {page} 页 · {len(rows)} 条结果 · 已完成 {state['finished']}/{len(targets)} 个书源"
                if state['errors']:note+='\n未返回的书源：'+'；'.join(state['errors'])
                self.note.setText(note)
                if state['finished']==len(targets):
                    self.source_more=dict(state['more']);self.prev.setEnabled(page>1);self.next.setEnabled(any(self.source_more.values()));self.search_cache[page]={'rows':rows,'more':dict(self.source_more),'note':note}
            self.search_futures.append(self.jobs.run(work,done,search=True))
    def add_selected(self):
        i=self.results.currentItem()
        if not i or self.add_busy:return
        self.add_busy=True
        b=i.data(Qt.ItemDataRole.UserRole);s=self.service.sources.get(b['source_id']);self.add.setEnabled(False);self.note.setText('正在读取章节目录…')
        def work():
            p=self.service.provider(s['id']);chapters=p.chapters(b['id'])
            return chapters,None
        def done(result,error):
            self.add_busy=False;self.add.setEnabled(bool(self.rows))
            if error:self.note.setText(error);return
            old=next((e for e in self.w.library.data['books'] if e.get('online',{}).get('source_id')==s['id'] and e.get('online',{}).get('book_id')==b['id']),None)
            try:
                entry=core.merge_entry(s,b,result[0],old)
                if result[1]:
                    from PySide6.QtGui import QImage
                    image=QImage.fromData(result[1])
                    if not image.isNull():
                        folder=self.w.runtime_root/'cache'/'online-covers';folder.mkdir(parents=True,exist_ok=True);file=folder/(entry['id']+'.png');image.scaled(420,600,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation).save(str(file));entry['online_cover']=str(file)
                if not old:self.w.library.data['books'].append(entry)
                self.w.library.save();self.w.refresh()
                if self.w.pages.currentWidget() is self.discovery:self.w.show_library(entry)
                if not entry.get('cover_path') and not entry.get('online_cover'):self.set_cover(entry,volumes(entry)[0]['path'])
            except Exception as e:self.note.setText(str(e))
        self.jobs.run(work,done)
    def set_cover(self,entry,path,on_finish=None):
        previous=entry.get('cover_path');self.w.statusBar().showMessage('正在生成章节第一页封面…')
        cover_root=self.w.runtime_root/'cache'/'online-covers'
        if core.os.name=='nt' and cover_root.drive.casefold()=='c:':
            roots=self.service.sources.data.get('cache_roots',[])
            if not roots:
                self.w.statusBar().showMessage('请先选择 C 盘以外的下载目录，再生成在线封面')
                if on_finish:QTimer.singleShot(0,on_finish)
                return
            cover_root=Path(roots[0])/'covers'
        def work():
            book=core.OnlineBook(path,quality='original')
            try:return book.render(0).scaled(420,600,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            finally:book.close()
        def done(image,error):
            if on_finish:QTimer.singleShot(0,on_finish)
            if error:self.w.statusBar().showMessage('封面暂不可用：'+error);return
            if entry not in self.w.library.data['books'] or entry.get('cover_path')!=previous:return
            folder=cover_root;folder.mkdir(parents=True,exist_ok=True);target=folder/(entry['id']+'-'+core.hashlib.sha256(path.encode()).hexdigest()[:16]+'.png')
            if not image.save(str(target)):self.w.statusBar().showMessage('封面保存失败');return
            self.w.library.set_cover_volume(entry,path);entry['online_cover']=str(target);self.w.library.save();self.w.shelf.covers.cache.clear();self.w.refresh();self.w.statusBar().showMessage('已使用所选章节第一页作为封面')
        self.jobs.run(work,done)
    def refresh_current(self):
        e=self.w.shelf.current()
        if e and e.get('online'):self.refresh_entry(e)
        else:QMessageBox.information(self.w,'刷新在线目录','请先进入一本在线作品的图书详情')
    def refresh_entry(self,entry):
        m=entry['online'];self.w.statusBar().showMessage('正在刷新在线章节…')
        def done(chapters,error):
            if error:QMessageBox.warning(self.w,'目录更新失败',error);return
            if entry not in self.w.library.data['books']:return
            core.merge_entry(self.service.sources.get(m['source_id']),{'id':m['book_id'],'title':m['title'],'cover':m.get('cover','')},chapters,entry);self.w.library.save();self.w.refresh();self.w.statusBar().showMessage('章节已更新，已有阅读记录保留')
            if not entry.get('cover_path') and (not entry.get('online_cover') or not Path(entry['online_cover']).is_file()):self.set_cover(entry,volumes(entry)[0]['path'])
        self.jobs.run(lambda:self.service.provider(m['source_id']).chapters(m['book_id']),done)
    def open(self,owner,path=None):
        self.prefetch_serial+=1
        self.serial+=1;token=self.serial;children=volumes(owner);selected=next((c for c in children if c['path']==(path or owner.get('current_volume'))),children[0]);self.w.reading_tracker.stop();self.w.statusBar().showMessage('正在加载章节…');double=self.w.double.isChecked();cover=self.w.cover.isChecked()
        def work():
            book=core.OnlineBook(selected['path']);page=max(0,min(selected.get('page',0),len(book)-1))
            for i in spread(page,len(book),double,cover):book.render(i)
            return book,page
        def done(result,error):
            if token!=self.serial or owner not in self.w.library.data['books']:
                if result:result[0].close()
                return
            if error:QMessageBox.warning(self.w,'章节读取失败',error);self.w.sync_reading_time();return
            book,page=result
            if self.w.book:self.w.book.close()
            self.w.page_turn.finish();self.w.book=book;self.w.entry=selected;self.w.active_book=owner;self.w.page=page;owner['current_volume']=selected['path'];self.w.reading_tracker.select(owner,selected);self.w.heading.setText(owner['title']+' / '+selected['title']);self.w.heading.setToolTip(selected['path']);self.w.jump.setRange(1,len(book));self.w.show_reader();self.w.refresh();self.w._display_ready();self.w.update_volume_buttons();self.w.statusBar().showMessage('离线缓存阅读' if book.offline else '在线阅读 · 页面仅保留在内存')
            self.warm()
        self.jobs.run(work,done)
    def display(self):
        w=self.w;indices=spread(w.page,len(w.book),w.double.isChecked(),w.cover.isChecked())
        if all(w.book.ready(i) for i in indices):
            result=w._display_ready();self.warm();return result
        self.go(w.page,False);return False
    def go(self,page,animate=False):
        self.prefetch_serial+=1
        w=self.w;book=w.book;target=max(0,min(page,len(book)-1));indices=spread(target,len(book),w.double.isChecked(),w.cover.isChecked());self.serial+=1;token=self.serial
        if all(book.ready(i) for i in indices):
            if target==w.page:w._display_ready()
            else:w._go_ready(target,animate)
            self.warm()
            return
        w.statusBar().showMessage('页面加载中…')
        def work():
            for i in indices:book.render(i)
        def done(_,error):
            if token!=self.serial or w.book is not book:return
            if error:QMessageBox.warning(w,'页面读取失败',error);return
            if target==w.page:w._display_ready()
            else:w._go_ready(target,animate)
            w.statusBar().showMessage('离线阅读' if book.offline else '在线阅读')
            self.warm()
        self.jobs.run(work,done)
    def download(self,chapters):
        if self.download_active:self.download_message='已有下载队列，暂停后可重新选择';return
        if not chapters:self.download_message='请先选择章节';return
        chapters=list({ch['path']:ch for ch in chapters}.values())
        self.cancel=threading.Event();self.download_active=True;self.download_message=f'正在下载 {len(chapters)} 个章节…'
        queue_file=self.w.runtime_root/'data/online-download-queue.json';pending=list(dict.fromkeys(ch['path'] for ch in chapters))
        try:prior=json.loads(queue_file.read_text('utf-8')) if queue_file.exists() else []
        except (ValueError,OSError):prior=[]
        deferred=[p for p in prior if p not in pending];core.atomic_json(queue_file,pending+deferred)
        owner_titles={v['path']:owner['title'] for owner in self.w.library.data['books'] for v in volumes(owner)}
        def work():
            successes=0;errors=[]
            for ch in chapters:
                if self.cancel.is_set():break
                try:
                    p=self.service.provider(ch['online']['source_id']);self.service.cache.download(dict(ch,_book_title=owner_titles.get(ch['path'],'')),p,self.cancel,lambda n,total:self.jobs.progress.emit(ch['title'],n,total));successes+=1
                except core.Cancelled:break
                except Exception as e:
                    errors.append(ch['title']+'：'+str(e));continue
                pending.remove(ch['path']);core.atomic_json(queue_file,pending+deferred)
            return successes,errors
        def done(result,error):
            self.download_active=False
            self.download_message=error or f'已完成 {result[0]} 个章节'+('；'+'；'.join(result[1]) if result[1] else '')+('；队列已暂停，可继续' if self.cancel.is_set() else '')
            self.w.statusBar().showMessage(self.download_message);self.w.refresh()
        self.jobs.run(work,done,download=True)
    def resume_downloads(self,owner=None):
        try:
            queue=self.w.runtime_root/'data/online-download-queue.json'
            if not queue.exists():self.w.statusBar().showMessage('没有待继续的队列');return
            paths=json.loads(queue.read_text('utf-8'));chapters=[];allowed={v['path'] for v in volumes(owner)} if owner else set()
            if owner is None:self.w.statusBar().showMessage('请从具体书籍的详情页继续下载');return
            for path in paths:
                if path not in allowed:continue
                try:chapters.append(self.service.find_volume(path))
                except core.OnlineError:pass
            if not chapters:self.w.statusBar().showMessage('本书没有待继续的队列，请选择需要下载的章节');return
            self.download(chapters)
        except Exception as e:QMessageBox.warning(self.w,'队列无法恢复',str(e))
    def cancel_downloads(self):self.cancel.set();self.download_message='正在暂停，当前网络请求结束后停止；已完成页面会保留'
    def shutdown(self):self.closed=True;self.serial+=1;self.cancel.set();self.jobs.shutdown()
