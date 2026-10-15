"""在 Windows 原生 Qt 平台验证字体、窗口及布局。"""
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from app import Window
app = QApplication([])
app.setFont(QFont('Microsoft YaHei UI', 10))
print('Chinese font:', 'Microsoft YaHei UI' in QFontDatabase.families())
w = Window(); w.show(); app.processEvents()
w.grab().save('preview.png')
w.close()
