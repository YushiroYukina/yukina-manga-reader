import hashlib
import os
import struct
import subprocess
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import QBuffer, QIODevice
from reader import Book, Library
from image_books import decoder

def png(color):
    image=QImage(32,48,QImage.Format.Format_RGB32);image.fill(QColor(color))
    buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,'PNG')
    return bytes(buffer.data())

def rar_stored(path, members):
    """Generated RAR4 stored fixture; no third-party copyrighted book content."""
    def header(body):return struct.pack('<H',zlib.crc32(body)&65535)+body
    output=b'Rar!\x1a\x07\x00'+header(struct.pack('<BHHHI',0x73,0,13,0,0))
    for name,data in members:
        raw=name.encode('ascii')
        body=struct.pack('<BHHIIBIIBBHI',0x74,0x8000,32+len(raw),len(data),len(data),2,zlib.crc32(data),0,20,0x30,len(raw),0x20)+raw
        output+=header(body)+data
    output+=header(struct.pack('<BHH',0x7b,0,7));path.write_bytes(output)

def fixtures(root):
    members=[('page10.png',png('blue')),('page2.png',png('red')),('__MACOSX/ignored.png',png('black'))]
    folder=root/'散图';folder.mkdir()
    for name,data in members[:2]:(folder/name).write_bytes(data)
    with zipfile.ZipFile(root/'scan.cbz','w',zipfile.ZIP_DEFLATED) as z:
        for name,data in members:z.writestr(name,data)
    rar_stored(root/'scan.rar',members)
    subprocess.run([decoder(),'a','-t7z',str(root/'scan.7z'),str(folder/'*')],stdout=subprocess.DEVNULL,check=True)
    return folder

class ScanBooksTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.folder=fixtures(self.root)
    def tearDown(self):self.temp.cleanup()
    def test_all_containers_order_render_and_readonly(self):
        before={p:hashlib.sha256(p.read_bytes()).digest() for p in self.root.rglob('*') if p.is_file()}
        for path in [self.folder,self.root/'scan.cbz',self.root/'scan.rar',self.root/'scan.7z']:
            with self.subTest(path=path):
                book=Book(path)
                try:
                    self.assertEqual(len(book),2)
                    self.assertGreater(book.render(0).pixelColor(10,10).red(),240)
                    self.assertGreater(book.render(1).pixelColor(10,10).blue(),240)
                finally:book.close()
        self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).digest() for p in self.root.rglob('*') if p.is_file()})
    def test_image_folder_import_and_single_image(self):
        lib=Library(self.root/'library.json');entry=lib.import_folder(self.folder)[0]
        self.assertEqual(entry['kind'],'images');self.assertEqual(len(lib.data['books']),1)
        self.assertEqual(lib.add([self.folder]),[])
        book=Book(self.folder/'page2.png');self.assertEqual(len(book),1);book.close()
    def test_nested_images_are_volumes_not_individual_pages(self):
        lib=Library(self.root/'library.json');entry=lib.import_folder(self.root)[0]
        self.assertEqual(len(entry['volumes']),4)
        self.assertEqual(sum(Path(v['path']).is_dir() for v in entry['volumes']),1)
    def test_unicode_and_dot_prefix(self):
        path=self.root/'中文.zip'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('./中文/页10.png',png('blue'));z.writestr('./中文/页2.png',png('red'))
        book=Book(path)
        try:
            self.assertEqual(len(book),2);self.assertGreater(book.render(0).pixelColor(10,10).red(),240)
        finally:book.close()

    def test_mixed_archive_prefixes_keep_natural_order_and_original_names(self):
        members=[('./页10.png','blue'),('页2.png','red')]
        for suffix in ('.zip','.cbz'):
            with self.subTest(suffix=suffix):
                path=self.root/('mixed'+suffix)
                with zipfile.ZipFile(path,'w') as archive:
                    for name,color in members: archive.writestr(name,png(color))
                before=hashlib.sha256(path.read_bytes()).digest()
                book=Book(path)
                try:
                    self.assertEqual([p.filename for p in book.image_book.pages],['页2.png','./页10.png'])
                    self.assertEqual(book.render(0).pixelColor(10,10).name(),'#ff0000')
                    self.assertEqual(book.render(1).pixelColor(10,10).name(),'#0000ff')
                finally: book.close()
                self.assertEqual(before,hashlib.sha256(path.read_bytes()).digest())

    def test_mixed_prefixes_rar_and_7z_read_original_members(self):
        members=[('page2.png',png('red')),('./page10.png',png('blue'))]
        for suffix in ('.rar','.cbr','.7z','.cb7'):
            with self.subTest(suffix=suffix):
                path=self.root/('mixed'+suffix)
                if suffix in ('.rar','.cbr'): rar_stored(path,members)
                else:
                    for name,data in members:
                        subprocess.run([decoder(),'a','-t7z',str(path),'-si'+name],input=data,stdout=subprocess.DEVNULL,check=True)
                before=hashlib.sha256(path.read_bytes()).digest()
                book=Book(path)
                try:
                    self.assertEqual(book.render(0).pixelColor(10,10).name(),'#ff0000')
                    self.assertEqual(book.render(1).pixelColor(10,10).name(),'#0000ff')
                finally: book.close()
                self.assertEqual(before,hashlib.sha256(path.read_bytes()).digest())

    def test_nested_mixed_prefixes_and_separators(self):
        path=self.root/'mixed-nested.zip'
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('././中文//页10.png',png('blue'))
            archive.writestr('中文/页2.png',png('red'))
            archive.writestr('./.hidden/页1.png',png('black'))
            archive.writestr('./__MACOSX/页1.png',png('black'))
        book=Book(path)
        try:
            self.assertEqual(len(book),2)
            self.assertEqual(book.render(0).pixelColor(10,10).name(),'#ff0000')
        finally: book.close()

    def test_repeated_image_folder_batch_counts_and_saved_progress(self):
        for grouped in (True,False):
            with self.subTest(grouped=grouped):
                library_path=self.root/('library-'+str(grouped)+'.json')
                lib=Library(library_path)
                first=lib.import_batch([self.folder],grouped=grouped)
                self.assertEqual(first,{'added':1,'updated':0,'skipped':0,'errors':[]})
                entry=lib.data['books'][0];entry.update(page=1,reading_status='在读',reading_seconds=12)
                lib.save();lib=Library(library_path)
                second=lib.import_batch([self.folder],grouped=grouped)
                self.assertEqual(second,{'added':0,'updated':0,'skipped':1,'errors':[]})
                loaded=Library(library_path);self.assertEqual(len(loaded.data['books']),1)
                self.assertEqual(loaded.data['books'][0]['page'],1)
                self.assertEqual(loaded.data['books'][0]['reading_status'],'在读')
                self.assertEqual(loaded.data['books'][0]['reading_seconds'],12)
                repeated=lib.import_batch([self.folder,self.folder],grouped=grouped)
                self.assertEqual(repeated,{'added':0,'updated':0,'skipped':2,'errors':[]})

    def test_existing_collection_still_counts_as_updated(self):
        lib=Library(self.root/'collection.json')
        first=lib.import_batch([self.root])
        self.assertEqual(first['added'],1)
        second=lib.import_batch([self.root])
        self.assertEqual(second,{'added':0,'updated':1,'skipped':0,'errors':[]})

    def test_empty_archive_and_corrupt_image(self):
        path=self.root/'empty.zip'
        with zipfile.ZipFile(path,'w') as z:z.writestr('note.txt','hello')
        with self.assertRaises(ValueError):Book(path)
        path=self.root/'broken.png';path.write_bytes(b'bad')
        book=Book(path)
        try:
            with self.assertRaises(ValueError):book.render(0)
        finally:book.close()

if __name__=='__main__':unittest.main()
