"""Verify actual Windows frame bounds on every attached monitor."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import tempfile
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app import Window
from reader import Library

app=QApplication([])
user32=ctypes.windll.user32
user32.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD]
user32.MonitorFromWindow.restype=wintypes.HANDLE
user32.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.c_void_p]
class MonitorInfo(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]
def check(w):
    frame=wintypes.RECT(); hwnd=wintypes.HWND(int(w.winId()))
    user32.GetWindowRect(hwnd,ctypes.byref(frame))
    info=MonitorInfo(); info.size=ctypes.sizeof(info)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd,2),ctypes.byref(info))
    a=info.work
    bounds=(frame.left,frame.top,frame.right,frame.bottom)
    assert frame.left>=a.left and frame.top>=a.top and frame.right<=a.right and frame.bottom<=a.bottom, (bounds,(a.left,a.top,a.right,a.bottom))
    print(w.screen().name(),bounds,'inside work area: PASS')
with tempfile.TemporaryDirectory() as directory:
    for i,screen in enumerate(app.screens()):
        w=Window(Library(Path(directory)/f'{i}.json'))
        w._startup_screen=screen; w.show(); QTest.qWait(150)
        assert w.screen().name()==screen.name()
        check(w)
        w.move(-10000,-10000); w.place_on_screen(screen); QTest.qWait(150); check(w)
        w.set_immersive(True); QTest.qWait(100); w.exit_immersive(); QTest.qWait(100); check(w)
        w.close()
