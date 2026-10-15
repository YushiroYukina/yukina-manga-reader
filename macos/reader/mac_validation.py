"""Opt-in local acceptance probe; uses isolated storage and read-only book paths."""
import os,sys,json,time,hashlib,struct,zipfile,shutil
from pathlib import Path
from PySide6.QtCore import Qt,QPoint,QPointF,QBuffer,QIODevice
from PySide6.QtGui import QImage,QColor,QWheelEvent,QFontDatabase,QAccessible
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from reader import Book,Library
from app import Window
from ui_theme import THEMES


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def png(color):
    image=QImage(200,300,QImage.Format.Format_RGB32); image.fill(QColor(color))
    buf=QBuffer(); buf.open(QIODevice.OpenModeFlag.WriteOnly); image.save(buf,'PNG'); return bytes(buf.data())


def samples(root):
    import pymupdf
    root.mkdir(parents=True,exist_ok=True)
    pdf=root/'测试漫画.pdf'; d=pymupdf.open()
    for color in ['red','green','blue','yellow','purple']:
        p=d.new_page(width=200,height=300); p.insert_image(p.rect,stream=png(color))
    d.save(pdf); d.close()
    epub=root/'测试漫画.epub'
    with zipfile.ZipFile(epub,'w') as z:
        z.writestr('mimetype','application/epub+zip')
        z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
        items=''.join(f'<item id="p{i}" href="p{i}.xhtml" media-type="application/xhtml+xml"/>' for i in range(5))
        spine=''.join(f'<itemref idref="p{i}"/>' for i in range(5))
        z.writestr('OPS/book.opf',f'<package xmlns="http://www.idpf.org/2007/opf"><manifest>{items}</manifest><spine>{spine}</spine></package>')
        for i,c in enumerate(['red','green','blue','yellow','purple']):
            z.writestr(f'OPS/p{i}.xhtml',f'<html><body><img src="img{i}.png"/></body></html>'); z.writestr(f'OPS/img{i}.png',png(c))
    mobi=root/'测试漫画.mobi'; html=b'<html><body><img recindex="1"/><img recindex="2"/></body></html>'
    h=bytearray(232); h[:4]=b'MOBI'
    for offset,value in [(4,232),(8,2),(12,65001),(16,1234),(20,6),(64,248),(68,4),(92,2),(108,0)]: struct.pack_into('>I',h,offset,value)
    for offset in [24,28,32,36,40,44,48,52,56,60,80,84,88]: struct.pack_into('>I',h,offset,0xffffffff)
    records=[struct.pack('>HHIHHHH',1,0,len(html),1,4096,0,0)+h+b'Test',html,png('red'),png('blue')]
    pdb=bytearray(78); pdb[:4]=b'Test'; pdb[60:68]=b'BOOKMOBI'; struct.pack_into('>H',pdb,76,len(records))
    offset=78+8*len(records)+2; table=b''
    for i,record in enumerate(records): table+=struct.pack('>II',offset,i); offset+=len(record)
    mobi.write_bytes(pdb+table+b'\0\0'+b''.join(records)); return [pdf,epub,mobi]


def main(root):
    root=Path(root).resolve(); root.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    report={'platform':app.platformName(),'frozen':bool(getattr(sys,'frozen',False)),'font':'PingFang SC' in QFontDatabase.families(),'screens':[(s.name(),s.geometry().getRect(),s.devicePixelRatio()) for s in app.screens()],'checks':[]}
    def check(name,condition,detail=None):
        report['checks'].append({'name':name,'pass':bool(condition),'detail':detail})
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        if not condition: raise AssertionError(name+': '+str(detail))
    paths=samples(root/'中文三格式样本'); before={str(p):digest(p) for p in paths}
    for p,n in zip(paths,[5,5,2]):
        b=Book(p); check(p.suffix+' pages',len(b)==n,len(b))
        check(p.suffix+' first red',b.render(0).pixelColor(20,20).name()=='#ff0000')
        for i in range(len(b)): check(p.suffix+f' render {i}',not b.render(i).isNull())
        b.close()
    # Optional user-supplied books only; never scan a developer's private folders.
    real=[Path(value).expanduser().resolve(strict=True)
          for value in json.loads(os.environ.get('MIGI_VALIDATION_BOOKS_JSON','[]'))]
    for p in real:
        if not p.exists(): continue
        h=digest(p); b=Book(p); count=len(b)
        for i in sorted(set([0,count//2,count-1])): check('real '+p.suffix+f' page {i}',not b.render(i,.4).isNull(),p.name)
        b.close(); check('real original hash '+p.suffix,h==digest(p),{'file':p.name,'pages':count,'sha256':h})
    lib=Library(root/'runtime/data/library.json'); check('independent empty library',len(lib.data['books'])==0)
    group_dir=root/'多卷'; group_dir.mkdir(exist_ok=True)
    # Generated fixtures only. Actual user books are never copied.
    shutil.copyfile(paths[0],group_dir/'卷10.pdf'); shutil.copyfile(paths[1],group_dir/'卷2.epub')
    mixed=lib.import_batch([*paths,group_dir,group_dir]); check('mixed dedupe',mixed['added']==4 and mixed['skipped']==1,mixed)
    group=next(e for e in lib.data['books'] if e.get('kind')=='folder')
    check('natural volumes',[v['title'] for v in group['volumes']]==['卷2','卷10'])
    check('ungrouped import',lib.import_batch([group_dir],grouped=False)['added']==2)
    w=Window(lib,root/'runtime'); w.show(); w.activateWindow(); QTest.qWait(1200)
    try:
        check('visible window',w.isVisible() and not w.isMinimized(),w.frameGeometry().getRect())
        w.grab().save(str(root/'library.png'))
        grid=w.shelf.grid
        for _ in range(3):
            interface=QAccessible.queryAccessibleInterface(grid)
            check('safe native accessibility',interface is not None and interface.childCount()==0)
            grid.setCurrentRow(0); grid.setFocus()
            QTest.keyClick(grid,Qt.Key.Key_Return); QTest.qWait(100)
            check('keyboard card detail',w.shelf.stack.currentIndex()==1)
            w.shelf.show_grid(); QTest.qWait(100)
            point=grid.visualItemRect(grid.item(0)).center()
            QTest.mouseClick(grid.viewport(),Qt.MouseButton.LeftButton,pos=point); QTest.mouseDClick(grid.viewport(),Qt.MouseButton.LeftButton,pos=point); QTest.qWait(100)
            check('double click card detail',w.shelf.stack.currentIndex()==1)
            w.shelf.show_grid(); QTest.qWait(100)
        for entry in lib.data['books'][:3]:
            w.open_entry(entry); QTest.qWait(200); check('GUI '+Path(entry['path']).suffix,bool(w.canvas.pages))
            if w.book.doc is not None: check('PDF Retina raster DPR',w.canvas.pages[0].devicePixelRatio()==max(1.0,min(3.0,w.devicePixelRatioF())))
        w.open_entry(lib.data['books'][1]); w.motion.setCurrentIndex(w.motion.findData('none'))
        page=w.page; QTest.mouseClick(w.canvas,Qt.MouseButton.LeftButton,pos=w.canvas.mapFrom(w.reading_viewport,QPoint(w.reading_viewport.width()//2,w.reading_viewport.height()//2)))
        check('ordinary center inert',w.page==page and not w.immersive_controls)
        w.set_immersive(True); QTest.qWait(1800)
        check('native fullscreen',w.isFullScreen()); w.grab().save(str(root/'immersive.png'))
        def geometry(): return (w.reading_viewport.size(),w.canvas.size(),w.canvas.page_rects(),w.scroll.horizontalScrollBar().value(),w.scroll.verticalScrollBar().value(),w.zoom.currentIndex(),w.isFullScreen())
        original=geometry(); QTest.mouseClick(w.canvas,Qt.MouseButton.LeftButton,pos=w.canvas.mapFrom(w.reading_viewport,QPoint(w.reading_viewport.width()//2,w.reading_viewport.height()//2))); QTest.qWait(200)
        check('overlay visible',w.immersive_controls); check('overlay geometry unchanged',original==geometry())
        w.grab().save(str(root/'overlay.png')); w.toggle_immersive_controls(); QTest.qWait(200); check('hide geometry unchanged',original==geometry())
        w.zoom.setCurrentIndex(4); QTest.qWait(500)
        w.scroll.horizontalScrollBar().setValue(w.scroll.horizontalScrollBar().maximum())
        w.scroll.verticalScrollBar().setValue(w.scroll.verticalScrollBar().maximum()//2); QTest.qWait(500)
        original=geometry()
        for _ in range(4):
            w.toggle_immersive_controls(); QTest.qWait(200)
            check('zoomed overlay geometry and scroll unchanged',original==geometry())
        w.zoom.setCurrentIndex(1); QTest.qWait(200)
        other=Window(Library(root/'inactive/data/library.json'),root/'inactive'); other.show(); other.raise_(); other.activateWindow(); QTest.qWait(1500)
        try:
            check('actual focus lost',not w.isActiveWindow())
            t=w.entry.get('reading_seconds',0); QTest.qWait(2300); w.sync_reading_time()
            check('immersive unfocused timer continues',w.entry['reading_seconds']-t>1.5,w.entry['reading_seconds']-t)
            w.pause_timer.setChecked(True); t=w.entry['reading_seconds']; QTest.qWait(1300); w.sync_reading_time(); check('manual pause',w.entry['reading_seconds']==t)
        finally: other.close()
        w.raise_(); w.activateWindow(); w.exit_immersive(); QTest.qWait(1800); check('fullscreen restored',not w.isFullScreen())
        w.pause_timer.setChecked(False); QTest.qWait(1100); w.sync_reading_time(); w.show_stats(); t=lib.data['stats']['total_reading_seconds']; QTest.qWait(1200); w.sync_reading_time(); check('stats pauses',t==lib.data['stats']['total_reading_seconds']); w.grab().save(str(root/'stats.png'))
        w.show_reader()
        for theme in THEMES:
            w.apply_color_scheme(theme); check('theme '+theme,w.canvas.pages[0].pixelColor(20,20).name()=='#ff0000')
        for effect in ('book','slide','cover','fade'):
            w.motion.setCurrentIndex(w.motion.findData(effect))
            for speed,ms in enumerate((260,420,650)):
                w.speed.setCurrentIndex(speed); w.go(0); w.turn(1)
                check('animation '+effect+' '+str(ms),w.page_turn.old is not None and w.page_turn.animation.duration()==ms)
                w.page_turn.finish()
        w.motion.setCurrentIndex(w.motion.findData('none')); w.speed.setCurrentIndex(1); w.go(0)
        check('no animation releases memory',w.page_turn.old is None)
        w.apply_color_scheme('sage'); w.fit.setCurrentIndex(2); w.zoom.setCurrentIndex(4); QTest.qWait(200)
        bar=w.scroll.verticalScrollBar(); bar.setValue(100); prior=bar.value()
        pos=QPointF(50,50); event=QWheelEvent(pos,QPointF(w.reading_viewport.mapToGlobal(QPoint(50,50))),QPoint(0,-35),QPoint(),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.ScrollUpdate,False)
        app.sendEvent(w.reading_viewport,event); check('reader pixel scroll',bar.value()>prior,(prior,bar.value()))
        # Force overflow then exercise a pan without triggering page turn.
        w.canvas.zoom=5; w.canvas.update_size(); QTest.qWait(100); bar.setValue(0); p=w.page
        QTest.mousePress(w.canvas,Qt.MouseButton.LeftButton,pos=QPoint(100,100)); QTest.mouseMove(w.canvas,QPoint(100,50)); QTest.mouseRelease(w.canvas,Qt.MouseButton.LeftButton,pos=QPoint(100,50)); check('drag pan no turn',bar.value()>0 and w.page==p,bar.value())
        sample_entry=next(e for e in lib.data['books'] if e.get('kind')!='folder' and e['path']==str(paths[1]))
        w.open_entry(sample_entry); w.go(3); w.completion.timer.stop(); w.completion.show_next()
        check('last spread confirmation visible',w.completion.dialog is not None)
        w.completion.dialog.button(QMessageBox.StandardButton.No).click(); QTest.qWait(100)
        w.display(); w.completion.show_next(); check('decline does not repeat',w.completion.dialog is None and sample_entry.get('reading_status','未标记')=='未标记')
        w.go(1); w.go(3); w.completion.timer.stop(); w.completion.show_next()
        w.completion.dialog.button(QMessageBox.StandardButton.Yes).click(); QTest.qWait(100)
        check('last page accepts read status',sample_entry['reading_status']=='已读')
        lib.set_reading_status(group['volumes'][0],'已读')
        w.open_entry(group,group['volumes'][1]['path']); w.go(3); w.completion.timer.stop(); w.completion.show_next()
        check('volume confirmation visible',w.completion.dialog is not None)
        w.completion.dialog.button(QMessageBox.StandardButton.Yes).click(); QTest.qWait(100)
        check('volume read independently',group['volumes'][1].get('reading_status')=='已读')
        for _ in range(30):
            if w.completion.dialog is not None: break
            QTest.qWait(100)
        check('collection separate confirmation',w.completion.dialog is not None and '所有分卷' in w.completion.dialog.text(),{'pending':len(w.completion.pending),'dialog':w.completion.dialog.text() if w.completion.dialog else None})
        w.completion.dialog.button(QMessageBox.StandardButton.No).click(); QTest.qWait(100)
        w.completion.groups_changed(); check('collection decline preserved',group.get('reading_status','未标记')=='未标记' and not w.completion.pending)
        lib.set_reading_status(group['volumes'][0],'搁置'); w.completion.groups_changed()
        lib.set_reading_status(group['volumes'][0],'已读'); w.completion.groups_changed(); w.completion.timer.stop(); w.completion.show_next()
        w.completion.dialog.button(QMessageBox.StandardButton.Yes).click(); QTest.qWait(100)
        check('collection accepts separately',group.get('reading_status')=='已读')
        w.open_entry(sample_entry); w.go(1); lib.set_reading_status(w.entry,'自己的状态'); w.apply_color_scheme('paper'); saved_id=w.active_book['id']; elapsed=lib.data['stats']['total_reading_seconds']
        for suffix in ('.pdf','.epub','.mobi'):
            entry=next(e for e in lib.data['books'] if e.get('kind')!='folder' and Path(e['path']).suffix==suffix)
            for _ in range(200):
                cover=w.shelf.covers.thumbnails.request(entry)
                if cover: break
                QTest.qWait(25)
            check('frozen cover '+Path(entry['path']).suffix,bool(cover),w.shelf.covers.thumbnails.failed)
        w.close(); check('worker exits',w.shelf.covers.thumbnails.process.state().value==0)
        restored=Library(lib.path); entry=restored.find(saved_id)
        check('save reload page status theme time',entry['page']==1 and entry['reading_status']=='自己的状态' and restored.data['settings']['theme']=='paper' and restored.data['stats']['total_reading_seconds']>=elapsed)
        check('sample hashes unchanged',before=={str(p):digest(p) for p in paths})
        check('no extracted pages',set(p.name for p in (root/'中文三格式样本').iterdir())==set(p.name for p in paths))
    finally:
        w.close()
    report['success']=True; (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)); return 0
