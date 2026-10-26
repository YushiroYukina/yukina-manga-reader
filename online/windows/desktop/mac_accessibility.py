"""Avoid Qt 6.12 Cocoa's stale table-cell bridge for a painted card surface.

The card surface remains keyboard selectable. Its accessible description names
all visible titles; the separate detail view exposes full native controls.
"""
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QListWidget,QAccessibleWidget

class BookGrid(QListWidget):
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self.currentItem():
            self.itemActivated.emit(self.currentItem()); event.accept(); return
        super().keyPressEvent(event)

class CardSurfaceAccessibility(QAccessibleWidget):
    def __init__(self,widget):
        super().__init__(widget,QAccessible.Role.Pane)
    def childCount(self): return 0
    def child(self,index): return None
    def indexOfChild(self,child): return -1
    def focusChild(self): return None
    def text(self,kind):
        widget=self.object()
        if kind==QAccessible.Text.Name: return '书库封面列表'
        if kind==QAccessible.Text.Description:
            titles=[widget.item(i).text() for i in range(widget.count())]
            current=widget.currentItem()
            return ('当前选择：'+current.text()+'。' if current else '')+'使用方向键选择图书，回车进入详情。当前页：'+'、'.join(titles)
        return super().text(kind)

_interfaces=[]
def factory(class_name,obj):
    if isinstance(obj,BookGrid):
        interface=CardSurfaceAccessibility(obj); _interfaces.append(interface); return interface
    return None

if sys.platform=='darwin': QAccessible.installFactory(factory)
