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

class Jobs(QObject):
    finished=Signal(object,object,object)
    progress=Signal(str,int,int)
    cache_changed=Signal()
    def __init__(self,parent):
        super().__init__(parent);self.pool=ThreadPoolExecutor(2,thread_name_prefix='online');self.searches=ThreadPoolExecutor(4,thread_name_prefix='search');self.downloads=ThreadPoolExecutor(1,thread_name_prefix='download');self.preloads=ThreadPoolExecutor(2,thread_name_prefix='preload');self.closed=False
        self.finished.connect(self.deliver)
    def run(self,work,done,download=False,search=False):
        def execute():
            try: result=work();error=None
            except Exception as exc: result=None;error=str(exc)
            if not self.closed:self.finished.emit(done,result,error)
        return (self.downloads if download else self.searches if search else self.pool).submit(execute)
    def deliver(self,done,result,error):
        if not self.closed:
            try: done(result,error)
            except RuntimeError: pass  # A closed transient dialog no longer owns its callback.
            except Exception as exc: QMessageBox.warning(self.parent(),'操作未完成',str(exc))
    def shutdown(self):
        self.closed=True;self.pool.shutdown(wait=False,cancel_futures=True);self.searches.shutdown(wait=False,cancel_futures=True);self.downloads.shutdown(wait=False,cancel_futures=True);self.preloads.shutdown(wait=False,cancel_futures=True)

class SourceEditor(QDialog):
    def __init__(self,parent,source=None):
        super().__init__(parent);self.original=source or {};self.setWindowTitle('配置书源');self.resize(640,420)
        lay=QVBoxLayout(self);form=QFormLayout();lay.addLayout(form)
        self.name=QLineEdit(self.original.get('name',''));form.addRow('显示名称',self.name)
        self.kind=QComboBox();self.kind.addItems(core.KINDS);self.kind.setCurrentText(self.original.get('type','komga'));form.addRow('接口类型',self.kind)
        self.base=QLineEdit(self.original.get('base_url',''));self.base.setPlaceholderText('https://…（Komga / Suwayomi 填服务器根地址）');form.addRow('服务地址',self.base)
        self.connection=QComboBox();self.connection.addItem('跟随系统代理（默认）','system');self.connection.addItem('直接连接（此书源不使用系统代理）','direct');self.connection.setCurrentIndex(self.connection.findData(self.original.get('connection','system')));form.addRow('连接方式',self.connection)
        self.lang=QComboBox();self.lang.addItems(['zh','ja','en','zh-hk','ko','fr','es']);self.lang.setCurrentText(self.original.get('language','zh'));form.addRow('MangaDex 章节语言',self.lang)
        self.sid=QLineEdit(str(self.original.get('source_id','')));self.sid.setPlaceholderText('Suwayomi 扩展书源 ID，可通过服务端列表选择');form.addRow('扩展书源 ID',self.sid)
        self.user=QLineEdit(self.original.get('username',''));form.addRow('用户名（可选）',self.user)
        self.password=QLineEdit(self.original.get('password',''));self.password.setEchoMode(QLineEdit.EchoMode.Password);form.addRow('密码（可选）',self.password)
        self.token=QLineEdit(self.original.get('api_key') or self.original.get('token',''));self.token.setEchoMode(QLineEdit.EchoMode.Password);form.addRow('API Key / 访问令牌',self.token)
        self.enabled=QCheckBox('启用此书源');self.enabled.setChecked(self.original.get('enabled',True));form.addRow(self.enabled)
        hint=QLabel('内置动漫屋、漫画柜、MangaDex、MangaPill，另支持 Komga / Suwayomi 服务和 JSON 目录。\nSuwayomi 的扩展需先在服务端安装。本程序不运行陌生脚本或 APK。');hint.setWordWrap(True);lay.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);lay.addWidget(buttons)
    def source(self):
        kind=self.kind.currentText();s={'id':self.original.get('id') or uuid.uuid4().hex,'name':self.name.text().strip(),'type':kind,'base_url':self.base.text().strip(),'language':self.lang.currentText(),'source_id':self.sid.text().strip(),'username':self.user.text(),'password':self.password.text(),'enabled':self.enabled.isChecked(),'connection':self.connection.currentData()}
        s['api_key' if kind=='komga' else 'token']=self.token.text().strip()
        return core.normalize_source(s)

class SourcesDialog(QDialog):
    def __init__(self,controller):
        super().__init__(controller.w);self.c=controller;self.setWindowTitle('书源管理');self.resize(820,550)
        lay=QVBoxLayout(self);lay.addWidget(QLabel('勾选启用的书源将参与混合搜索 · 配置保存在独立在线版书库'))
        self.list=QListWidget();self.list.itemChanged.connect(self.set_enabled);lay.addWidget(self.list,1);row=QHBoxLayout();lay.addLayout(row)
        for title,fn in [('添加',self.add),('编辑',self.edit),('启用 / 停用',self.toggle),('移除',self.remove),('选择 Suwayomi 扩展',self.extensions)]:
            b=QPushButton(title);b.clicked.connect(fn);row.addWidget(b)
        row2=QHBoxLayout();lay.addLayout(row2)
        for title,fn in [('导入书源 JSON',self.import_file),('从链接导入',self.import_url),('导出配置（不含认证）',self.export)]:
            b=QPushButton(title);b.clicked.connect(fn);row2.addWidget(b)
        self.note=QLabel('仅启用您需要的书源；各书源独立返回结果，较慢或失败的来源不会挡住其他来源。');self.note.setWordWrap(True);lay.addWidget(self.note)
        close=QPushButton('完成');close.clicked.connect(self.accept);lay.addWidget(close);self.refresh()
    def refresh(self):
        selected=self.selected();self.list.blockSignals(True);self.list.clear()
        for source in self.c.service.sources.all:
            item=QListWidgetItem(source['name']+'  ·  '+source['type']+'\n'+source['base_url']);item.setData(Qt.ItemDataRole.UserRole,source['id']);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if source.get('enabled',True) else Qt.CheckState.Unchecked);self.list.addItem(item)
            if selected and selected['id']==source['id']:self.list.setCurrentItem(item)
        self.list.blockSignals(False);self.c.refresh_sources()
    def set_enabled(self,item):
        source=next((s for s in self.c.service.sources.all if s['id']==item.data(Qt.ItemDataRole.UserRole)),None)
        if source:
            source['enabled']=item.checkState()==Qt.CheckState.Checked;self.c.service.sources.save();self.c.refresh_sources()
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

class DownloadsDialog(QDialog):
    """Library inventory is read-only for downloads; book detail owns new work."""
    def __init__(self,c,owner=None,inventory_only=False):
        super().__init__(c.w);self.c=c;self.owner=owner;self.allow_download=owner is not None and not inventory_only;self.records={};self.was_active=c.download_active
        self.setWindowTitle((owner['title']+' · 下载与缓存') if owner else '已下载的在线书籍');self.resize(900,640);lay=QVBoxLayout(self)
        self.location=QLabel();self.location.setWordWrap(True);lay.addWidget(self.location)
        if self.allow_download:
            select=QPushButton('选择独立下载目录（可选外置盘）');select.clicked.connect(self.choose);lay.addWidget(select)
        self.list=QListWidget();self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);lay.addWidget(self.list,1)
        row=QHBoxLayout();lay.addLayout(row)
        actions=[]
        if self.allow_download:actions += [('下载所选 / 继续',self.download),('继续本书队列',self.resume)]
        if owner is None:actions += [('查看缓存章节',self.browse),('前往书籍详情',self.open_detail)]
        actions += [('暂停当前队列',self.pause),('清理所选缓存',self.clear),('清理本书下载' if owner else '清理全部下载',self.clear_all),('刷新',self.refresh)]
        for title,fn in actions:
            b=QPushButton(title);b.clicked.connect(fn);row.addWidget(b)
        self.progress=QLabel();self.progress.setWordWrap(True);lay.addWidget(self.progress)
        self.c.jobs.progress.connect(self.update_progress);self.c.jobs.cache_changed.connect(self.refresh)
        self.finished.connect(self.cleanup);self.refresh();self.status_timer=QTimer(self);self.status_timer.timeout.connect(self.sync_status);self.status_timer.start(400);self.sync_status()
    def cleanup(self,*args):
        self.status_timer.stop()
        try:self.c.jobs.progress.disconnect(self.update_progress);self.c.jobs.cache_changed.disconnect(self.refresh)
        except (RuntimeError,TypeError):pass
    def owns_active_download(self):
        return self.owner is None or bool({ch['path'] for ch in volumes(self.owner)} & self.c.active_download_paths)
    def sync_status(self):
        if self.c.download_active:
            if self.owns_active_download():self.progress.setText(self.c.download_message)
            else:self.progress.setText('其他图书正在下载，请等待完成或在其详情页暂停。')
        elif self.was_active and self.owns_active_download():self.progress.setText(self.c.download_message)
        self.was_active=self.c.download_active
    def update_progress(self,title,n,total):
        if self.owns_active_download():self.progress.setText(f'{title} · {n} / {total} 页')
    def choose(self):
        path=QFileDialog.getExistingDirectory(self,'选择下载目录')
        if path:
            try:self.c.service.sources.set_cache_root(path);self.refresh()
            except Exception as e:QMessageBox.warning(self,'目录不可用',str(e))
    def cached_books(self):
        library={e['path']:e for e in self.c.w.library.data['books'] if e.get('online')};groups={}
        for cached in self.c.service.cache.all_volumes():
            record=self.c.service.cache.manifest(cached,False)
            if not record:continue
            key=cached['path'].rsplit('/',1)[0];owner=library.get(key)
            if owner:
                ch=next((v for v in volumes(owner) if v['path']==cached['path']),cached)
                entry=owner
            else:
                ch=cached;entry={'id':key,'path':key,'kind':'folder','title':record[1].get('book_title') or '已移出书库的作品','online':{'source_id':key.split('/')[2]},'volumes':[]}
            group=groups.setdefault(key,{'owner':entry,'chapters':[]});group['chapters'].append(ch)
            if not owner:group['owner']['volumes'].append(ch)
        return sorted(groups.values(),key=lambda g:g['owner']['title'].casefold())
    def refresh(self):
        selected={i.data(Qt.ItemDataRole.UserRole) for i in self.list.selectedItems()};self.list.clear();self.records={}
        roots=self.c.service.sources.data.get('cache_roots',[])
        if self.owner:
            children=volumes(self.owner);cached=sum(bool(self.c.service.cache.manifest(ch)) for ch in children)
            self.location.setText(f"{self.owner['title']} · 完整下载 {cached} / {len(children)} 个章节\n下载位置："+(roots[0] if roots else '尚未选择'))
            self.progress.setText('选择本书章节后下载；页面只在主动下载时落盘。' if self.allow_download else '这里只管理已有缓存；新下载请进入书籍详情页。')
            for ch in children:
                complete=self.c.service.cache.manifest(ch);partial=complete or self.c.service.cache.manifest(ch,False)
                if not self.allow_download and not partial:continue
                state='已下载' if complete else '部分下载 · 可继续' if partial else '未下载'
                item=QListWidgetItem(ch['title']+'  ·  '+state);item.setData(Qt.ItemDataRole.UserRole,ch['path']);self.records[ch['path']]={'chapters':[ch]};self.list.addItem(item)
                if ch['path'] in selected:item.setSelected(True)
            if not self.list.selectedItems() and self.list.count():
                path=self.owner.get('current_volume');match=next((self.list.item(i) for i in range(self.list.count()) if self.list.item(i).data(Qt.ItemDataRole.UserRole)==path),self.list.item(0));match.setSelected(True);self.list.setCurrentItem(match)
        else:
            groups=self.cached_books();self.location.setText(f'已缓存 {len(groups)} 本在线书籍 · {self.c.service.cache.size()/1024/1024:.1f} MiB\n这里只浏览和管理已有下载。新下载请前往对应书籍详情页。');self.progress.setText('选择书籍查看缓存章节，或前往书籍详情。')
            for group in groups:
                owner=group['owner'];key=owner['path'];complete=sum(bool(self.c.service.cache.manifest(ch)) for ch in group['chapters'])
                label=f"{owner['title']}  ·  已缓存 {len(group['chapters'])} 章（完整 {complete} 章）"
                if owner not in self.c.w.library.data['books']:label+=' · 已移出书库'
                item=QListWidgetItem(label);item.setData(Qt.ItemDataRole.UserRole,key);self.records[key]=group;self.list.addItem(item)
                if key in selected:item.setSelected(True)
    def selected(self):
        return [ch for i in self.list.selectedItems() for ch in self.records.get(i.data(Qt.ItemDataRole.UserRole),{}).get('chapters',[])]
    def chosen_owner(self):
        item=self.list.currentItem()
        return self.records.get(item.data(Qt.ItemDataRole.UserRole),{}).get('owner') if item else None
    def browse(self):
        owner=self.chosen_owner()
        if owner:DownloadsDialog(self.c,owner,inventory_only=True).exec()
    def open_detail(self):
        owner=self.chosen_owner()
        if owner in self.c.w.library.data['books']:self.accept();self.c.w.show_library(owner)
        elif owner:self.progress.setText('该作品已移出书库，仍可查看和清理缓存。')
    def download(self):
        if not self.allow_download:return
        selected=self.selected()
        if not selected:self.progress.setText('请先选择本书的章节');return
        if not self.c.service.sources.data.get('cache_roots'):self.choose()
        if self.c.service.sources.data.get('cache_roots'):
            self.c.download(selected);self.progress.setText(self.c.download_message)
    def resume(self):
        if self.allow_download:self.c.resume_downloads(self.owner);self.progress.setText(self.c.download_message)
    def pause(self):
        if self.owns_active_download():self.c.cancel_downloads();self.progress.setText(self.c.download_message)
    def clear(self):self.remove_cache(self.selected(),'清理所选缓存？')
    def remove_cache(self,chapters,title):
        if not chapters:return
        if self.c.download_active:QMessageBox.information(self,'正在下载','请先暂停队列并等待当前页面完成');return
        if QMessageBox.question(self,title,f'只删除 {len(chapters)} 个章节的离线缓存，保留书库进度和原图书。')!=QMessageBox.StandardButton.Yes:return
        for ch in chapters:self.c.service.cache.remove(ch)
        self.c.jobs.cache_changed.emit()
    def clear_all(self):
        self.remove_cache(volumes(self.owner) if self.owner else self.c.service.cache.all_volumes(),'清理本书下载？' if self.owner else '清理全部在线下载？')

class OnlineController(QObject):
    def __init__(self,w):
        super().__init__(w);self.w=w;self.service=core.OnlineService(w.runtime_root,w.library);core.SERVICE=self.service;self.jobs=Jobs(w);self.serial=0;self.search_serial=0;self.result_page=1;self.rows=[];self.cancel=threading.Event();self.download_active=False;self.active_download_paths=set();self.search_jobs=[];self.download_message='选择章节后下载，可多选。';self.closed=False
        self.discovery=QWidget();lay=QVBoxLayout(self.discovery);lay.setContentsMargins(32,26,32,20);lay.setSpacing(16)
        heading=QHBoxLayout();title=QLabel('发现在线漫画');title.setStyleSheet('font-size:28px;font-weight:600');heading.addWidget(title);heading.addStretch();back=QPushButton('返回书库');back.clicked.connect(w.show_library);heading.addWidget(back);lay.addLayout(heading)
        bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('输入作品名称，留空浏览热门');self.query.returnPressed.connect(self.search);bar.addWidget(self.query,1)
        search=QPushButton('搜索');button_role(search,'primary');search.clicked.connect(lambda:self.search());bar.addWidget(search);manage=QPushButton('管理书源');manage.clicked.connect(self.manage_sources);bar.addWidget(manage);lay.addLayout(bar)
        self.note=QLabel('混合搜索所有已启用书源；在书源管理中选择参与搜索的来源。');self.note.setWordWrap(True);lay.addWidget(self.note)
        self.results=QListWidget();self.results.setSpacing(8);self.results.itemDoubleClicked.connect(lambda _:self.add_selected());lay.addWidget(self.results,1)
        footer=QHBoxLayout();self.prev=QPushButton('上一页');self.prev.clicked.connect(lambda:self.search_page(-1));footer.addWidget(self.prev);self.next=QPushButton('下一页');self.next.clicked.connect(lambda:self.search_page(1));footer.addWidget(self.next);footer.addStretch();self.add=QPushButton('加入书库并查看章节');button_role(self.add,'primary');self.add.clicked.connect(self.add_selected);footer.addWidget(self.add);lay.addLayout(footer);w.pages.addWidget(self.discovery)
        actions=QHBoxLayout()
        self.prefetch_serial=0;self.prefetch_job=None;self.prefetch_jobs=[];self.preload_errors=[]
        for name,fn in [('在线发现',self.show),('书源管理',self.manage_sources),('下载与缓存',self.manage_downloads),('刷新在线目录',self.refresh_current)]:
            b=QPushButton(name);b.clicked.connect(fn);actions.addWidget(b)
        actions.addStretch();w.shelf.layout().insertLayout(1,actions)
        self.reader_quality=QPushButton('在线画质 / 预加载');self.reader_quality.clicked.connect(self.reading_settings);w.appearance.layout().insertWidget(0,self.reader_quality)
        w.shelf.online_downloads_requested.connect(lambda owner:DownloadsDialog(self,owner).exec());w.shelf.online_source_requested.connect(self.manage_sources);w.shelf.online_refresh_requested.connect(self.refresh_entry);w.shelf.online_cover_requested.connect(self.set_cover);self.refresh_sources();w.setWindowTitle('yukina漫画阅读器 · 在线版')
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
    def manage_downloads(self):
        owner=self.w.shelf.current() if self.w.shelf.stack.currentIndex()==1 else None
        DownloadsDialog(self,owner if owner and owner.get('online') else None).exec()
    def manage_sources(self):SourcesDialog(self).exec()
    def refresh_sources(self):
        fingerprint=json.dumps(self.service.sources.all,sort_keys=True)
        if fingerprint==getattr(self,'sources_fingerprint',None):return
        self.sources_fingerprint=fingerprint;self.search_serial+=1
        for job in self.search_jobs:job.cancel()
        self.rows=[];self.results.clear();self.add.setEnabled(False);self.prev.setEnabled(False);self.next.setEnabled(False)
        count=sum(s.get('enabled',True) for s in self.service.sources.all)
        self.note.setText(f'已启用 {count} 个书源，搜索时混合查询；可在书源管理中勾选来源。' if count else '尚未启用书源，请先打开书源管理。')
    def search_page(self,step):self.result_page=max(1,self.result_page+step);self.search(reset=False)
    def search(self,reset=True):
        sources=[dict(s) for s in self.service.sources.all if s.get('enabled',True)]
        if not sources:self.note.setText('请先在书源管理中启用至少一个书源');return
        if reset:self.result_page=1
        self.search_serial+=1;token=self.search_serial;page=self.result_page;term=self.query.text().strip()
        for job in self.search_jobs:job.cancel()
        self.search_jobs=[];self.search_pending={s['id'] for s in sources};self.search_results={};self.search_errors={};self.search_more={};self.rows=[];self.results.clear();self.prev.setEnabled(False);self.next.setEnabled(False);self.add.setEnabled(False)
        def update():
            selected=self.results.currentItem();selection=selected.data(Qt.ItemDataRole.UserRole) if selected else None
            lists=[self.search_results.get(s['id'],[]) for s in sources];self.rows=[];self.results.clear()
            for i in range(max((len(rows) for rows in lists),default=0)):
                for source,rows in zip(sources,lists):
                    if i>=len(rows):continue
                    book=dict(rows[i],source_id=source['id']);self.rows.append(book)
                    item=QListWidgetItem(book['title']+'\n'+source['name']);item.setData(Qt.ItemDataRole.UserRole,book);self.results.addItem(item)
                    if selection and (selection['source_id'],selection['id'])==(book['source_id'],book['id']):self.results.setCurrentItem(item)
            finished=len(sources)-len(self.search_pending);message=f'第 {page} 页 · {len(self.rows)} 部作品 · {finished}/{len(sources)} 个书源已返回'
            if self.search_pending:message+=' · 其余来源仍在搜索，可先查看已有结果'
            if self.search_errors:message+='\n'+'；'.join(next(s['name'] for s in sources if s['id']==sid)+'：'+error for sid,error in self.search_errors.items())
            self.note.setText(message);self.add.setEnabled(bool(self.rows));self.prev.setEnabled(page>1);self.next.setEnabled(any(self.search_more.values()))
        update()
        for source in sources:
            sid=source['id']
            def work(source=source):
                if token!=self.search_serial:return [],False
                core.BACKGROUND.active=True
                try:return core.Provider(source).search(term,page)
                finally:core.BACKGROUND.active=False
            def done(result,error,sid=sid):
                if token!=self.search_serial or self.closed:return
                self.search_pending.discard(sid)
                if error:self.search_errors[sid]=error
                else:
                    rows,more=result;seen=set();unique=[]
                    for book in rows:
                        if book['id'] not in seen:seen.add(book['id']);unique.append(book)
                    self.search_results[sid]=unique;self.search_more[sid]=more
                update()
            self.search_jobs.append(self.jobs.run(work,done,search=True))
    def add_selected(self):
        i=self.results.currentItem()
        if not i:return
        b=i.data(Qt.ItemDataRole.UserRole);s=self.service.sources.get(b['source_id']);self.add.setEnabled(False);self.note.setText('正在读取章节目录…')
        def work():
            p=self.service.provider(s['id']);chapters=p.chapters(b['id'])
            return chapters,None
        def done(result,error):
            self.add.setEnabled(True)
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
        chapters=list({ch['path']:ch for ch in chapters}.values())
        if not chapters:self.download_message='请先选择章节';return
        queue_file=self.w.runtime_root/'data/online-download-queue.json'
        try:existing=json.loads(queue_file.read_text('utf-8')) if queue_file.exists() else []
        except (OSError,ValueError):self.download_message='上次下载队列无法读取，原文件未覆盖';return
        if not isinstance(existing,list) or not all(isinstance(path,str) for path in existing):self.download_message='上次下载队列格式无效，原文件未覆盖';return
        pending=[ch['path'] for ch in chapters];other_pending=[path for path in existing if path not in pending]
        core.atomic_json(queue_file,other_pending+pending)
        self.cancel=threading.Event();self.download_active=True;self.active_download_paths=set(pending);self.download_message=f'正在下载 {len(chapters)} 个章节…'
        owners={ch['path']:owner['title'] for owner in self.w.library.data['books'] if owner.get('online') for ch in volumes(owner)}
        def work():
            successes=0;errors=[]
            for ch in chapters:
                if self.cancel.is_set():break
                try:
                    provider=self.service.provider(ch['online']['source_id']);self.service.cache.download(ch,provider,self.cancel,lambda n,total:self.jobs.progress.emit(ch['title'],n,total),book_title=owners.get(ch['path']));successes+=1
                except core.Cancelled:break
                except Exception as error:errors.append(ch['title']+'：'+str(error))
                pending.remove(ch['path']);core.atomic_json(queue_file,other_pending+pending)
            return successes,errors
        def done(result,error):
            self.download_active=False
            self.download_message=error or f'已完成 {result[0]} 个章节'+('；'+'；'.join(result[1]) if result[1] else '')+('；队列已暂停，可继续' if self.cancel.is_set() else '')
            self.w.statusBar().showMessage(self.download_message);self.w.refresh();self.jobs.cache_changed.emit()
        self.jobs.run(work,done,download=True)
    def resume_downloads(self,owner=None):
        try:
            queue=self.w.runtime_root/'data/online-download-queue.json'
            paths=json.loads(queue.read_text('utf-8')) if queue.exists() else []
            allowed={ch['path'] for ch in volumes(owner)} if owner else None;chapters=[]
            for path in paths:
                if allowed is not None and path not in allowed:continue
                try:chapters.append(self.service.find_volume(path))
                except core.OnlineError:pass
            if not chapters:self.download_message='本书没有待继续的队列' if owner else '没有待继续的队列';self.w.statusBar().showMessage(self.download_message);return
            self.download(chapters)
        except Exception as error:QMessageBox.warning(self.w,'队列无法恢复',str(error))
    def cancel_downloads(self):self.cancel.set();self.download_message='正在暂停，当前网络请求结束后停止；已完成页面会保留'
    def shutdown(self):self.closed=True;self.serial+=1;self.search_serial+=1;self.cancel.set();self.jobs.shutdown()
