"""Explicit isolated acceptance for source and frozen Windows/macOS applications."""
import hashlib,json,platform,sys,threading,time,traceback
from urllib.parse import unquote
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from PySide6.QtCore import QTimer,QBuffer,QIODevice,Qt
from PySide6.QtGui import QImage,QPainter,QColor,QFont,QGuiApplication
from PySide6.QtWidgets import QApplication

def live_main(output,selection,performance=False):
    """Explicit opt-in real-book UI acceptance; selection is JSON metadata only.

    Stores only the normal small cover thumbnail. No page/screenshot is saved.
    Never loads or writes the real user's library.
    """
    root=Path(output).resolve()
    if root.exists():raise SystemExit('Validation requires a NEW directory.')
    root.mkdir(parents=True);app=QApplication([])
    from app import Window
    from reader import Library
    import online_core as core
    selected=json.loads(Path(selection).read_text('utf-8-sig'));library=Library(root/'data/library.json')
    entry=selected['book'];entry.pop('online_cover',None);entry.pop('cover_path',None);entry['current_volume']=entry['volumes'][0]['path'];entry['volumes'][0]['page']=0
    library.data['books'].append(entry);library.save()
    sources=core.Sources(root/'data/online-sources.json');sources.put(selected['source'])
    requests=[];original_read=core.Http.read
    def measured_read(client,url,limit=core.PAGE_LIMIT):
        requests.append(time.monotonic());return original_read(client,url,limit)
    if performance:core.Http.read=measured_read
    w=Window(library,root);w.show();report={'frozen':bool(getattr(sys,'frozen',False)),'book':entry['title'],'qtPlatform':QGuiApplication.platformName(),'success':False};deadline=time.monotonic()+180;started=False
    phase=0;start=time.monotonic();previous=None;reopen_start=0;reopen_requests=0
    def finish(error=None):
        timer.stop();report['success']=error is None
        if error:report['error']=error
        report['pageDiskFiles']=len(list(root.rglob('*.img')));(root/'live-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');w.close();app.exit(0 if error is None else 2)
    def step():
        nonlocal started,phase,start,previous,reopen_start,reopen_requests
        try:
            if not started:w.open_entry(entry);started=True
            # Capture failures instead of leaving a modal dialog blocking unattended QA.
            from PySide6.QtWidgets import QMessageBox
            for widget in app.topLevelWidgets():
                if isinstance(widget,QMessageBox) and widget.isVisible():
                    error=widget.text();widget.accept();finish(error);return
            if w.book and getattr(w.book,'online',False) and entry.get('online_cover') and (not performance or phase==0):
                im=w.book.render(0);cover=Path(entry['online_cover'])
                if not cover.is_file() or im.isNull():raise AssertionError('Cover or rendered page missing')
                report.update(pageWidth=im.width(),pageHeight=im.height(),coverBytes=cover.stat().st_size,chapters=len(entry['volumes']))
                if not performance:finish();return
                report['coldOpenMs']=round((time.monotonic()-start)*1000,1);phase=1
            if performance and phase==1 and all(w.book.ready(i) for i in (1,2)):
                before=time.perf_counter();w.go(1,False);report['preloadedTurnMs']=round((time.perf_counter()-before)*1000,2)
                if w.page!=1:raise AssertionError('Preloaded double page was not immediately displayed')
                previous=w.book;w.show_library(entry);w.book.close();w.book=None
                w.library.data['settings']['online_preload']=False;reopen_requests=len(requests);reopen_start=time.monotonic();w.open_entry(entry);phase=2
            if performance and phase==2 and w.book is not None and w.book is not previous and w.page==1:
                report['reopenMs']=round((time.monotonic()-reopen_start)*1000,1);report['reopenRequests']=len(requests)-reopen_requests
                if report['reopenRequests']:raise AssertionError('Reopen unexpectedly fetched already resident pages')
                m=w.online_controller.service.memory;report['retainedCacheBytes']={'raw':m.raw.bytes,'prepared':m.prepared.bytes,'decoded':m.images.bytes};finish();return
            if time.monotonic()>deadline:
                if performance:report['preloadErrors']=w.online_controller.preload_errors;report['readyPages']=[i for i in range(min(6,len(w.book))) if w.book.ready(i)] if w.book else []
                finish('Timed out waiting for native page and cover')
        except Exception:finish(traceback.format_exc())
    timer=QTimer();timer.timeout.connect(step);timer.start(200);code=app.exec();return code

def main(output):
    root=Path(output).expanduser().resolve()
    if root.exists():raise SystemExit('Validation requires a NEW directory; existing data was not changed.')
    root.mkdir(parents=True);app=QApplication([]);app.setApplicationName('YukinaOnlineValidation')
    from platform_support import install_chinese_translation
    install_chinese_translation(app)
    from app import Window
    from reader import Library
    import online_core as core
    pages=[]
    for i,color in enumerate(('#d6e9df','#bcd3e6','#ead6c0','#dfcdeb'),1):
        image=QImage(800,1100,QImage.Format.Format_RGB32);image.fill(QColor(color));p=QPainter(image);p.setPen(QColor('#264039'));p.setFont(QFont('Arial',32));p.drawRect(40,40,720,1020);p.drawText(image.rect(),Qt.AlignmentFlag.AlignCenter,f'YUKINA ONLINE\nSYNTHETIC PAGE {i}');p.end();b=QBuffer();b.open(QIODevice.OpenModeFlag.WriteOnly);image.save(b,'PNG');pages.append(bytes(b.data()))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if unquote(self.path).startswith('/page/水星 完全版/'):
                data=pages[int(self.path.rsplit('/',1)[1])-1];kind='image/png'
            else:
                data=json.dumps({'books':[{'id':'demo','title':'雪色日和 · 合成验证','chapters':[{'id':'ch1','title':'第 1 话 · 出发','pages':['/page/水星 完全版/1','/page/水星 完全版/2','/page/水星 完全版/3','/page/水星 完全版/4']},{'id':'ch2','title':'第 2 话 · 归来','pages':['/page/水星 完全版/4','/page/水星 完全版/3']}]}]},ensure_ascii=False).encode('utf-8');kind='application/json'
            self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    library=Library(root/'data/library.json');w=Window(library,root);c=w.online_controller;s={'id':'acceptance','name':'本地合成书源','type':'catalog','base_url':f'http://127.0.0.1:{server.server_address[1]}/catalog.json','enabled':True};c.service.sources.put(s);
    builtin_ids={source['id'] for source in c.service.sources.all}
    for source in c.service.sources.all:source['enabled']=source['id']==s['id']
    c.refresh_sources();w.show();checks=[];state={'phase':0,'deadline':time.monotonic()+90};entry=None;original_hash=hashlib.sha256(pages[0]).hexdigest();report={'version':'0.1.4-windows-preview','platform':sys.platform,'machine':platform.machine(),'qtPlatform':QGuiApplication.platformName(),'frozen':bool(getattr(sys,'frozen',False)),'checks':checks,'originalPageHash':original_hash}
    def check(value,name):
        if not value:raise AssertionError(name)
        checks.append(name)
    def finish(error=None):
        timer.stop();report['success']=error is None
        if error:report['error']=error
        report['checkCount']=len(checks);(root/'online-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');w.close();app.exit(0 if error is None else 2)
    def step():
        nonlocal entry
        try:
            if time.monotonic()>state['deadline']:raise TimeoutError('phase '+str(state['phase']))
            phase=state['phase']
            if phase==0:
                check(all(key in builtin_ids for key in ('mangadex-zh','manhuagui-zh','mangapill-en','baozimh-org-zh','comicabc-zh','mangakatana-en')),'six built-in sources configured for mixed search')
                check('在线版' in w.windowTitle(),'independent online window title');check(w.runtime_root==root,'isolated validation data');check(QGuiApplication.platformName() in ('windows','cocoa','offscreen'),'native Qt platform identified');c.show();c.query.setText('雪色');c.search();state['phase']=1
            elif phase==1 and c.results.count()==1:
                check(w.pages.currentWidget() is c.discovery,'native source discovery');check(c.rows[0]['id']=='demo','HTTP search metadata');c.discovery.grab().save(str(root/'online-discovery.png'));c.results.setCurrentRow(0);c.add_selected();state['phase']=2
            elif phase==2 and library.data['books'] and library.data['books'][0].get('online_cover'):
                entry=library.data['books'][0];check(len(entry['volumes'])==2,'online chapters in shared library');check(Path(entry['online_cover']).is_file(),'first-page cover thumbnail');check(not c.service.sources.data.get('cache_roots'),'no implicit download destination');check(not list(root.rglob('*.img')),'online browsing writes no page files');library.set_reading_status(entry,'在读');library.set_reading_status(entry['volumes'][0],'自定义测试');w.open_entry(entry);state['phase']=3
            elif phase==3 and w.book and getattr(w.book,'online',False):
                check(len(w.book)==4,'online page count');check(bool(w.canvas.pages),'network page rendered');check(not w.book.offline,'first read streams from source');check(w.entry['reading_status']=='自定义测试','manual chapter status retained');w.go(2,True);state['phase']=4
            elif phase==4 and w.page==2 and not w.page_turn.isVisible():
                check(w.entry['page']==2,'native async page turn records progress');w.toggle_immersive();check(w.immersive,'immersive mode');w.toggle_immersive_controls();check(w.immersive and w.immersive_controls,'center controls preserve immersion');w.grab().save(str(root/'online-reader.png'));w.exit_immersive();w.show_library(entry);w.grab().save(str(root/'online-library.png'));c.service.sources.set_cache_root(root/'offline');c.download([entry['volumes'][0]]);state['phase']=5
            elif phase==5 and not c.download_active:
                volume=entry['volumes'][0];cached=c.service.cache.manifest(volume);check(cached is not None,'explicit chapter cache completes');check(len(cached[1]['pages'])==4,'offline manifest page count');check(len(list(cached[0].glob('*.img')))==4,'only selected chapter downloaded');check(json.loads((root/'data/online-download-queue.json').read_text('utf-8'))==[],'persistent queue consumed');s2=c.service.sources.get(s['id']);s2['enabled']=False;c.service.sources.save();w.open_entry(entry);state['phase']=6
            elif phase==6 and w.book and w.book.offline:
                check(bool(w.canvas.pages),'offline images rendered with source disabled');check(w.page==2,'offline reopen preserves page');check(entry['volumes'][0]['reading_status']=='自定义测试','offline reopen preserves custom status');check(hashlib.sha256(pages[0]).hexdigest()==original_hash,'source images unchanged');library.save();check(Library(library.path).find(entry['id']) is not None,'independent library reload');check(Path(c.service.sources.data['cache_roots'][0]).is_relative_to(root),'downloads stay inside selected test directory');finish()
        except Exception:finish(traceback.format_exc())
    timer=QTimer();timer.timeout.connect(step);timer.start(80)
    code=app.exec();server.shutdown();server.server_close();thread.join(timeout=3);print(json.dumps({'success':report.get('success'),'checks':len(checks),'report':str(root/'online-validation.json')},ensure_ascii=False));return code
