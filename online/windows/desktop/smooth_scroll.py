"""Small pixel steps for mouse wheels; direct pixel input for touchpads."""
from PySide6.QtCore import QObject,QEvent,QVariantAnimation,QEasingCurve,Qt
from PySide6.QtWidgets import QAbstractItemView

class SmoothScroll(QObject):
    STEP=64
    def __init__(self,view):
        super().__init__(view)
        self.view=view; self.viewport=view.viewport(); self.bar=view.verticalScrollBar(); self.target=0.0
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.bar.setSingleStep(24)
        self.animation=QVariantAnimation(self); self.animation.setDuration(170)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.advance)
        self.viewport.installEventFilter(self)
        self.bar.sliderPressed.connect(self.stop)

    def stop(self,*args):
        self.animation.stop(); self.target=float(self.bar.value())

    def advance(self,value):
        if value is not None: self.bar.setValue(round(float(value)))

    def eventFilter(self,watched,event):
        if watched is self.viewport and event.type()==QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier: return False
            pixel=event.pixelDelta().y(); angle=event.angleDelta().y()
            if pixel:
                self.stop(); self.bar.setValue(self.bar.value()-pixel); self.target=float(self.bar.value())
                event.accept(); return True
            if not angle: return False
            if self.animation.state()!=QVariantAnimation.State.Running: self.target=float(self.bar.value())
            delta=max(-192,min(192,-angle/120*self.STEP))
            self.target=max(self.bar.minimum(),min(self.bar.maximum(),self.target+delta))
            # Prevent a long queue of scrolling after a fast wheel gesture ends.
            lead=max(160,min(360,self.view.viewport().height()/2))
            self.target=max(self.bar.value()-lead,min(self.bar.value()+lead,self.target))
            self.animation.stop(); self.animation.setStartValue(float(self.bar.value())); self.animation.setEndValue(float(self.target))
            self.animation.start(); event.accept(); return True
        if event.type()==QEvent.Type.Hide: self.animation.stop()
        elif event.type()==QEvent.Type.MouseButtonPress: self.stop()
        return False
