package cn.migi.reader;

import java.io.*;
import java.util.*;
import java.util.regex.*;
import javax.xml.parsers.*;
import org.w3c.dom.*;

/** Platform-independent rules, also exercised by the host test runner. */
public final class Core {
    public static int[] spread(int page,int count,boolean landscape,boolean cover) {
        if(count<1) return new int[0];
        page=Math.max(0,Math.min(count-1,page));
        return landscape && !(cover && page==0) && page+1<count ? new int[]{page,page+1}:new int[]{page};
    }
    public static boolean reading(boolean visible,boolean screenOn,boolean reader,boolean paused,boolean loaded) {
        return visible && screenOn && reader && !paused && loaded;
    }
    public static int region(float x,float width) {
        if(width<=0) return 0;
        return x>=width*.35f && x<=width*.65f?0:x<width*.35f?-1:1;
    }
    public static String duration(double seconds) {
        long s=(long)Math.max(0,seconds);
        return String.format(Locale.ROOT,"%02d:%02d:%02d",s/3600,s/60%60,s%60);
    }
    public static boolean format(String name) {
        String s=name.toLowerCase(Locale.ROOT); return s.matches(".*\\.(pdf|epub|mobi|zip|cbz|rar|cbr|7z|cb7|jpe?g|png|webp|bmp|gif)$");
    }
    public static String archivePageKey(String name) {
        StringBuilder result=new StringBuilder();
        for(String part:name.replace('\\','/').split("/")) {
            if(part.isEmpty()||part.equals("."))continue;
            if(result.length()>0)result.append('/');result.append(part);
        }
        return result.toString();
    }
    public static int naturalCompare(String a,String b) {
        Matcher x=Pattern.compile("\\d+|\\D+").matcher(a.toLowerCase(Locale.ROOT));
        Matcher y=Pattern.compile("\\d+|\\D+").matcher(b.toLowerCase(Locale.ROOT));
        while(x.find() && y.find()) {
            String u=x.group(),v=y.group(); int c;
            if(Character.isDigit(u.charAt(0)) && Character.isDigit(v.charAt(0))) {
                String un=u.replaceFirst("^0+(?!$)",""),vn=v.replaceFirst("^0+(?!$)","");
                c=Integer.compare(un.length(),vn.length()); if(c==0)c=un.compareTo(vn);
            } else c=u.compareTo(v);
            if(c!=0)return c;
        }
        return a.length()-b.length();
    }
    public static byte[] readBounded(InputStream in,int maximum) throws IOException {
        ByteArrayOutputStream out=new ByteArrayOutputStream(); byte[] b=new byte[16384]; int n;
        while((n=in.read(b))!=-1) {
            if(out.size()+n>maximum)throw new IOException("文件内容过大，超出基础版内存保护限制");
            out.write(b,0,n);
        }
        return out.toByteArray();
    }
    public static Document xml(byte[] bytes) throws Exception {
        String probe=new String(bytes,"ISO-8859-1").replace("\u0000","").toUpperCase(Locale.ROOT);
        if(probe.contains("<!ENTITY")||java.util.regex.Pattern.compile("<!DOCTYPE[^>]*\\[",java.util.regex.Pattern.DOTALL).matcher(probe).find())throw new IOException("不支持包含自定义实体的 EPUB 元数据");
        DocumentBuilderFactory f=DocumentBuilderFactory.newInstance(); f.setNamespaceAware(true);
        DocumentBuilder builder=f.newDocumentBuilder();
        builder.setEntityResolver((publicId,systemId)->new org.xml.sax.InputSource(new StringReader("")));
        return builder.parse(new ByteArrayInputStream(bytes));
    }
    public static List<Element> elements(Node node,String local) {
        List<Element> result=new ArrayList<>();
        if(node instanceof Element) {
            Element e=(Element)node;
            if(local.equals(e.getLocalName())||local.equals(e.getNodeName()))result.add(e);
        }
        for(Node c=node.getFirstChild();c!=null;c=c.getNextSibling()) result.addAll(elements(c,local));
        return result;
    }
    public static String resolve(String base,String href) throws Exception {
        href=href.split("[?#]",2)[0];
        if(href.contains(":")||href.startsWith("/"))throw new IOException("EPUB 外部图片不可读取");
        href=java.net.URLDecoder.decode(href.replace("+","%2B"),"UTF-8");
        String full=(base.contains("/")?base.substring(0,base.lastIndexOf('/')+1):"")+href;
        Deque<String> parts=new ArrayDeque<>();
        for(String p:full.split("/")) {
            if(p.equals("..")){if(parts.isEmpty())throw new IOException("EPUB 路径越界");parts.removeLast();}
            else if(!p.equals(".")&&!p.isEmpty())parts.add(p);
        }
        return String.join("/",parts);
    }
    public interface Archive { byte[] read(String name,int max) throws Exception; }
    public static List<String> epubPages(Archive archive) throws Exception {
        Document container=xml(archive.read("META-INF/container.xml",2*1024*1024));
        List<Element> roots=elements(container,"rootfile");
        if(roots.isEmpty())throw new IOException("EPUB 缺少书目入口");
        String opf=roots.get(0).getAttribute("full-path");
        Document book=xml(archive.read(opf,2*1024*1024));
        Map<String,Element> items=new HashMap<>();
        for(Element item:elements(book,"item"))items.put(item.getAttribute("id"),item);
        List<String> result=new ArrayList<>();
        for(Element ref:elements(book,"itemref")) {
            if("no".equals(ref.getAttribute("linear")))continue;
            Element item=items.get(ref.getAttribute("idref")); if(item==null)continue;
            String name=resolve(opf,item.getAttribute("href")),type=item.getAttribute("media-type");
            if(type.startsWith("image/")){result.add(name);continue;}
            if(!type.contains("html"))continue;
            Document html=xml(archive.read(name,2*1024*1024));
            List<Element> bodies=elements(html,"body");
            if(!bodies.isEmpty()&&!bodies.get(0).getTextContent().trim().isEmpty())throw new IOException("基础版 EPUB 仅支持图片漫画，暂不支持文字排版");
            for(Element img:elements(html,"img")) {
                String src=img.getAttribute("src"); if(!src.isEmpty())result.add(resolve(name,src));
            }
            for(Element img:elements(html,"image")) {
                String src=img.getAttribute("href"); if(src.isEmpty())src=img.getAttributeNS("http://www.w3.org/1999/xlink","href");
                if(!src.isEmpty())result.add(resolve(name,src));
            }
        }
        if(result.isEmpty())throw new IOException("EPUB 中未找到可阅读的漫画图片");
        return result;
    }
    public static byte[] palmDoc(byte[] src) throws IOException {
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        for(int i=0;i<src.length;i++) {
            int b=src[i]&255;
            if(b==0||b>=9&&b<=127)out.write(b);
            else if(b<=8){if(i+b>=src.length)throw new IOException("PalmDOC 文本损坏");out.write(src,i+1,b);i+=b;}
            else if(b>=192){out.write(32);out.write(b^128);}
            else {
                if(++i>=src.length)throw new IOException("PalmDOC 引用损坏");
                int pair=((b&63)<<8)|(src[i]&255),distance=pair>>3,length=(pair&7)+3;
                if(distance==0||distance>out.size())throw new IOException("PalmDOC 引用越界");
                for(int j=0;j<length;j++){byte[] data=out.toByteArray();out.write(data[data.length-distance]);}
            }
            if(out.size()>2*1024*1024)throw new IOException("PalmDOC 解压过大");
        }
        return out.toByteArray();
    }
}
