"""Serial thumbnail renderer. Only the explicitly supplied non-C cache is writable."""
import json
import sys
import os
from pathlib import Path
from PySide6.QtCore import QCoreApplication,QSize,QSaveFile,QIODevice
from PySide6.QtGui import QImage,QImageReader,QPainter,QColor
from reader import Book
from platform_support import bundle_contains

SIZE=QSize(420,600)

def render_thumbnail(source,kind,output,cache_root):
    root=Path(cache_root).resolve()
    if sys.platform=='darwin' and bundle_contains(root): raise ValueError('禁止在 .app 内写入缩略图缓存')
    if sys.platform=='win32' and root.drive.casefold()=='c:': raise ValueError('禁止在 C 盘写入缩略图缓存')
    target=Path(output).resolve()
    if target.parent!=root or target.suffix.lower()!='.png': raise ValueError('缩略图输出必须位于指定缓存文件夹内')
    if kind=='image':
        reader=QImageReader(str(source)); reader.setAutoTransform(True)
        if reader.size().isValid(): reader.setScaledSize(reader.size().scaled(SIZE,Qt.AspectRatioMode.KeepAspectRatio))
        image=reader.read()
    else:
        book=Book(source)
        try:
            scale=1
            if book.doc:
                rect=book.doc.load_page(0).rect
                scale=min(SIZE.width()/rect.width,SIZE.height()/rect.height)
            image=book.render(0,scale)
        finally: book.close()
    if image.isNull(): raise ValueError('无法读取封面内容')
    image=image.scaled(SIZE,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
    result=QImage(SIZE,QImage.Format.Format_RGB32); result.fill(QColor('#29373d'))
    painter=QPainter(result); painter.drawImage((SIZE.width()-image.width())//2,(SIZE.height()-image.height())//2,image); painter.end()
    root.mkdir(parents=True,exist_ok=True)
    file=QSaveFile(str(target))
    if not file.open(QIODevice.OpenModeFlag.WriteOnly): raise OSError(file.errorString())
    if not result.save(file,'PNG'):
        file.cancelWriting(); raise OSError('无法写入缩略图')
    if not file.commit(): raise OSError(file.errorString())

def attach_redirected_stdio():
    # PyInstaller's windowed bootloader sets sys.std* to None, even when
    # QProcess supplies Windows pipe handles. Reattach those inherited pipes.
    if sys.platform=='darwin':
        for name,fd,mode in [('stdin',0,'r'),('stdout',1,'w'),('stderr',2,'w')]:
            if getattr(sys,name) is None:
                setattr(sys,name,os.fdopen(os.dup(fd),mode,encoding='utf-8',buffering=1))
    if sys.platform=='win32' and (sys.stdin is None or sys.stdout is None):
        import ctypes,msvcrt
        from ctypes import wintypes
        kernel=ctypes.windll.kernel32
        kernel.GetStdHandle.argtypes=[wintypes.DWORD]; kernel.GetStdHandle.restype=wintypes.HANDLE
        for name,identifier,flags,mode in [('stdin',-10,os.O_RDONLY,'r'),('stdout',-11,os.O_WRONLY,'w'),('stderr',-12,os.O_WRONLY,'w')]:
            if getattr(sys,name) is not None: continue
            handle=kernel.GetStdHandle(identifier & 0xffffffff)
            if handle and handle!=ctypes.c_void_p(-1).value:
                fd=msvcrt.open_osfhandle(handle,flags|os.O_BINARY)
                setattr(sys,name,os.fdopen(fd,mode,encoding='utf-8',buffering=1))

def main(cache_root):
    attach_redirected_stdio()
    app=QCoreApplication.instance() or QCoreApplication([])
    for line in sys.stdin:
        job={}
        try:
            job=json.loads(line)
            render_thumbnail(job['source'],job['kind'],job['output'],cache_root)
            reply={'id':job['id'],'ok':True}
        except Exception as error: reply={'id':job.get('id'),'ok':False,'error':str(error)}
        print(json.dumps(reply,ensure_ascii=True),flush=True)
    return 0

from PySide6.QtCore import Qt
if __name__=='__main__': sys.exit(main(sys.argv[1]))
