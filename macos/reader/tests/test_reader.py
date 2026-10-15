import hashlib
import os
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import QBuffer, QIODevice, Qt,QPoint
from PySide6.QtTest import QTest
import pymupdf
from reader import Book, Library, spread
from app import Window

APP = QApplication.instance() or QApplication([])
TEST_TEMP_ROOT=Path(__file__).resolve().parent.parent / "qa-temp"
TEST_TEMP_ROOT.mkdir(exist_ok=True)
def temporary_directory(): return tempfile.TemporaryDirectory(dir=TEST_TEMP_ROOT)

def png(color):
    image = QImage(200, 300, QImage.Format.Format_RGB32); image.fill(QColor(color))
    buffer = QBuffer(); buffer.open(QIODevice.OpenModeFlag.WriteOnly); image.save(buffer, 'PNG')
    return bytes(buffer.data())

def fixtures(folder):
    folder = Path(folder)
    pdf = folder / '测试漫画.pdf'
    doc = pymupdf.open()
    for color in ['red', 'green', 'blue', 'yellow', 'purple']:
        page = doc.new_page(width=200, height=300); page.insert_image(page.rect, stream=png(color))
    doc.save(pdf); doc.close()
    epub = folder / '测试漫画.epub'
    with zipfile.ZipFile(epub, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip')
        z.writestr('META-INF/container.xml', '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        items = ''.join(f'<item id="p{i}" href="p{i}.xhtml" media-type="application/xhtml+xml"/><item id="i{i}" href="img{i}.png" media-type="image/png"/>' for i in range(5))
        spine = ''.join(f'<itemref idref="p{i}"/>' for i in range(5))
        z.writestr('OPS/book.opf', f'<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>测试漫画</dc:title><dc:identifier id="id">test</dc:identifier><dc:language>ja</dc:language></metadata><manifest>{items}</manifest><spine>{spine}</spine></package>')
        for i, color in enumerate(['red', 'green', 'blue', 'yellow', 'purple']):
            z.writestr(f'OPS/p{i}.xhtml', f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Page</title></head><body><img src="img{i}.png"/></body></html>')
            z.writestr(f'OPS/img{i}.png', png(color))
    # 无压缩 MOBI6，合法 Palm 数据库结构，图片内嵌记录。
    mobi = folder / '测试漫画.mobi'
    html = b'<html><body><img recindex="1"/><mbp:pagebreak/><img recindex="2"/></body></html>'
    header = bytearray(232)
    header[:4] = b'MOBI'
    for offset, value in [(4,232),(8,2),(12,65001),(16,1234),(20,6),(64,248),(68,4),(92,2),(108,0)]:
        struct.pack_into('>I',header,offset,value)
    for offset in [24,28,32,36,40,44,48,52,56,60,80,84,88]: struct.pack_into('>I',header,offset,0xffffffff)
    palm = struct.pack('>HHIHHHH', 1,0,len(html),1,4096,0,0)
    records = [palm+header+b'Test',html,png('red'),png('blue')]
    pdb = bytearray(78); pdb[:4]=b'Test'; pdb[60:68]=b'BOOKMOBI'; struct.pack_into('>H',pdb,76,len(records))
    offset = 78+8*len(records)+2
    table = b''
    for i, record in enumerate(records):
        table += struct.pack('>II', offset, i); offset += len(record)
    mobi.write_bytes(pdb+table+b'\0\0'+b''.join(records))
    return pdf, epub, mobi

class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory(); self.root=Path(self.temp.name)
        self.paths = fixtures(self.root)
    def tearDown(self): self.temp.cleanup()

    def test_all_formats_read_only_no_extraction(self):
        before = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.paths}
        for p in self.paths:
            b = Book(p)
            self.assertGreater(len(b), 0)
            for i in range(len(b)): self.assertFalse(b.render(i).isNull())
            b.close()
        self.assertEqual(before, {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.paths})
        self.assertEqual(set(before), {p.name for p in self.root.iterdir()})

    def test_epub_spine_and_pixels(self):
        b=Book(self.paths[1]); self.assertEqual(len(b),5)
        self.assertEqual(b.render(0).pixelColor(20,20).name(),'#ff0000')
        self.assertEqual(b.render(2).pixelColor(20,20).name(),'#0000ff'); b.close()

    def test_mobi_actual_images(self):
        b=Book(self.paths[2]); self.assertEqual(len(b),2)
        self.assertEqual(b.render(0).pixelColor(20,20).name(),'#ff0000')
        self.assertEqual(b.render(1).pixelColor(20,20).name(),'#0000ff'); b.close()

    def test_path_only_duplicate_and_progress(self):
        lib=Library(self.root/'library.json'); lib.add([self.paths[0],self.paths[0]])
        self.assertEqual(len(lib.data['books']),1)
        lib.data['books'][0]['page']=3; lib.save()
        self.assertEqual(Library(lib.path).data['books'][0]['page'],3)
        self.assertLess(lib.path.stat().st_size,1000)

    def test_gui_rtl_spread_navigation_restore(self):
        lib=Library(self.root/'library.json'); lib.add([self.paths[1]])
        w=Window(lib,runtime_root=self.root); w.show(); APP.processEvents(); w.open_entry(lib.data['books'][0]); APP.processEvents()
        self.assertEqual(len(w.canvas.pages),1)
        w.turn(1); APP.processEvents(); self.assertEqual(w.page,1)
        self.assertEqual(len(w.canvas.pages),2)
        shot=w.canvas.grab().toImage(); width,height,scale=w.canvas.dimensions()
        start=max(16,(w.canvas.width()-width*scale)/2)
        self.assertEqual(shot.pixelColor(int(start+100*scale),shot.height()//2).name(),'#0000ff')
        self.assertEqual(shot.pixelColor(int(start+300*scale),shot.height()//2).name(),'#008000')
        w.turn(1); self.assertEqual(w.page,3); w.turn(-1); self.assertEqual(w.page,1)
        w.close()
        w=Window(Library(lib.path),runtime_root=self.root); w.open_entry(w.library.data['books'][0]); self.assertEqual(w.page,1); w.close()

    def test_spread_boundary(self):
        self.assertEqual(spread(0,5),[0]); self.assertEqual(spread(1,5),[1,2]); self.assertEqual(spread(4,5),[4])

    def window(self):
        lib=Library(self.root/'library.json'); lib.add([self.paths[1]])
        w=Window(lib,runtime_root=self.root); w.show(); APP.processEvents()
        w.open_entry(lib.data['books'][0]); APP.processEvents()
        return w

    def test_gap_geometry_pixels_and_saved_settings(self):
        w=self.window(); w.motion.setCurrentIndex(1); w.turn(1)
        w.gap.setValue(64); APP.processEvents()
        a,b=w.canvas.page_rects()
        self.assertAlmostEqual(b.left()-a.right(),64)
        shot=w.canvas.grab().toImage()
        self.assertEqual(shot.pixelColor(int((a.right()+b.left())/2),int(a.center().y())).name(),'#101416')
        w.gap.setValue(0); a,b=w.canvas.page_rects(); self.assertAlmostEqual(a.right(),b.left())
        w.close()
        saved=Library(self.root/'library.json')
        self.assertEqual(saved.data['settings']['gap'],0)
        self.assertEqual(saved.data['books'][0]['page'],1)

    def test_immersive_exit_and_layout_restore(self):
        w=self.window(); w.settings_btn.click(); APP.processEvents()
        w.set_immersive(True); QTest.qWait(1000 if APP.platformName()=="cocoa" else 50)
        w.activateWindow(); w.canvas.setFocus(); APP.processEvents()
        self.assertTrue(w.isFullScreen())
        self.assertTrue(all(x.isHidden() for x in [w.header,w.toolbar,w.appearance,w.navigation,w.statusBar()]))
        QTest.keyClick(w.canvas,Qt.Key.Key_Escape); APP.processEvents()
        self.assertFalse(w.immersive); self.assertFalse(w.isFullScreen())
        self.assertFalse(w.header.isHidden()); self.assertFalse(w.appearance.isHidden())
        w.set_immersive(True); w.canvas.exit_immersive.emit(); self.assertFalse(w.immersive)
        w.close()

    def test_center_click_controls_without_leaving_immersive(self):
        w=self.window()
        def click(fraction):
            viewport=w.reading_viewport
            point=w.canvas.mapFrom(viewport,QPoint(round(viewport.width()*fraction),viewport.height()//2))
            QTest.mouseClick(w.canvas,Qt.MouseButton.LeftButton,pos=point)
        page=w.page
        for x in (.36,.5,.64): click(x)
        self.assertEqual(w.page,page); self.assertFalse(w.immersive_controls)
        w.settings_btn.setChecked(True)
        w.set_immersive(True); QTest.qWait(1200 if APP.platformName()=="cocoa" else 120)
        viewport_size=w.reading_viewport.size()
        canvas_size=w.canvas.size()
        page_rects=w.canvas.page_rects()
        click(.5); QTest.qWait(100)
        self.assertTrue(w.immersive); self.assertTrue(w.isFullScreen()); self.assertTrue(w.immersive_controls)
        self.assertTrue(all(widget.isVisible() for widget in [w.header,w.toolbar,w.appearance,w.navigation]))
        self.assertTrue(w.statusBar().isHidden())
        self.assertEqual(w.reading_viewport.size(),viewport_size)
        self.assertEqual(w.canvas.size(),canvas_size)
        self.assertEqual(w.canvas.page_rects(),page_rects)
        w.settings_btn.click(); QTest.qWait(50)
        self.assertEqual(w.reading_viewport.size(),viewport_size)
        w.settings_btn.click(); QTest.qWait(50)
        self.assertEqual(w.canvas.page_rects(),page_rects)
        self.assertFalse(w.cursor_timer.isActive()); self.assertEqual(w.page,page)
        click(.5); QTest.qWait(100)
        self.assertTrue(w.immersive); self.assertTrue(w.isFullScreen()); self.assertFalse(w.immersive_controls)
        self.assertEqual(w.reading_viewport.size(),viewport_size)
        self.assertEqual(w.canvas.page_rects(),page_rects)
        self.assertTrue(all(widget.isHidden() for widget in [w.header,w.toolbar,w.appearance,w.navigation,w.statusBar()]))
        click(.5); w.exit_immersive(); APP.processEvents()
        self.assertFalse(w.immersive_controls); self.assertTrue(w.header.isVisible())
        w.set_immersive(True); APP.processEvents(); self.assertTrue(w.header.isHidden())
        w.exit_immersive(); w.go(1); click(.2); self.assertEqual(w.page,3)
        click(.8); self.assertEqual(w.page,1)
        w.close()

    def test_center_click_uses_visible_viewport_when_zoomed_and_scrolled(self):
        w=self.window(); w.zoom.setCurrentIndex(4); APP.processEvents()
        w.scroll.horizontalScrollBar().setValue(w.scroll.horizontalScrollBar().maximum())
        viewport=w.reading_viewport
        center=w.canvas.mapFrom(viewport,QPoint(viewport.width()//2,viewport.height()//2))
        page=w.page; QTest.mouseClick(w.canvas,Qt.MouseButton.LeftButton,pos=center)
        self.assertEqual(w.page,page)
        w.set_immersive(True); QTest.qWait(1200 if APP.platformName()=="cocoa" else 120)
        w.scroll.horizontalScrollBar().setValue(w.scroll.horizontalScrollBar().maximum())
        w.scroll.verticalScrollBar().setValue(w.scroll.verticalScrollBar().maximum()//2)
        QTest.qWait(300 if APP.platformName()=="cocoa" else 10)
        before=(viewport.size(),w.canvas.size(),w.canvas.page_rects(),w.scroll.horizontalScrollBar().value(),w.scroll.verticalScrollBar().value())
        for _ in range(2):
            center=w.canvas.mapFrom(viewport,QPoint(viewport.width()//2,viewport.height()//2))
            QTest.mouseClick(w.canvas,Qt.MouseButton.LeftButton,pos=center); QTest.qWait(60)
            after=(viewport.size(),w.canvas.size(),w.canvas.page_rects(),w.scroll.horizontalScrollBar().value(),w.scroll.verticalScrollBar().value())
            self.assertEqual(before,after)
        w.close()

    def test_animation_frames_rapid_navigation_and_release(self):
        w=self.window(); w.go(1); APP.processEvents()
        w.turn(1); overlay=w.page_turn
        self.assertEqual(overlay.side,-1); self.assertIsNotNone(overlay.old)
        overlay.animation.pause()
        frames=[]
        for t in (.0,.25,.5,.75,.999):
            overlay.advance(t)
            image=overlay.grab().toImage()
            frames.append(hashlib.sha256(image.constBits()).hexdigest())
        self.assertEqual(len(set(frames)),5)
        w.turn(-1); self.assertEqual(w.page,1); self.assertEqual(overlay.side,1)
        QTest.qWait(750 if APP.platformName()=="cocoa" else 500)
        self.assertIsNone(overlay.old); self.assertIsNone(overlay.new); self.assertTrue(overlay.isHidden())
        w.direction.setCurrentIndex(1); w.turn(1); self.assertEqual(overlay.side,1)
        w.motion.setCurrentIndex(1); w.turn(-1); self.assertIsNone(overlay.old)
        w.close()

    def test_immersive_animation_survives_deferred_viewport_resize(self):
        w=self.window()
        for cycle in range(2):
            w.set_immersive(True); QTest.qWait(1200 if APP.platformName()=="cocoa" else 100)
            for effect in ('book','slide','cover','fade'):
                w.motion.setCurrentIndex(w.motion.findData(effect))
                w.go(0); APP.processEvents(); w.turn(1)
                overlay=w.page_turn
                overlay.animation.pause(); overlay.advance(.25)
                before=overlay.grab().toImage()
                viewport=w.reading_viewport
                viewport.resize(viewport.width()-17,viewport.height()-11)
                APP.processEvents()
                self.assertIsNotNone(overlay.old,(cycle,effect))
                self.assertTrue(overlay.isVisible())
                self.assertEqual(overlay.geometry(),viewport.rect())
                self.assertEqual(overlay.progress,.25)
                overlay.advance(.65)
                after=overlay.grab().toImage()
                self.assertNotEqual(hashlib.sha256(before.constBits()).digest(),hashlib.sha256(after.constBits()).digest())
                overlay.animation.resume(); QTest.qWait(750 if APP.platformName()=="cocoa" else 500)
                self.assertIsNone(overlay.old)
            w.exit_immersive(); QTest.qWait(100)
        w.close()

if __name__=='__main__': unittest.main()
