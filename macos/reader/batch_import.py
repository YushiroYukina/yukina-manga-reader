from platform_support import MULTI_FILE_TITLE, restore_after_native_dialog
"""Review a mixed list of files and folders before importing path references."""
from pathlib import Path
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,
    QListWidget,QListWidgetItem,QFileDialog,QListView,QTreeView,QAbstractItemView,
    QRadioButton,QCheckBox,QDialogButtonBox,QFileIconProvider)
from ui_theme import button_role,icon

class ChineseFileIconProvider(QFileIconProvider):
    def type(self,info):
        if info.isDir(): return '文件夹'
        return (info.suffix().upper()+' 文件') if info.suffix() else '文件'

class MultiFolderDialog(QFileDialog):
    def __init__(self,parent=None):
        super().__init__(parent,'选择多个文件夹（Command / Shift 多选）' if sys.platform=='darwin' else '选择多个文件夹（Ctrl / Shift 多选）')
        self.setOption(QFileDialog.Option.DontUseNativeDialog,True)
        self.setFileMode(QFileDialog.FileMode.Directory); self.setOption(QFileDialog.Option.ShowDirsOnly,True)
        self.setLabelText(QFileDialog.DialogLabel.Accept,'加入所选文件夹')
        self.setLabelText(QFileDialog.DialogLabel.Reject,'取消')
        self.setLabelText(QFileDialog.DialogLabel.LookIn,'位置：')
        self.setLabelText(QFileDialog.DialogLabel.FileName,'目录：')
        self.setLabelText(QFileDialog.DialogLabel.FileType,'文件类型：')
        self.chinese_icon_provider=ChineseFileIconProvider()
        self.setIconProvider(self.chinese_icon_provider)
        self.folders=[]
        for view in self.findChildren(QListView)+self.findChildren(QTreeView):
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def accept(self):
        self.folders=list(dict.fromkeys(str(Path(path).resolve()) for path in self.selectedFiles() if Path(path).is_dir()))
        if self.folders: QDialog.accept(self)

class BatchImportDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle('批量导入图书'); self.resize(740,560)
        layout=QVBoxLayout(self); layout.setContentsMargins(24,24,24,24); layout.setSpacing(14)
        title=QLabel('批量导入'); title.setStyleSheet('font-size:24px; font-weight:600;'); layout.addWidget(title)
        hint=QLabel('一次添加多个图书文件或文件夹，确认列表后统一导入。'); hint.setObjectName('muted'); layout.addWidget(hint)
        row=QHBoxLayout()
        files=QPushButton('添加图书文件'); files.setIcon(icon('book')); files.clicked.connect(self.choose_files); row.addWidget(files)
        folders=QPushButton('添加多个文件夹'); folders.setIcon(icon('folder')); folders.clicked.connect(self.choose_folders); row.addWidget(folders)
        remove=QPushButton('移出列表'); button_role(remove,'quiet'); remove.clicked.connect(self.remove_selected); row.addWidget(remove); row.addStretch(); layout.addLayout(row)
        self.items=QListWidget(); self.items.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); layout.addWidget(self.items,1)
        self.count=QLabel(); self.count.setObjectName('muted'); layout.addWidget(self.count)
        self.grouped=QRadioButton('每个文件夹合为一本多卷书'); self.grouped.setChecked(True); layout.addWidget(self.grouped)
        self.separate=QRadioButton('文件夹内的每个文件独立建书'); layout.addWidget(self.separate)
        self.recursive=QCheckBox('包含子文件夹'); self.recursive.setChecked(True); layout.addWidget(self.recursive)
        note=QLabel('单独选中的图书文件各自建书。只连接原路径；重复路径不会重复加入同类型书库记录。'); note.setWordWrap(True); note.setObjectName('muted'); layout.addWidget(note)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText('开始导入'); button_role(self.buttons.button(QDialogButtonBox.StandardButton.Ok),'primary')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject); layout.addWidget(self.buttons)
        self.update_count()

    def sources(self): return [self.items.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.items.count())]
    def add_sources(self,paths):
        known={path.casefold() for path in self.sources()}
        for path in paths:
            value=str(Path(path).resolve())
            if value.casefold() in known: continue
            item=QListWidgetItem(('文件夹  ' if Path(value).is_dir() else '图书  ')+value)
            item.setData(Qt.ItemDataRole.UserRole,value); item.setToolTip(value); self.items.addItem(item); known.add(value.casefold())
        self.update_count()
    def update_count(self):
        self.count.setText(f'待导入 {self.items.count()} 项 · 可用 Command / Shift 多选')
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.items.count()>0)
    def choose_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,MULTI_FILE_TITLE,'','漫画图书 (*.pdf *.epub *.mobi)')
        restore_after_native_dialog(self)
        self.add_sources(paths)
    def choose_folders(self):
        dialog=MultiFolderDialog(self)
        if dialog.exec()==QDialog.DialogCode.Accepted: self.add_sources(dialog.folders)
    def remove_selected(self):
        for item in self.items.selectedItems(): self.items.takeItem(self.items.row(item))
        self.update_count()
