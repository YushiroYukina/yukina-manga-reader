from platform_support import FONT_FAMILY
"""Comfortable native Qt styling and code-drawn icons; no external assets."""
import sys
import re
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QPalette,QColor,QFont,QPainter,QPen,QPixmap,QIcon,QPainterPath
from PySide6.QtWidgets import QLabel,QSizePolicy

THEMES={
    'sage':('鼠尾草绿',142,False), 'ocean':('海湾蓝',210,False),
    'violet':('紫藤',265,False), 'rose':('玫瑰',340,False),
    'amber':('琥珀',35,False), 'paper':('暖纸白',45,True),
}
_ACTIVE_THEME='sage'

def theme_color(value,name=None):
    name=name or _ACTIVE_THEME
    color=QColor(value)
    if name=='sage' or name not in THEMES: return color
    _,hue,light=THEMES[name]
    h,s,v,a=color.getHsvF()
    if light:
        fixed={'#181e20':'#f3eee4','#101416':'#e5dfd2','#e7ebe5':'#333c32',
            '#a2c9b1':'#bdd0a9','#172c24':'#233a25','#e3e9df':'#333c32',
            '#1c392b':'#233a25',
            '#3a484a':'#cfc9bc','#303c3e':'#ded7c9','#303d3c':'#ded7c9',
            '#d6a49b':'#99554e','#584442':'#d6b7b0','#453232':'#efded9'}
        if value.lower() in fixed: return QColor(fixed[value.lower()])
        # Backgrounds and text trade lightness, with low saturation on paper.
        v=.97-v*.17 if v<.40 else .54-(v-.4)*.50
        s=min(s*.25,.07)
    elif value.lower() in ('#d6a49b','#584442','#453232','#9d736a'):
        return color
    else:
        s=min(.48,s*1.18)
    return QColor.fromHsvF(hue/360,s,max(0,min(1,v)),a)

def themed_css(css,name):
    return re.sub(r'#[0-9a-fA-F]{6}',lambda match:theme_color(match.group(),name).name(),css)

STYLESHEET='''
QWidget {color:#e7ebe5; font-family:"Microsoft YaHei UI"; font-size:14px;}
QMainWindow,QDialog {background:#181e20;}
QWidget#readerSidebar {background:#1e2729; border-right:1px solid #303b3c;}
QWidget#controlBar {background:#222c2e; border:1px solid #303c3e; border-radius:12px;}
QLabel {background:transparent; border:0;}
QLabel#eyebrow {color:#8baba2; font-size:11px; letter-spacing:2px;}
QLabel#muted {color:#97a7a8; font-size:12px;}
QLabel#metric {color:#bad8c8; background:#243330; border:1px solid #344b42; border-radius:10px; padding:9px 14px; font-size:13px;}
QPushButton {background:#2b3638; border:1px solid #3a484a; border-radius:9px; padding:8px 14px; min-height:18px; font-size:13px;}
QPushButton:hover {background:#354344; border-color:#60766f;}
QPushButton:pressed {background:#263733;}
QPushButton:focus {border-color:#afd0be;}
QPushButton:disabled {color:#6c7a7b; background:#20292b; border-color:#2c383a;}
QPushButton:checked {background:#344e43; border-color:#8fb8a2; color:#d8ecdd;}
QPushButton[role="primary"] {background:#a2c9b1; color:#172c24; border-color:#a2c9b1; font-weight:600;}
QPushButton[role="primary"]:hover {background:#b5d6bf; border-color:#b5d6bf;}
QPushButton[role="primary"]:pressed {background:#8bb89d;}
QPushButton[role="quiet"] {background:transparent; border-color:transparent; color:#afbeb9; padding:7px 10px;}
QPushButton[role="quiet"]:hover {background:#2a3637; color:#e3ece4;}
QPushButton[role="quiet"]:focus {border-color:#7fa890;}
QPushButton[role="quiet"]:checked {background:#344e43; border-color:#8fb8a2; color:#d8ecdd;}
QPushButton[role="danger"] {background:transparent; color:#d6a49b; border-color:#584442;}
QPushButton[role="danger"]:hover {background:#453232; border-color:#9d736a;}
QLineEdit,QComboBox,QSpinBox {background:#222c2e; border:1px solid #3a484a; border-radius:9px; padding:8px 11px; min-height:18px; selection-background-color:#486959; selection-color:#eef4ed;}
QLineEdit:focus,QComboBox:focus,QSpinBox:focus {border-color:#91b79e; background:#263234;}
QLineEdit:disabled {color:#748482; border-color:#2d3b3d;}
QComboBox {padding-right:25px; font-size:13px;}
QComboBox::drop-down {border:0; width:24px;}
QComboBox::down-arrow {image:url("@ASSETS@/chevron-down.svg"); width:14px; height:14px;}
QComboBox QAbstractItemView {background:#273335; border:1px solid #52655b; selection-background-color:#405c4c; padding:5px; outline:0;}
QSpinBox {padding-right:27px; font-size:13px;}
QSpinBox::up-button,QSpinBox::down-button {border:0; width:21px; background:transparent;}
QSpinBox::up-arrow {image:url("@ASSETS@/chevron-up.svg"); width:12px; height:12px;}
QSpinBox::down-arrow {image:url("@ASSETS@/chevron-down.svg"); width:12px; height:12px;}
QCheckBox,QRadioButton {spacing:8px; background:transparent; font-size:13px; padding:5px 0;}
QCheckBox::indicator {width:16px; height:16px; border:1px solid #657b6c; border-radius:4px; background:#222c2e;}
QCheckBox::indicator:checked {background:#a2c9b1; border-color:#a2c9b1; image:url("@ASSETS@/check.svg");}
QRadioButton::indicator {width:20px; height:20px; image:url("@ASSETS@/radio-off.svg");}
QRadioButton::indicator:checked {image:url("@ASSETS@/radio-on.svg");}
QListWidget {background:transparent; border:0; outline:0;}
QListWidget::item {padding:12px 8px; border:0; border-radius:8px; margin:2px 0; color:#aebab7;}
QListWidget::item:hover {background:#2a3537;}
QListWidget::item:selected {background:#354c42; color:#e2eee2;}
QTreeWidget {background:#1c2527; alternate-background-color:#212c2e; border:1px solid #303e40; border-radius:12px; outline:0;}
QTreeWidget::item {padding:10px 8px; border-bottom:1px solid #293638; color:#cbd6d0;}
QTreeWidget::item:hover {background:#2a3938;}
QTreeWidget::item:selected {background:#375247; color:#ecf3e9;}
QHeaderView::section {background:#283537; color:#9eb4ab; border:0; border-bottom:1px solid #3a4a48; padding:11px 8px; font-size:12px;}
QScrollArea {border:0; background:#101416;}
QScrollBar:vertical {background:transparent; width:9px; margin:4px 0;}
QScrollBar::handle:vertical {background:#4a5d59; border-radius:4px; min-height:32px;}
QScrollBar::handle:vertical:hover {background:#789889;}
QScrollBar:horizontal {background:transparent; height:9px; margin:0 4px;}
QScrollBar::handle:horizontal {background:#4a5d59; border-radius:4px; min-width:32px;}
QScrollBar::add-line,QScrollBar::sub-line {width:0; height:0;}
QScrollBar::add-page,QScrollBar::sub-page {background:transparent;}
QSplitter::handle {background:#303d3c; width:1px;}
QStatusBar {background:#181e20; color:#879a95; font-size:11px; padding:3px 12px; border-top:1px solid #2a3737;}
QStatusBar::item {border:0;}
QToolTip {background:#34473e; color:#eef3e8; border:1px solid #6e8e79; padding:8px;}
'''

def stylesheet(name='sage'):
    assets=(Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'assets').as_posix()
    css=themed_css(STYLESHEET,name).replace('@ASSETS@',assets).replace('Microsoft YaHei UI',FONT_FAMILY)
    for file in ('chevron-down.svg','chevron-up.svg','check.svg','radio-off.svg','radio-on.svg'):
        css=css.replace('/'+file,'/'+name+'-'+file)
    return css

def install_theme(app,name='sage'):
    global _ACTIVE_THEME
    _ACTIVE_THEME=name if name in THEMES else 'sage'
    if not app.property('migiComfortTheme'):
        app.setProperty('migiComfortTheme',True); app.setStyle('Fusion')
    palette=QPalette()
    for role,color in [(QPalette.ColorRole.Window,'#181e20'),(QPalette.ColorRole.WindowText,'#e7ebe5'),
        (QPalette.ColorRole.Base,'#222c2e'),(QPalette.ColorRole.AlternateBase,'#283537'),
        (QPalette.ColorRole.Text,'#e7ebe5'),(QPalette.ColorRole.Button,'#2b3638'),
        (QPalette.ColorRole.ButtonText,'#e7ebe5'),(QPalette.ColorRole.Highlight,'#486959'),
        (QPalette.ColorRole.HighlightedText,'#eef4ed'),(QPalette.ColorRole.PlaceholderText,'#80938c')]:
        palette.setColor(role,theme_color(color))
    app.setPalette(palette); app.setFont(QFont(FONT_FAMILY,10))

def button_role(button,role):
    button.setProperty('role',role)
    button.style().unpolish(button); button.style().polish(button)
    return button

_ICONS={}
def icon(name,color='#b9cdc1'):
    key=(name,color,_ACTIVE_THEME)
    if key in _ICONS: return _ICONS[key]
    pix=QPixmap(48,48); pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.scale(2,2)
    p.setPen(QPen(theme_color(color),1.6,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
    if name=='search':
        p.drawEllipse(QRectF(4,4,11,11)); p.drawLine(14,14,20,20)
    elif name=='folder':
        path=QPainterPath(QPointF(3,7)); path.lineTo(3,18); path.lineTo(21,18); path.lineTo(21,7); path.lineTo(11,7); path.lineTo(9,4); path.lineTo(3,4); path.closeSubpath(); p.drawPath(path)
    elif name=='book':
        path=QPainterPath(QPointF(12,6)); path.cubicTo(8,3,4,4,3,5); path.lineTo(3,19); path.cubicTo(7,17,10,18,12,20); path.cubicTo(14,18,17,17,21,19); path.lineTo(21,5); path.cubicTo(18,4,15,3,12,6); path.lineTo(12,20); p.drawPath(path)
    elif name=='library':
        for x in (4,9,14): p.drawRoundedRect(QRectF(x,4,3,16),.8,.8)
        p.drawLine(19,5,22,19)
    elif name=='focus':
        for x,y,dx,dy in [(4,4,1,1),(20,4,-1,1),(4,20,1,-1),(20,20,-1,-1)]:
            p.drawLine(x,y,x+5*dx,y); p.drawLine(x,y,x,y+5*dy)
    elif name=='clock':
        p.drawEllipse(QRectF(3,3,18,18)); p.drawLine(12,7,12,12); p.drawLine(12,12,16,14)
    elif name=='settings':
        for y,x in [(6,9),(12,16),(18,7)]:
            p.drawLine(3,y,21,y); p.setBrush(theme_color('#222c2e')); p.drawEllipse(QRectF(x-2,y-2,4,4))
    p.end(); result=QIcon(pix); _ICONS[key]=result; return result

class ElidedLabel(QLabel):
    """Keep long book titles readable without stretching the reading toolbar."""
    def __init__(self,*args):
        super().__init__(*args); self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(60); self.setMinimumHeight(36)
    def paintEvent(self,event):
        p=QPainter(self); p.setFont(self.font()); p.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        rect=self.contentsRect().adjusted(6,0,-6,0)
        p.drawText(rect,Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,self.fontMetrics().elidedText(self.text(),Qt.TextElideMode.ElideRight,max(0,rect.width())))
