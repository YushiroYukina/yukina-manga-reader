"""Reading surface and transient, memory-only book-turn animation."""
import math
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QPolygonF, QTransform, QPen
from PySide6.QtWidgets import QWidget


class PageTurn(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.old = self.new = None
        self.progress = 0.0
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.valueChanged.connect(self.advance)
        self.animation.finished.connect(self.finish)
        self.hide()

    def start(self, old, new, bounds, side, duration, single=False, effect='book'):
        self.finish()
        self.old, self.new = old, new
        self.bounds, self.side = QRectF(bounds), side
        self.single = single
        self.effect = effect
        self.progress = 0.0
        self.setGeometry(self.parentWidget().rect())
        self.animation.setDuration(duration)
        self.show(); self.raise_(); self.animation.start()

    def advance(self, value):
        self.progress = float(value)
        self.update()

    def resize_viewport(self):
        """Keep an in-flight turn when fullscreen/layout changes the viewport."""
        previous = self.size()
        target = self.parentWidget().rect()
        if self.old is not None and previous.width() > 0 and previous.height() > 0:
            sx, sy = target.width()/previous.width(), target.height()/previous.height()
            r = self.bounds
            self.bounds = QRectF(r.x()*sx, r.y()*sy, r.width()*sx, r.height()*sy)
        self.setGeometry(target)
        if self.old is not None:
            self.raise_()
            self.update()

    def finish(self):
        self.animation.stop()
        self.hide()
        self.old = self.new = None

    def paintEvent(self, event):
        if self.old is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        viewport = QRectF(self.rect())
        if self.effect=='slide':
            width=viewport.width(); displacement=-self.side*width*self.progress
            painter.drawImage(viewport.translated(displacement,0),self.old)
            painter.drawImage(viewport.translated(displacement+self.side*width,0),self.new)
            return
        if self.effect=='cover':
            painter.drawImage(viewport,self.old)
            offset=self.side*viewport.width()*(1-self.progress)
            target=viewport.translated(offset,0)
            painter.drawImage(target,self.new)
            edge=target.right() if self.side<0 else target.left()
            shadow=QLinearGradient(edge-18,0,edge+18,0)
            shadow.setColorAt(0,QColor(0,0,0,0)); shadow.setColorAt(.5,QColor(0,0,0,int(65*math.sin(math.pi*self.progress)))); shadow.setColorAt(1,QColor(0,0,0,0))
            painter.fillRect(QRectF(edge-18,0,36,viewport.height()),shadow)
            return
        if self.effect=='fade':
            painter.drawImage(viewport,self.old); painter.setOpacity(self.progress); painter.drawImage(viewport,self.new)
            return
        painter.drawImage(viewport, self.new)
        r = self.bounds
        if self.single:
            self.paint_single(painter, viewport, r)
            return
        hinge = r.center().x()
        # The source leaf lifts toward the spine, then its reverse settles
        # over the opposite leaf. Reading direction also reverses the fold.
        source = QRectF(r.left() if self.side < 0 else hinge, r.top(), r.width()/2, r.height())
        target = QRectF(hinge if self.side < 0 else r.left(), r.top(), r.width()/2, r.height())
        painter.save()
        painter.setClipRect(target)
        painter.drawImage(viewport, self.old)
        painter.restore()
        t = self.progress
        cosine = math.cos(math.pi * t)
        extent = r.width()/2 * cosine * self.side
        lift = math.sin(math.pi*t) * min(52, r.height()*0.07)
        edge = hinge + extent
        left, right = min(hinge, edge), max(hinge, edge)
        # A soft moving shadow makes the turning leaf stand above the spread.
        shadow = QLinearGradient(edge-32, 0, edge+32, 0)
        shadow.setColorAt(0, QColor(0,0,0,0))
        shadow.setColorAt(.5, QColor(0,0,0,int(110*math.sin(math.pi*t))))
        shadow.setColorAt(1, QColor(0,0,0,0))
        painter.fillRect(QRectF(edge-32, r.top(), 64, r.height()), shadow)
        if abs(extent) < 0.7:
            return
        sample = source if t < .5 else target
        image = self.old if t < .5 else self.new
        # Project the outer edge inward and lift its corners for a paper-like
        # perspective, while keeping the spine fixed.
        top_left = QPointF(left, r.top()-lift if edge < hinge else r.top())
        top_right = QPointF(right, r.top()-lift if edge > hinge else r.top())
        bottom_left = QPointF(left, r.bottom()+lift if edge < hinge else r.bottom())
        bottom_right = QPointF(right, r.bottom()+lift if edge > hinge else r.bottom())
        quad = QPolygonF([top_left, top_right, bottom_right, bottom_left])
        src = QPolygonF([sample.topLeft(), sample.topRight(), sample.bottomRight(), sample.bottomLeft()])
        transform = QTransform()
        if QTransform.quadToQuad(src, quad, transform):
            painter.save()
            painter.setTransform(transform)
            painter.setClipRect(sample)
            painter.drawImage(viewport, image)
            painter.restore()
        shade = QLinearGradient(left, 0, right, 0)
        darkness = int(100 * math.sin(math.pi*t))
        shade.setColorAt(0, QColor(0,0,0,darkness if edge < hinge else 0))
        shade.setColorAt(.75, QColor(255,255,255,int(28*math.sin(math.pi*t))))
        shade.setColorAt(1, QColor(0,0,0,darkness if edge > hinge else 0))
        painter.setBrush(shade); painter.setPen(QPen(QColor(230,235,233,70), .6))
        painter.drawPolygon(quad)

    def paint_single(self, painter, viewport, r):
        """A single page lifts from its outside edge, revealing the next one."""
        t = self.progress
        hinge = r.right() if self.side < 0 else r.left()
        extent = r.width()*math.cos(math.pi*t/2)*self.side
        if abs(extent)<.7: return
        edge = hinge+extent
        left,right = min(edge,hinge),max(edge,hinge)
        lift = math.sin(math.pi*t)*min(40,r.height()*.05)
        quad = QPolygonF([
            QPointF(left,r.top()-lift if self.side<0 else r.top()),
            QPointF(right,r.top()-lift if self.side>0 else r.top()),
            QPointF(right,r.bottom()+lift if self.side>0 else r.bottom()),
            QPointF(left,r.bottom()+lift if self.side<0 else r.bottom())])
        src = QPolygonF([r.topLeft(),r.topRight(),r.bottomRight(),r.bottomLeft()])
        transform=QTransform()
        shadow=QLinearGradient(edge-28,0,edge+28,0)
        shadow.setColorAt(0,QColor(0,0,0,0)); shadow.setColorAt(.5,QColor(0,0,0,100)); shadow.setColorAt(1,QColor(0,0,0,0))
        painter.fillRect(QRectF(edge-28,r.top(),56,r.height()),shadow)
        if QTransform.quadToQuad(src,quad,transform):
            painter.save(); painter.setTransform(transform); painter.setClipRect(r)
            painter.drawImage(viewport,self.old); painter.restore()
        shade=QLinearGradient(left,0,right,0)
        shade.setColorAt(0,QColor(0,0,0,int(t*95) if self.side<0 else 0))
        shade.setColorAt(1,QColor(0,0,0,int(t*95) if self.side>0 else 0))
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(shade); painter.drawPolygon(quad)


class Canvas(QWidget):
    turn = Signal(int)
    exit_immersive = Signal()
    center_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.pages = []
        self.rtl = True
        self.zoom = 1.0
        self.mode = '适合窗口'
        self.gap = 24
        self.margin = 28
        self.background=QColor('#101416')
        self.setMinimumSize(200, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_pages(self, images, rtl, zoom, mode, gap=None):
        self.pages, self.rtl, self.zoom, self.mode = images, rtl, zoom, mode
        if gap is not None: self.gap = gap
        self.update_size(); self.update()

    def dimensions(self):
        if not self.pages: return (0, 0, 1)
        width = sum(p.width() for p in self.pages)
        height = max(p.height() for p in self.pages)
        viewport = self.parentWidget()
        gutter = self.gap * (len(self.pages)-1)
        w = max(50, viewport.width()-2*self.margin-gutter)
        h = max(50, viewport.height()-2*self.margin)
        factor = min(w/width, h/height) if self.mode == '适合窗口' else w/width if self.mode == '适合宽度' else 1
        return width, height, factor*self.zoom

    def page_rects(self):
        if not self.pages: return []
        w, h, scale = self.dimensions()
        total = w*scale + self.gap*(len(self.pages)-1)
        x = max(self.margin, (self.width()-total)/2)
        rects = []
        for page in reversed(self.pages) if self.rtl else self.pages:
            pw, ph = page.width()*scale, page.height()*scale
            rects.append(QRectF(x, max(self.margin,(self.height()-ph)/2), pw, ph))
            x += pw+self.gap
        return rects

    def update_size(self):
        w, h, scale = self.dimensions()
        gutter = self.gap*max(0,len(self.pages)-1)
        self.setMinimumSize(max(200, math.ceil(w*scale+gutter+2*self.margin)), max(200,math.ceil(h*scale+2*self.margin)))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.background)
        if not self.pages:
            painter.setPen(QColor('#9da9ac'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '右页先读，向左翻开\n\n导入本地图书，开始阅读\nPDF · EPUB · MOBI\n\n双击书名打开 · Tab 沉浸阅读')
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pages = list(reversed(self.pages)) if self.rtl else self.pages
        for page, rect in zip(pages, self.page_rects()):
            for radius in (9,6,3):
                painter.fillRect(rect.adjusted(-radius,-radius,radius,radius), QColor(0,0,0,15))
            painter.drawImage(rect, page)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            viewport=self.parentWidget()
            width=viewport.width() if viewport is not None else self.width()
            x=event.position().x()+(self.pos().x() if viewport is not None else 0)
            if .35*width<=x<=.65*width:
                self.center_clicked.emit()
            else:
                self.turn.emit(1 if (x<width/2)==self.rtl else -1)
        elif event.button() == Qt.MouseButton.RightButton:
            self.exit_immersive.emit()
