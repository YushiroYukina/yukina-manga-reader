package cn.migi.reader;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.io.*;
public final class CoreTests {
    static int passed=0;
    static void check(boolean value,String name){if(!value)throw new AssertionError(name);passed++;}
    static void reject(Core.Archive archive)throws Exception{try{Core.epubPages(archive);throw new AssertionError("Invalid EPUB accepted");}catch(IOException expected){passed++;}}
    public static void main(String[] args)throws Exception {
        check(Arrays.equals(Core.spread(0,5,true,true),new int[]{0}),"cover alone");
        check(Arrays.equals(Core.spread(1,5,true,true),new int[]{1,2}),"landscape pair");
        check(Arrays.equals(Core.spread(3,5,true,true),new int[]{3,4}),"last spread");
        check(Arrays.equals(Core.spread(1,5,false,true),new int[]{1}),"portrait single");
        check(Arrays.equals(Core.spread(4,5,true,true),new int[]{4}),"last single");
        check(Core.region(35,100)==0&&Core.region(65,100)==0,"center boundaries");
        check(Core.region(34,100)==-1&&Core.region(66,100)==1,"side regions");
        check(Core.reading(true,true,true,false,true),"visible reader counts without focus");
        check(!Core.reading(false,true,true,false,true),"background stops");
        check(!Core.reading(true,false,true,false,true),"screen off stops");
        check(!Core.reading(true,true,true,true,true),"manual pause");
        check(!Core.reading(true,true,false,false,true),"library stops");
        check(Core.duration(3661).equals("01:01:01"),"duration");
        check(Core.naturalCompare("卷2.epub","卷10.epub")<0,"natural ordering");
        check(Core.resolve("OPS/book.opf","img%20a.png").equals("OPS/img a.png"),"encoded path");
        check(Core.resolve("OPS/page/p.xhtml","../img/a.png").equals("OPS/img/a.png"),"relative path");
        check(Arrays.equals(Core.palmDoc(new byte[]{65,66,67,(byte)0x80,0x18}),"ABCABC".getBytes("US-ASCII")),"PalmDOC backreference");
        Map<String,String> archive=new HashMap<>();archive.put("META-INF/container.xml","<container><rootfile full-path='OPS/book.opf'/></container>");
        archive.put("OPS/book.opf","<package><manifest><item id='b' href='b.xhtml' media-type='application/xhtml+xml'/><item id='a' href='a.png' media-type='image/png'/></manifest><spine><itemref idref='b'/><itemref idref='a'/></spine></package>");
        archive.put("OPS/b.xhtml","<html><body><img src='img/02.png'/><img src='../01.png'/></body></html>");
        Core.Archive source=(name,max)->{String s=archive.get(name);if(s==null)throw new IOException(name);return s.getBytes(StandardCharsets.UTF_8);};
        check(Core.epubPages(source).equals(Arrays.asList("OPS/img/02.png","01.png","OPS/a.png")),"EPUB spine order");
        archive.put("OPS/b.xhtml","<html><body>真实正文<img src='img/02.png'/></body></html>");reject(source);
        check(Core.xml("<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.1//EN' 'http://invalid.example/xhtml.dtd'><html><body><img src='a.png'/></body></html>".getBytes("UTF-8")).getDocumentElement().getNodeName().equals("html"),"XHTML public doctype without external fetch");
        check(Core.xml("<!DOCTYPE html><html/>".getBytes("UTF-8")).getDocumentElement().getNodeName().equals("html"),"HTML5 doctype");
        try{Core.xml("<!DOCTYPE html [<!ENTITY x SYSTEM 'file:///private'>]><html/>".getBytes("UTF-8"));throw new AssertionError("DTD accepted");}catch(IOException expected){passed++;}
        try{Core.resolve("book.opf","../../escape.png");throw new AssertionError("Path escape accepted");}catch(IOException expected){passed++;}
        try{Core.readBounded(new ByteArrayInputStream(new byte[100]),99);throw new AssertionError("Unbounded read");}catch(IOException expected){passed++;}
        for(String name:new String[]{"a.ZIP","a.cbz","a.RAR","a.cbr","a.7z","a.cb7","a.jpg","a.jpeg","a.png","a.webp","a.bmp","a.gif"})check(Core.format(name),"new format "+name);
        check(!Core.format("archive.zip.exe"),"unsupported suffix rejected");
        check(Core.naturalCompare(Core.archivePageKey("page2.png"),Core.archivePageKey("./page10.png"))<0,"mixed archive prefixes sort naturally");
        check(Core.archivePageKey("././中文//页2.png").equals("中文/页2.png"),"archive path normalization");
        System.out.println("Core tests passed: "+passed);
    }
}
