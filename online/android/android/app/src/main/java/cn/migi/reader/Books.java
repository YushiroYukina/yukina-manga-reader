package cn.migi.reader;

import android.content.*;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.graphics.*;
import android.graphics.pdf.PdfRenderer;
import java.io.*;
import java.nio.*;
import java.nio.channels.FileChannel;
import java.util.*;
import java.util.regex.*;
import java.util.zip.*;

/** Read-only page decoding. No temporary book copy and no page disk cache. */
public final class Books {
    public interface Engine extends Closeable { int count(); Bitmap render(int page,int width) throws Exception; }
    public static Engine open(ContentResolver resolver,org.json.JSONObject source) throws Exception {
        if(source.has("online")){if(Online.instance==null)throw new IOException("在线书源服务尚未初始化");return Online.instance.new Engine(source);}
        if("images".equals(source.optString("kind")))return new ScanBooks.Images(resolver,Uri.parse(source.getString("uri")),true);
        return open(resolver,Uri.parse(source.getString("uri")),source.getString("title"));
    }
    public static Engine open(ContentResolver resolver,Uri uri,String title) throws Exception {
        String name=title.toLowerCase(Locale.ROOT);
        if(name.endsWith(".pdf"))return new Pdf(resolver,uri);
        if(name.endsWith(".epub"))return new Epub(resolver,uri);
        if(name.endsWith(".mobi"))return new Mobi(resolver,uri);
        if(ScanBooks.archive(name))return new ScanBooks.Packed(resolver,uri);
        if(ScanBooks.image(name))return new ScanBooks.Images(resolver,uri,false);
        throw new IOException("请选择图书、扫图压缩包或图片");
    }
    static Bitmap image(byte[] bytes,int width) throws IOException {
        BitmapFactory.Options options=new BitmapFactory.Options(); options.inJustDecodeBounds=true;
        BitmapFactory.decodeByteArray(bytes,0,bytes.length,options);
        if(options.outWidth<=0||options.outHeight<=0)throw new IOException("图片无法解码");
        int sample=1;
        while(options.outWidth/sample>Math.max(512,width)*2||options.outHeight/sample>4096)sample*=2;
        options.inJustDecodeBounds=false; options.inSampleSize=sample;
        options.inPreferredConfig=Bitmap.Config.RGB_565;
        Bitmap bitmap=BitmapFactory.decodeByteArray(bytes,0,bytes.length,options);
        if(bitmap==null)throw new IOException("图片解码失败");
        // Decode off the UI thread, then keep only screen-sized textures in RAM.
        // Oversized scans otherwise upload and transform several times more pixels every frame.
        float scale=Math.min(1,Math.min(Math.max(512,Math.min(width,1800))/(float)bitmap.getWidth(),3200f/bitmap.getHeight()));
        if(scale<1){Bitmap fitted=Bitmap.createScaledBitmap(bitmap,Math.max(1,Math.round(bitmap.getWidth()*scale)),Math.max(1,Math.round(bitmap.getHeight()*scale)),true);if(fitted!=bitmap)bitmap.recycle();bitmap=fitted;}
        return bitmap;
    }
    static final class Pdf implements Engine {
        final PdfRenderer renderer;
        Pdf(ContentResolver resolver,Uri uri) throws Exception {
            ParcelFileDescriptor fd=resolver.openFileDescriptor(uri,"r");
            if(fd==null)throw new IOException("文件授权不可用，请重新定位图书");
            try{renderer=new PdfRenderer(fd);}catch(Exception e){fd.close();throw new IOException("PDF 必须来自可寻址的本地文件；请在系统选择器选择内部存储或 TF 卡文件",e);}
        }
        public int count(){return renderer.getPageCount();}
        public Bitmap render(int index,int width) throws Exception {
            try(PdfRenderer.Page page=renderer.openPage(index)) {
                float scale=Math.min(Math.min(Math.max(512,width),1800)/(float)page.getWidth(),2600f/page.getHeight());
                Bitmap bitmap=Bitmap.createBitmap(Math.max(1,(int)(page.getWidth()*scale)),Math.max(1,(int)(page.getHeight()*scale)),Bitmap.Config.ARGB_8888);
                bitmap.eraseColor(Color.WHITE); page.render(bitmap,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);return bitmap;
            }
        }
        public void close(){renderer.close();}
    }
    static class Source implements Closeable {
        final FileInputStream input; final FileChannel channel;
        Source(ContentResolver resolver,Uri uri) throws Exception {
            ParcelFileDescriptor fd=resolver.openFileDescriptor(uri,"r");
            if(fd==null)throw new IOException("文件授权不可用");
            input=new ParcelFileDescriptor.AutoCloseInputStream(fd); channel=input.getChannel();
            try{channel.position(0);channel.size();}catch(Exception e){input.close();throw new IOException("该文件来源不支持直接定位读取，请选内部存储或 TF 卡中的本地图书",e);}
        }
        byte[] read(long position,int count) throws IOException {
            if(position<0||count<0||position+count>channel.size())throw new IOException("图书记录越界或文件损坏");
            ByteBuffer buffer=ByteBuffer.allocate(count);
            while(buffer.hasRemaining()){int n=channel.read(buffer,position+buffer.position());if(n<=0)throw new EOFException();}
            return buffer.array();
        }
        public void close() throws IOException {input.close();}
    }
    static class Entry {long offset,size,compressed;int method,flags;}
    static final class Epub implements Engine,Core.Archive {
        final Source source; final Map<String,Entry> entries=new HashMap<>(); final List<String> pages;
        Epub(ContentResolver resolver,Uri uri) throws Exception {
            source=new Source(resolver,uri);
            try {
                long size=source.channel.size(); byte[] tail=source.read(Math.max(0,size-65557),(int)Math.min(size,65557));
                int end=-1;
                for(int i=tail.length-22;i>=0;i--)if(le32(tail,i)==0x06054b50L&&i+22+le16(tail,i+20)==tail.length){end=i;break;}
                if(end<0)throw new IOException("EPUB ZIP 目录损坏");
                int count=le16(tail,end+10); long position=le32(tail,end+16);
                if(count==65535||position==0xffffffffL)throw new IOException("基础版暂不支持 ZIP64 EPUB");
                for(int i=0;i<count;i++) {
                    byte[] header=source.read(position,46);
                    if(le32(header,0)!=0x02014b50L)throw new IOException("EPUB ZIP 目录损坏");
                    int nameLength=le16(header,28),extra=le16(header,30),comment=le16(header,32);
                    String name=new String(source.read(position+46,nameLength),"UTF-8");
                    Entry entry=new Entry();entry.flags=le16(header,8);entry.method=le16(header,10);
                    entry.compressed=le32(header,20);entry.size=le32(header,24);entry.offset=le32(header,42);
                    entries.put(name,entry); position+=46+nameLength+extra+comment;
                }
                pages=Core.epubPages(this);
            }catch(Exception e){source.close();throw e;}
        }
        public byte[] read(String name,int maximum) throws Exception {
            Entry e=entries.get(name);if(e==null)throw new IOException("EPUB 引用不存在："+name);
            if((e.flags&1)!=0)throw new IOException("EPUB 内容已加密");
            if(e.size>maximum||e.compressed>maximum)throw new IOException("EPUB 单项内容超出内存保护限制");
            byte[] local=source.read(e.offset,30);
            if(le32(local,0)!=0x04034b50L)throw new IOException("EPUB 文件头损坏");
            byte[] data=source.read(e.offset+30+le16(local,26)+le16(local,28),(int)e.compressed);
            if(e.method==0)return data;
            if(e.method!=8)throw new IOException("EPUB 压缩方法暂不支持");
            Inflater inflater=new Inflater(true);
            try(InflaterInputStream in=new InflaterInputStream(new ByteArrayInputStream(data),inflater)) {
                return Core.readBounded(in,maximum);
            }finally{inflater.end();}
        }
        public int count(){return pages.size();}
        public Bitmap render(int page,int width) throws Exception {return image(read(pages.get(page),32*1024*1024),width);}
        public void close() throws IOException {source.close();}
    }
    static final class Mobi implements Engine {
        final Source source; final long[] offsets; final List<Integer> pages=new ArrayList<>();
        Mobi(ContentResolver resolver,Uri uri) throws Exception {
            source=new Source(resolver,uri);
            try {
                byte[] header=source.read(0,78);
                if(!new String(header,60,8,"US-ASCII").equals("BOOKMOBI"))throw new IOException("MOBI 数据库标记无效");
                int count=be16(header,76); if(count<2)throw new IOException("MOBI 没有图书内容");
                byte[] table=source.read(78,count*8);offsets=new long[count+1];
                for(int i=0;i<count;i++)offsets[i]=be32(table,i*8);offsets[count]=source.channel.size();
                byte[] meta=record(0,2*1024*1024);
                if(meta.length<132||!new String(meta,16,4,"US-ASCII").equals("MOBI"))throw new IOException("暂不支持此 MOBI 版本");
                if(be16(meta,12)!=0)throw new IOException("MOBI 已加密；仅支持无 DRM 图书");
                int compression=be16(meta,0),textCount=be16(meta,8),version=(int)be32(meta,36),first=(int)be32(meta,108);
                if(version>6||compression!=1&&compression!=2)throw new IOException("基础版仅支持 MOBI6 图片漫画，暂不支持 KF8／HuffDic");
                int flags=meta.length>=244 && be32(meta,20)>=228?be16(meta,242):0;
                ByteArrayOutputStream text=new ByteArrayOutputStream();
                for(int i=1;i<=textCount&&i<count;i++) {
                    byte[] data=record(i,2*1024*1024);
                    for(int bit=15;bit>0;bit--)if((flags&(1<<bit))!=0){
                        int value=0,shift=0;
                        for(int j=data.length-1;j>=Math.max(0,data.length-4);j--){int b=data[j]&255;value|=(b&127)<<shift;shift+=7;if((b&128)!=0)break;}
                        if(value<1||value>data.length)throw new IOException("MOBI 尾部数据损坏");data=Arrays.copyOf(data,data.length-value);
                    }
                    if((flags&1)!=0&&data.length>0){int trim=(data[data.length-1]&3)+1;if(trim>data.length)throw new IOException("MOBI 尾部数据损坏");data=Arrays.copyOf(data,data.length-trim);}
                    if(compression==2)data=Core.palmDoc(data);
                    if(text.size()+data.length>8*1024*1024)throw new IOException("MOBI 文本目录超出基础版限制");text.write(data);
                }
                String html=text.toString("UTF-8");
                String content=html.replaceAll("(?is)<(head|script|style)\\b[^>]*>.*?</\\1>","").replaceAll("(?s)<[^>]+>","").replace("&nbsp;","").trim();
                if(!content.isEmpty())throw new IOException("基础版 MOBI 暂不支持文字排版");
                Matcher matcher=Pattern.compile("(?is)<img\\b[^>]*\\brecindex\\s*=\\s*['\"]?(\\d+)").matcher(html);
                while(matcher.find()) {long record=(long)first+Long.parseLong(matcher.group(1))-1;if(record<0||record>=count)throw new IOException("MOBI 图片索引越界");pages.add((int)record);}
                if(pages.isEmpty())throw new IOException("MOBI 中未找到漫画图片");
            }catch(Exception e){source.close();throw e;}
        }
        byte[] record(int i,int maximum) throws IOException {long length=offsets[i+1]-offsets[i];if(length<0||length>maximum)throw new IOException("MOBI 单项内容超出限制");return source.read(offsets[i],(int)length);}
        public int count(){return pages.size();}
        public Bitmap render(int page,int width) throws Exception{return image(record(pages.get(page),32*1024*1024),width);}
        public void close() throws IOException{source.close();}
    }
    static int le16(byte[] b,int p){return (b[p]&255)|((b[p+1]&255)<<8);}
    static long le32(byte[] b,int p){return (long)le16(b,p)|((long)le16(b,p+2)<<16);}
    static int be16(byte[] b,int p){return ((b[p]&255)<<8)|(b[p+1]&255);}
    static long be32(byte[] b,int p){return ((long)be16(b,p)<<16)|be16(b,p+2);}
}
