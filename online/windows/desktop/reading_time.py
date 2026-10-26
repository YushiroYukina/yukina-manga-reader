"""Monotonic reading accounting, independent of wall-clock adjustments."""
import time
from datetime import datetime,timedelta

def duration(seconds):
    seconds=max(0,int(seconds))
    hours,remainder=divmod(seconds,3600)
    minutes,seconds=divmod(remainder,60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'

class ReadingTracker:
    def __init__(self,library,now=time.monotonic,wall_now=lambda:datetime.now().astimezone()):
        self.library=library; self.now=now
        self.wall_now=wall_now; self.last_wall=None
        self.owner=self.volume=None
        self.running=False; self.last=None; self.saved_at=now(); self.dirty=False

    def select(self,owner,volume):
        self.update(False); self.flush()
        self.owner,self.volume=owner,volume

    def update(self,running):
        now=self.now()
        wall=self.wall_now()
        if self.running and self.last is not None and self.owner is not None:
            elapsed=now-self.last
            # A delayed heartbeat after sleep or a blocked event loop does not
            # count the unattended interval as active reading.
            if 0<elapsed<=5:
                self.owner['reading_seconds']=self.owner.get('reading_seconds',0)+elapsed
                if self.volume is not self.owner and self.volume is not None:
                    self.volume['reading_seconds']=self.volume.get('reading_seconds',0)+elapsed
                stats=self.library.data.setdefault('stats',{})
                stats['total_reading_seconds']=stats.get('total_reading_seconds',0)+elapsed
                # Monotonic time remains authoritative. A wall-clock jump only
                # changes the date bucket, never the amount of reading time.
                start=self.last_wall
                if start is None or abs((wall-start).total_seconds()-elapsed)>2:
                    start=wall-timedelta(seconds=elapsed)
                remaining=elapsed
                while remaining>1e-9:
                    midnight=(start+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
                    chunk=min(remaining,max(1e-6,(midnight-start).total_seconds()))
                    day=start.date().isoformat()
                    stats.setdefault('daily_started',day)
                    bucket=stats.setdefault('daily',{}).setdefault(day,{'seconds':0,'books':{}})
                    bucket['seconds']+=chunk
                    key=self.owner.get('id') or self.owner['path']
                    record=bucket['books'].setdefault(key,{'title':self.owner.get('title','未命名图书'),'seconds':0,'volumes':{}})
                    record['title']=self.owner.get('title',record['title']); record['seconds']+=chunk
                    if self.volume is not None and self.volume is not self.owner:
                        volume_key=self.volume.get('id') or self.volume['path']
                        volume=record['volumes'].setdefault(volume_key,{'title':self.volume.get('title','未命名分卷'),'seconds':0})
                        volume['title']=self.volume.get('title',volume['title']); volume['seconds']+=chunk
                    start+=timedelta(seconds=chunk); remaining-=chunk
                self.dirty=True
        self.last=now; self.last_wall=wall; self.running=bool(running and self.owner is not None)
        if self.dirty and now-self.saved_at>=15: self.flush()

    def flush(self):
        if self.dirty:
            self.library.save(); self.dirty=False
        self.saved_at=self.now()

    def stop(self):
        self.update(False); self.flush(); self.owner=self.volume=None
