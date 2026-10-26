"""Windows download navigation: book detail owns network actions; shelf lists disk inventory."""
from pathlib import Path
from urllib.parse import unquote
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QListWidget,
    QListWidgetItem,QAbstractItemView,QFileDialog,QMessageBox)
from reader import volumes
from smooth_scroll import SmoothScroll

class DownloadsDialog(QDialog):
    def __init__(self,c,owner=None,existing_only=False,selected_path=None):
        super().__init__(c.w);self.c=c;self.owner=owner;self.existing_only=existing_only;self.selected_path=selected_path;self.groups={};self.refresh_token=0;self.opened_reader=False;self.navigated=False
        self.setWindowTitle(('本书下载与缓存 · '+owner['title']) if owner else '已下载的在线书籍');self.resize(920,640);lay=QVBoxLayout(self)
        title=QLabel(owner['title'] if owner else '已下载的在线书籍');title.setStyleSheet('font-size:23px;font-weight:600');lay.addWidget(title)
        hint=QLabel('选择章节下载或继续未完成的下载；仅管理当前书籍。' if owner and not existing_only else '这里只浏览、打开或清理已有缓存。新增下载请进入具体书籍的详情页。');hint.setWordWrap(True);lay.addWidget(hint)
        self.location=QLabel();self.location.setWordWrap(True);lay.addWidget(self.location)
        select=QPushButton('管理独立缓存路径');select.clicked.connect(self.choose);lay.addWidget(select)
        self.list=QListWidget();self.list.scroll_motion=SmoothScroll(self.list);self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);lay.addWidget(self.list,1)
        self.list.itemDoubleClicked.connect(lambda _:self.open_selected())
        row=QHBoxLayout();lay.addLayout(row);self.download_button=None;self.resume_button=None
        if owner and not existing_only:
            self.download_button=QPushButton('下载所选 / 继续');self.download_button.clicked.connect(self.download);row.addWidget(self.download_button)
            self.resume_button=QPushButton('继续本书队列');self.resume_button.clicked.connect(lambda:self.c.resume_downloads(self.owner));row.addWidget(self.resume_button)
        open_btn=QPushButton('打开已下载章节' if owner else '查看本书缓存');open_btn.clicked.connect(self.open_selected);row.addWidget(open_btn)
        if owner is None or existing_only:
            detail_btn=QPushButton('进入书籍详情');detail_btn.clicked.connect(self.open_book_detail);row.addWidget(detail_btn)
        for label,fn in [('暂停当前队列',self.pause),('清理所选缓存',self.clear),('清理本书全部缓存' if owner else '清理全部已有缓存',self.clear_all),('刷新',self.refresh)]:
            b=QPushButton(label);b.clicked.connect(fn);row.addWidget(b)
        self.progress=QLabel(c.download_message);self.progress.setWordWrap(True);lay.addWidget(self.progress);c.jobs.progress.connect(self.update_progress);self.refresh()
    def update_progress(self,title,n,total):self.progress.setText(f'{title} · {n} / {total} 页')
    def pause(self):self.c.cancel_downloads();self.progress.setText(self.c.download_message)
    def choose(self):
        path=QFileDialog.getExistingDirectory(self,'选择独立缓存的父目录')
        if path:
            try:self.c.service.sources.set_cache_root(path);self.refresh()
            except Exception as e:QMessageBox.warning(self,'目录不可用',str(e))
    def refresh(self):
        self.refresh_token+=1;token=self.refresh_token;self.list.clear();self.location.setText('正在读取本机已有缓存…')
        owners={e['path']:e for e in self.c.w.library.data['books'] if e.get('online')}
        known={v['path']:v for e in owners.values() for v in volumes(e)}
        def work():
            inventory=self.c.service.cache.all_volumes();metadata={}
            targets=volumes(self.owner) if self.owner else inventory
            for ch in targets:metadata[ch['path']]=self.c.service.cache.manifest(ch,False)
            return inventory,metadata,self.c.service.cache.size()
        def done(result,error):
            if token!=self.refresh_token:return
            if error:self.location.setText('读取缓存失败：'+error);return
            inventory,metadata,size=result;roots=self.c.service.sources.data.get('cache_roots',[])
            self.location.setText('当前路径：'+(roots[0] if roots else '尚未选择')+f'\n已有下载 {size/1048576:.1f} MiB；切换路径后仍可管理旧路径中的缓存。')
            if self.owner:
                for ch in volumes(self.owner):
                    cached=metadata.get(ch['path'])
                    if self.existing_only and not cached:continue
                    status=('已下载' if cached[1].get('complete') else f"未完成 · 已有 {len(cached[1].get('pages',[]))} 页") if cached else '未下载'
                    item=QListWidgetItem(ch['title']+'  ·  '+status);item.setData(Qt.ItemDataRole.UserRole,ch);self.list.addItem(item)
                    if ch['path']==(self.selected_path or self.owner.get('current_volume')):self.list.setCurrentItem(item)
            else:
                self.groups={}
                for cached in inventory:
                    path=cached['path'];book_path=cached.get('book_path') or path.rsplit('/',1)[0];owner=owners.get(book_path)
                    title=owner['title'] if owner else cached.get('book_title') or ('已移出书库 · '+unquote(book_path.rsplit('/',1)[-1]))
                    group=self.groups.setdefault(book_path,{'title':title,'owner':owner,'path':book_path,'chapters':[]});group['chapters'].append(known.get(path,cached))
                for group in self.groups.values():
                    complete=sum(bool(metadata.get(ch['path']) and metadata[ch['path']][1].get('complete')) for ch in group['chapters'])
                    item=QListWidgetItem(f"{group['title']}\n{complete} 个完整章节 · {len(group['chapters'])-complete} 个未完成章节");item.setData(Qt.ItemDataRole.UserRole,group);self.list.addItem(item)
            if not self.list.count():self.progress.setText('本书还没有已有缓存。' if self.owner else '还没有已下载书籍；请到书籍详情页下载章节。')
        self.c.jobs.run(work,done)
    def selected(self):
        if self.owner:return [i.data(Qt.ItemDataRole.UserRole) for i in self.list.selectedItems()]
        return [ch for i in self.list.selectedItems() for ch in i.data(Qt.ItemDataRole.UserRole)['chapters']]
    def download(self):
        if self.owner is None or self.existing_only:return
        selected=self.selected()
        if not selected:self.progress.setText('请先选择需要下载的章节');return
        if not self.c.service.sources.data.get('cache_roots'):self.choose()
        if self.c.service.sources.data.get('cache_roots'):self.c.download(selected);self.progress.setText(self.c.download_message)
    def open_selected(self):
        item=self.list.currentItem()
        if not item:return
        value=item.data(Qt.ItemDataRole.UserRole)
        if self.owner:
            if self.c.service.cache.manifest(value) is None:QMessageBox.information(self,'尚未完整下载','该章节尚未完整下载。请在本书下载界面继续。');return
            if self.c.w.library.find(self.owner.get('id','')) is None:QMessageBox.information(self,'书籍已移出书库','这里可以管理其缓存；如需阅读，请重新加入书库。');return
            actual=self.c.w.library.find(self.owner['id'])
            if not any(v['path']==value['path'] for v in volumes(actual)):QMessageBox.information(self,'章节不在书库目录','此缓存章节已不在当前目录中，可以在这里清理缓存。');return
            self.c.w.open_entry(actual,value['path']);self.opened_reader=True;self.navigated=True;self.accept()
        else:
            owner=dict(value['owner'] or {'title':value['title'],'path':value['path'],'kind':'folder'},volumes=value['chapters'])
            child=DownloadsDialog(self.c,owner,existing_only=True);child.exec()
            if child.navigated:self.opened_reader=child.opened_reader;self.navigated=True;self.accept()
            else:self.refresh()
    def open_book_detail(self):
        item=self.list.currentItem();record=self.owner if self.owner else item.data(Qt.ItemDataRole.UserRole).get('owner') if item else None
        actual=self.c.w.library.find(record.get('id','')) if record else None
        if actual is None:QMessageBox.information(self,'未找到书籍','请先选择仍在书库中的书籍；移出书库的缓存仍可清理。');return
        self.c.w.show_library(actual);self.navigated=True;self.accept()
    def clear(self):self._clear(self.selected())
    def clear_all(self):self._clear(self.c.service.cache.all_volumes() if self.owner is None else [v for v in volumes(self.owner) if self.c.service.cache.manifest(v,False)])
    def _clear(self,chapters):
        if self.c.download_active:QMessageBox.information(self,'正在下载','请先暂停队列并等待当前页面完成');return
        if chapters and QMessageBox.question(self,'清理已有缓存？',f'仅删除 {len(chapters)} 个章节的下载缓存，保留书库、进度与原图书。')==QMessageBox.StandardButton.Yes:
            for ch in chapters:self.c.service.cache.remove(ch)
            self.refresh()
