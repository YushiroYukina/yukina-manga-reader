"""Bounded RAM-only online caches and quality processing. No filesystem writes."""
from collections import OrderedDict
import threading,time

class MemoryLru:
    def __init__(self,limit):self.limit=limit;self.bytes=0;self.items=OrderedDict();self.lock=threading.RLock()
    def get(self,key):
        with self.lock:
            item=self.items.get(key)
            if item is None:return None
            value,size,expires=item
            if expires and time.monotonic()>expires:self.items.pop(key);self.bytes-=size;return None
            self.items.move_to_end(key);return value
    def put(self,key,value,size,ttl=0):
        with self.lock:
            old=self.items.pop(key,None)
            if old:self.bytes-=old[1]
            if size>self.limit:return
            self.items[key]=(value,size,time.monotonic()+ttl if ttl else 0);self.bytes+=size
            while self.bytes>self.limit:
                _,old=self.items.popitem(last=False);self.bytes-=old[1]
    def clear(self):
        with self.lock:self.items.clear();self.bytes=0
    def discard(self,key):
        with self.lock:
            old=self.items.pop(key,None)
            if old:self.bytes-=old[1]

def quality_profile(quality,byte_count,pixels):
    if quality=='original':return None,None
    if quality=='low':return 1280,65
    return (1600,78) if byte_count>4*1024*1024 or pixels>12_000_000 else (2000,85)

def decode_page(data,quality):
    from PySide6.QtGui import QImageReader,QImage,QPainter
    from PySide6.QtCore import QBuffer,QByteArray,QIODevice,QSize,Qt
    buf=QBuffer();buf.setData(QByteArray(data));buf.open(QIODevice.OpenModeFlag.ReadOnly);reader=QImageReader(buf);size=reader.size()
    if not size.isValid() or size.width()*size.height()>120_000_000:raise ValueError('页面不是有效图片或尺寸过大')
    edge,jpeg=quality_profile(quality,len(data),size.width()*size.height())
    if edge and max(size.width(),size.height())>edge:reader.setScaledSize(size.scaled(QSize(edge,edge),Qt.AspectRatioMode.KeepAspectRatio))
    image=reader.read()
    if image.isNull():raise ValueError('图片解码失败')
    if quality=='original':return image,None
    if image.hasAlphaChannel():
        opaque=QImage(image.size(),QImage.Format.Format_RGB32);opaque.fill(Qt.GlobalColor.white);p=QPainter(opaque);p.drawImage(0,0,image);p.end();image=opaque
    target=QBuffer();target.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(target,'JPEG',jpeg):raise ValueError('图片压缩失败')
    packed=bytes(target.data())
    # Small existing JPEG/WebP/PNG pages can already be more efficient than a
    # fresh JPEG. Avoid increasing their byte size or degrading detail for no gain.
    if image.size()==size and len(packed)>=len(data):return image,data
    result=QImage.fromData(packed)
    if result.isNull():raise ValueError('图片压缩后解码失败')
    return result,packed

class PageMemory:
    def __init__(self):
        self.raw=MemoryLru(64*1024*1024);self.prepared=MemoryLru(32*1024*1024);self.images=MemoryLru(96*1024*1024);self.manifests=MemoryLru(2*1024*1024)
        self.guard=threading.Lock();self.flights={}
    def load(self,key,operation):
        # Coalesce only requests for the SAME page; other pages never wait on it.
        with self.guard:
            flight=self.flights.get(key);owner=flight is None
            if owner:flight={'event':threading.Event()};self.flights[key]=flight
        if not owner:
            flight['event'].wait()
            if 'error' in flight:raise flight['error']
            return flight['result']
        try:flight['result']=operation();return flight['result']
        except BaseException as e:flight['error']=e;raise
        finally:
            with self.guard:self.flights.pop(key,None);flight['event'].set()
    def clear(self):
        for cache in (self.raw,self.prepared,self.images,self.manifests):cache.clear()
