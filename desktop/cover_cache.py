"""Lazy disk thumbnails under the reader folder; MuPDF runs in a serial worker."""
import hashlib
import json
import sys
from collections import deque
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QProcess,QProcessEnvironment,QTimer
from reader import volumes

def cover_source(entry):
    if entry.get('cover_path'): return entry['cover_path'],'image'
    if entry.get('kind')=='folder':
        choices=volumes(entry)
        selected=entry.get('cover_volume')
        chosen=next((v for v in choices if v['path']==selected),choices[0] if choices else None) if selected else (choices[0] if choices else None)
        return (chosen['path'],'book') if chosen else ('','book')
    return entry['path'],'book'

class ThumbnailCache(QObject):
    ready=Signal(str)
    def __init__(self,runtime_root,parent=None):
        super().__init__(parent)
        self.runtime_root=Path(runtime_root).resolve()
        self.root=self.runtime_root/'cache'/'covers'
        self.enabled=self.root.drive.casefold()!='c:'
        self.queue=deque(); self.pending=set(); self.failed={}; self.active=None; self.buffer=b''
        self.process=QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(lambda:self.process.readAllStandardError())
        self.process.finished.connect(self.worker_finished)
        self.process.errorOccurred.connect(self.worker_error)
        self.watchdog=QTimer(self); self.watchdog.setSingleShot(True); self.watchdog.setInterval(45000)
        self.watchdog.timeout.connect(self.timeout)
        self.stopping=False
        self._cached_size=None

    def identity(self,entry):
        source,kind=cover_source(entry)
        if not source: return None,source,kind
        try:
            p=Path(source).resolve(strict=True); stat=p.stat()
            if not p.is_file(): return None,source,kind
            key=hashlib.sha256(json.dumps([str(p),kind,stat.st_mtime_ns,stat.st_size,1],ensure_ascii=True).encode()).hexdigest()
            return key,str(p),kind
        except OSError: return None,source,kind

    def request(self,entry):
        key,source,kind=self.identity(entry)
        if not key or not self.enabled: return None
        target=self.root/(key+'.png')
        if target.is_file(): return target
        if key not in self.pending and key not in self.failed:
            self.pending.add(key); self.queue.append({'id':key,'source':source,'kind':kind,'output':str(target)})
            QTimer.singleShot(0,self.pump)
        return None

    def pump(self):
        if self.stopping or self.active or not self.queue: return
        self.active=self.queue.popleft()
        if self.process.state()==QProcess.ProcessState.NotRunning:
            self.root.mkdir(parents=True,exist_ok=True)
            temp=self.runtime_root/'cache'/'worker-temp'; temp.mkdir(parents=True,exist_ok=True)
            env=QProcessEnvironment.systemEnvironment(); env.insert('TEMP',str(temp)); env.insert('TMP',str(temp)); env.insert('PYTHONDONTWRITEBYTECODE','1')
            self.process.setProcessEnvironment(env); self.process.setWorkingDirectory(str(self.runtime_root))
            if getattr(sys,'frozen',False):
                self.process.setProgram(sys.executable); self.process.setArguments(['--thumbnail-worker',str(self.root)])
            else:
                self.process.setProgram(sys.executable); self.process.setArguments([str(Path(__file__).with_name('thumbnail_worker.py')),str(self.root)])
            self.process.start()
        self.process.write((json.dumps(self.active,ensure_ascii=True)+'\n').encode())
        self.watchdog.start()

    def read_output(self):
        self.buffer+=bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try: reply=json.loads(line)
            except ValueError: continue
            if self.active and reply.get('id')==self.active['id']:
                self.watchdog.stop(); key=self.active['id']; self.pending.discard(key)
                if not reply.get('ok'): self.failed[key]=reply.get('error','封面提取失败')
                self._cached_size=None
                self.active=None; self.ready.emit(key); QTimer.singleShot(0,self.pump)

    def worker_error(self,error):
        if self.process.state()==QProcess.ProcessState.NotRunning: self.worker_finished()

    def worker_finished(self,*args):
        self.watchdog.stop(); self.buffer=b''
        failed_key=self.active['id'] if self.active else ''
        if self.active:
            key=self.active['id']; self.failed[key]='封面提取进程退出'; self.pending.discard(key); self.active=None
        if not self.stopping:
            self.ready.emit(failed_key); QTimer.singleShot(0,self.pump)

    def timeout(self):
        if self.active: self.failed[self.active['id']]='封面提取超时'
        self.process.kill()

    def stop(self):
        self.stopping=True; self.watchdog.stop(); self.queue.clear(); self.pending.clear(); self.active=None
        if self.process.state()!=QProcess.ProcessState.NotRunning:
            self.process.closeWriteChannel()
            if not self.process.waitForFinished(500):
                self.process.kill(); self.process.waitForFinished(500)
        self.buffer=b''

    def clear(self):
        self.stop()
        if self.enabled and self.root.exists():
            # Only known cache files directly under this fixed directory.
            for pattern in ('*.png','*.tmp'):
                for p in self.root.glob(pattern):
                    if p.is_file() and p.resolve().parent==self.root.resolve(): p.unlink()
        self.failed.clear(); self._cached_size=0; self.stopping=False; self.ready.emit('')

    def size(self):
        if self._cached_size is None:
            self._cached_size=sum(p.stat().st_size for p in self.root.glob('*.png') if p.is_file()) if self.root.exists() else 0
        return self._cached_size
