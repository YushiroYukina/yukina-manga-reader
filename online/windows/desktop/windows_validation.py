"""Opt-in native/frozen Windows workflow acceptance. Only a NEW QA directory is used."""
import hashlib,json,sys,time,threading,traceback
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from PySide6.QtCore import QTimer,Qt,QBuffer,QIODevice
from PySide6.QtGui import QImage,QColor,QPainter,QFont,QGuiApplication
from PySide6.QtWidgets import QApplication,QDialog,QPushButton,QComboBox,QCheckBox,QMessageBox

def main(output):
    if sys.platform!='win32':raise SystemExit('This acceptance targets Windows only.')
    root=Path(output).resolve()
    if root.exists():raise SystemExit('A NEW QA directory is required; existing data was not changed.')
    root.mkdir(parents=True);app=QApplication([])
    from app import Window
    from reader import Library,volumes
    from online_downloads import DownloadsDialog
    import online_core as core
    images=[]
    for n,color in enumerate(('#d6e9df','#bcd3e6','#ead6c0','#dfcdeb'),1):
        image=QImage(800,1100,QImage.Format.Format_RGB32);image.fill(QColor(color));p=QPainter(image);p.setPen(QColor('#264039'));p.setFont(QFont('Arial',32));p.drawText(image.rect(),Qt.AlignmentFlag.AlignCenter,f'YUKINA WINDOWS QA\nSYNTHETIC {n}');p.end();b=QBuffer();b.open(QIODevice.OpenModeFlag.WriteOnly);image.save(b,'PNG');images.append(bytes(b.data()))
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            requests.append(self.path);status=200
            if self.path.startswith('/page/'):
                data=images[int(self.path.rsplit('/',1)[1])-1];kind='image/png'
            elif self.path.startswith('/broken'):
                status=503;data=b'{"error":"synthetic unavailable source"}';kind='application/json'
            else:
                data=json.dumps({'books':[{'id':'demo','title':'雪色日和 · 合成漫画','chapters':[{'id':'ch1','title':'第 1 话','pages':['/page/1','/page/2','/page/3','/page/4']},{'id':'ch2','title':'第 2 话','pages':['/page/3','/page/4']}]}]},ensure_ascii=False).encode();kind='application/json'
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_address[1]}'
    library=Library(root/'data/library.json');w=Window(library,root);c=w.online_controller
    for s in c.service.sources.all:s['enabled']=False
    source_a={'id':'qa-A','name':'合成书源 A','type':'catalog','base_url':base+'/catalog-A.json','enabled':True};source_b=dict(source_a,id='qa-B',name='合成书源 B',base_url=base+'/catalog-B.json');broken=dict(source_a,id='qa-broken',name='合成失败来源',base_url=base+'/broken.json')
    for s in (source_a,source_b,broken):c.service.sources.put(s)
    c.refresh_sources();w.show();checks=[];state={'phase':0,'deadline':time.monotonic()+120};entries={};dialogs=[]
    report={'version':'0.1.4-windows-preview','frozen':bool(getattr(sys,'frozen',False)),'qtPlatform':QGuiApplication.platformName(),'checks':checks}
    def check(value,label):
        if not value:raise AssertionError(label)
        checks.append(label)
    def finish(error=None):
        timer.stop();report.update(success=error is None,checkCount=len(checks))
        if error:report['error']=error
        (root/'windows-workflow-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for d in dialogs:d.close()
        w.close();app.exit(2 if error else 0)
    def inspect_quality():
        try:
            dialog=next(d for d in app.topLevelWidgets() if isinstance(d,QDialog) and d.isVisible() and d.windowTitle()=='在线画质与预加载');boxes=dialog.findChildren(QComboBox);keys={boxes[0].itemData(i) for i in range(boxes[0].count())};check(keys=={'low','smooth','original'},'reading menu exposes three quality presets');check(dialog.findChildren(QCheckBox)[0].isChecked(),'preloading defaults enabled');dialog.grab().save(str(root/'reading-quality-menu.png'));dialog.reject();state['phase']=9
        except Exception:finish(traceback.format_exc())
    def step():
        try:
            if time.monotonic()>state['deadline']:raise TimeoutError('phase '+str(state['phase']))
            phase=state['phase']
            if phase==0:
                check(not c.discovery.findChildren(QComboBox),'search source dropdown removed');check(not any('画质' in b.text() for b in w.shelf.findChildren(QPushButton)),'no shelf quality entry');check(not any('画质' in b.text() for b in c.discovery.findChildren(QPushButton)),'no discovery quality entry');c.show();c.query.setText('雪色');c.search();state['phase']=1
            elif phase==1 and c.results.count()==2 and c.search_cache:
                check({b['source_id'] for b in c.rows}=={'qa-A','qa-B'},'mixed search preserves source-specific results');check('合成失败来源' in c.note.text(),'failed source does not hide successful results');c.discovery.grab().save(str(root/'mixed-search.png'));c.results.setCurrentRow(0);c.add_selected();state['phase']=2
            elif phase==2 and library.data['books'] and library.data['books'][0].get('online_cover'):
                entries['a']=library.data['books'][0];a=entries['a'];chapters=[v['online']['chapter'] for v in volumes(a)]
                for key,source in (('b',source_b),('c',dict(source_b,id='qa-C',name='未下载书籍来源'))):
                    c.service.sources.put(source);entry=core.merge_entry(source,{'id':'demo','title':'合成书籍 '+key,'cover':''},chapters);entry['cover_path']=a['online_cover'];library.data['books'].append(entry);entries[key]=entry
                library.save();w.show_library(a);check(w.shelf.online_download_btn.isVisible(),'online book detail exposes download/cache entry');w.grab().save(str(root/'book-detail.png'));c.service.sources.set_cache_root(root/'selected-downloads');d=DownloadsDialog(c,a);dialogs.append(d);d.show();state['book_dialog']=d;state['phase']=3
            elif phase==3 and state['book_dialog'].list.count()==2:
                d=state['book_dialog'];check(d.owner is entries['a'],'detail cache manager defaults to current book');check(all(d.list.item(i).data(Qt.ItemDataRole.UserRole)['path'].startswith(entries['a']['path']+'/') for i in range(d.list.count())),'detail chapter list excludes other books');d.grab().save(str(root/'single-book-cache.png'));d.list.setCurrentRow(0);d.download();state['phase']=4
            elif phase==4 and not c.download_active:
                a,b=entries['a'],entries['b'];check(c.service.cache.manifest(volumes(a)[0]) is not None,'download selected book chapter');check(c.service.cache.manifest(volumes(b)[0]) is None,'other book was not downloaded');state['book_dialog'].close();d=DownloadsDialog(c);dialogs.append(d);d.show();state['global_dialog']=d;state['phase']=5
            elif phase==5 and state['global_dialog'].list.count()==1:
                d=state['global_dialog'];check(d.download_button is None and d.resume_button is None,'global cache browser has no download or resume action');check(d.list.item(0).data(Qt.ItemDataRole.UserRole)['owner']['id']==entries['a']['id'],'global cache lists only already downloaded books');before=len(requests);d.download();check(len(requests)==before,'global browser cannot start a new network download');d.grab().save(str(root/'downloaded-library.png'));d.close();queue=root/'data/online-download-queue.json';core.atomic_json(queue,[volumes(entries['b'])[0]['path'],volumes(entries['c'])[0]['path']]);c.resume_downloads(entries['b']);state['phase']=6
            elif phase==6 and not c.download_active:
                a,b,unused=entries['a'],entries['b'],entries['c'];check(c.service.cache.manifest(volumes(b)[0]) is not None,'book-scoped queue resumes selected book');check(json.loads((root/'data/online-download-queue.json').read_text('utf-8'))==[volumes(unused)[0]['path']],'other book pending queue preserved');d=state['book_dialog'];question=QMessageBox.question;QMessageBox.question=lambda *a,**kw:QMessageBox.StandardButton.Yes
                try:d.clear_all()
                finally:QMessageBox.question=question
                check(c.service.cache.manifest(volumes(a)[0]) is None and c.service.cache.manifest(volumes(b)[0]) is not None,'clear current book does not clear other book cache');check(len(library.data['books'])==3,'cleanup preserves library entries');w.open_entry(b);state['phase']=7
            elif phase==7 and w.book and w.book.offline:
                check(bool(w.canvas.pages),'downloaded chapter renders offline');w.toggle_immersive();w.toggle_immersive_controls();w.settings_btn.click();check(w.immersive and c.reader_quality.isVisible(),'quality entry available inside immersive reading controls');state['phase']=8;QTimer.singleShot(100,inspect_quality);c.reader_quality.click()
            elif phase==9:
                check(w.immersive,'quality dialog preserves immersive mode');check(c.service.cache.manifest(volumes(entries['c'])[0]) is None,'untouched book has no downloaded pages');finish()
        except Exception:finish(traceback.format_exc())
    timer=QTimer();timer.timeout.connect(step);timer.start(50);code=app.exec();server.shutdown();server.server_close();thread.join(3);return code
