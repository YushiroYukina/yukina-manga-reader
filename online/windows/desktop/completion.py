"""Explicit, queued read-completion confirmations; never infer a status silently."""
from PySide6.QtCore import QObject,QTimer,Qt
from PySide6.QtWidgets import QMessageBox
from reader import reading_status,volumes,spread


class CompletionPrompts(QObject):
    def __init__(self,window):
        super().__init__(window)
        self.window=window
        self.seen=set()
        self.pending=[]
        self.dialog=None
        self.closed=False
        self.timer=QTimer(self); self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.show_next)

    def key(self,entry):
        return ('folder' if entry.get('kind')=='folder' else 'file',entry.get('id') or entry['path'])

    def enqueue(self,entry):
        key=self.key(entry)
        if key in self.seen or reading_status(entry)=='已读': return
        self.seen.add(key); self.pending.append(entry)
        self.timer.start(int(self.window.speed.currentData())+80)

    def page_changed(self,entry,reached):
        if reached: self.enqueue(entry)
        else:
            self.seen.discard(self.key(entry))
            self.pending=[item for item in self.pending if item is not entry]

    def groups_changed(self):
        for entry in self.window.library.data['books']:
            if entry.get('kind')!='folder': continue
            children=volumes(entry)
            if children and all(reading_status(child)=='已读' for child in children): self.enqueue(entry)
            else:
                self.seen.discard(self.key(entry))
                self.pending=[item for item in self.pending if item is not entry]

    def eligible(self,entry):
        w=self.window
        if reading_status(entry)=='已读': return False
        if entry.get('kind')=='folder':
            return any(item is entry for item in w.library.data['books']) and bool(volumes(entry)) and all(reading_status(v)=='已读' for v in volumes(entry))
        return entry is w.entry and w.book is not None and w.pages.currentWidget() is w.split and spread(w.page,len(w.book),w.double.isChecked(),w.cover.isChecked())[-1]==len(w.book)-1

    def show_next(self):
        if self.closed or self.dialog is not None: return
        if self.window.page_turn.old is not None:
            self.timer.start(50)
            return
        while self.pending:
            entry=self.pending.pop(0)
            if not self.eligible(entry):
                self.seen.discard(self.key(entry)); continue
            group=entry.get('kind')=='folder'
            dialog=QMessageBox(self.window)
            dialog.setWindowTitle('合辑阅读完成' if group else '阅读完成')
            dialog.setIcon(QMessageBox.Icon.Question)
            title=entry.get('title','这本书')
            dialog.setText(f'《{title}》的所有分卷都已标为“已读”。\n是否将整本合辑也标为“已读”？' if group else f'已到达《{title}》的最后一页。\n是否将'+('本卷' if self.window.active_book is not entry else '这本书')+'标为“已读”？')
            dialog.setStandardButtons(QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            dialog.button(QMessageBox.StandardButton.Yes).setText('标为已读')
            dialog.button(QMessageBox.StandardButton.No).setText('暂不标记')
            dialog.setDefaultButton(QMessageBox.StandardButton.No)
            dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.dialog=dialog
            dialog.finished.connect(lambda result,entry=entry,dialog=dialog:self.answer(entry,dialog,result))
            dialog.open()
            return

    def answer(self,entry,dialog,result):
        self.dialog=None; dialog.deleteLater()
        if self.closed: return
        if result==int(QMessageBox.StandardButton.Yes) and self.eligible(entry):
            self.window.library.set_reading_status(entry,'已读')
            self.window.refresh()
            self.groups_changed()
        self.timer.start(0)

    def shutdown(self):
        self.closed=True; self.timer.stop(); self.pending.clear()
        if self.dialog is not None: self.dialog.reject()
