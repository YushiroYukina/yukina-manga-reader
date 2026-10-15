"""Smoke-test the packaged native window and immersive keyboard shortcuts."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys
import time

user32=ctypes.windll.user32
user32.SetProcessDPIAware()
user32.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD]
user32.MonitorFromWindow.restype=wintypes.HANDLE
user32.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.c_void_p]
class MonitorInfo(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]
process=subprocess.Popen([str(Path(sys.argv[1]).resolve())])
handles=[]
@ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
def find(hwnd,arg):
    pid=wintypes.DWORD(); user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd),ctypes.byref(pid))
    if pid.value==process.pid:
        text=ctypes.create_unicode_buffer(512); user32.GetWindowTextW(ctypes.c_void_p(hwnd),text,512)
        if text.value=='yukina漫画阅读器': handles.append(hwnd)
    return True
def rect(hwnd):
    bounds=wintypes.RECT(); user32.GetWindowRect(ctypes.c_void_p(hwnd),ctypes.byref(bounds))
    return (bounds.left,bounds.top,bounds.right,bounds.bottom)
def key(hwnd,value):
    user32.PostMessageW(ctypes.c_void_p(hwnd),0x100,value,0)
    user32.PostMessageW(ctypes.c_void_p(hwnd),0x101,value,0)
    time.sleep(.4)
try:
    time.sleep(2); user32.EnumWindows(find,0)
    assert handles, 'Main window missing'
    second=subprocess.Popen([str(Path(sys.argv[1]).resolve())])
    assert second.wait(timeout=5)==0, 'Repeat launch should reuse existing instance'
    assert process.poll() is None, 'Original reader must remain alive'
    print('Repeat launch reuses original instance: PASS')
    hwnd=handles[0]; user32.SetForegroundWindow(ctypes.c_void_p(hwnd)); time.sleep(.2)
    original=rect(hwnd)
    monitor=MonitorInfo(); monitor.size=ctypes.sizeof(monitor)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(wintypes.HWND(hwnd),2),ctypes.byref(monitor))
    work=monitor.work
    assert original[0]>=work.left and original[1]>=work.top and original[2]<=work.right and original[3]<=work.bottom, ('Window outside work area',original)
    key(hwnd,0x75)  # F6: enter reading from the new library home.
    key(hwnd,9); immersive=rect(hwnd)
    key(hwnd,27); restored=rect(hwnd)
    assert immersive!=original, (original,immersive)
    assert restored==original, (original,restored)
    print('Packaged window fully inside work area, Tab immersive and Esc restore: PASS',original)
finally:
    for hwnd in handles: user32.PostMessageW(ctypes.c_void_p(hwnd),0x10,0,0)
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
print('Exit code:',process.returncode)
