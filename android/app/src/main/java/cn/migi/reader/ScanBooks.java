package cn.migi.reader;

import android.content.ContentResolver;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.*;
import me.zhanghai.android.libarchive.Archive;
import me.zhanghai.android.libarchive.ArchiveEntry;

/** Original SAF documents stay read-only. Only one decoded page lives in memory. */
final class ScanBooks {
    static final int LIMIT=32*1024*1024;
    static boolean image(String name){return name.toLowerCase(Locale.ROOT).matches(".*\\.(jpe?g|png|webp|bmp|gif)$");}
    static boolean archive(String name){return name.toLowerCase(Locale.ROOT).matches(".*\\.(zip|cbz|rar|cbr|7z|cb7)$");}
    static boolean page(String name){
        if(name==null||!image(name))return false;
        for(String part:name.replace('\\','/').split("/"))if((part.startsWith(".")&&!part.equals("."))||part.equals("__MACOSX"))return false;
        return true;
    }
    static final class Images implements Books.Engine {
        final ContentResolver resolver;final List<Uri> pages=new ArrayList<>();
        Images(ContentResolver r,Uri uri,boolean folder)throws Exception{
            resolver=r;
            if(!folder){pages.add(uri);return;}
            String id=uri.getPathSegments().contains("document")?DocumentsContract.getDocumentId(uri):DocumentsContract.getTreeDocumentId(uri);
            List<String[]> names=new ArrayList<>();
            try(Cursor c=r.query(DocumentsContract.buildChildDocumentsUriUsingTree(uri,id),new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE},null,null,null)){
                if(c==null)throw new IOException("图片文件夹读取授权不可用，请重新导入");
                while(c.moveToNext())if(!DocumentsContract.Document.MIME_TYPE_DIR.equals(c.getString(2))&&page(c.getString(1))){
                    if(names.size()>=20000)throw new IOException("单本书超过 20000 页，请分卷导入");
                    names.add(new String[]{c.getString(1),c.getString(0)});
                }
            }
            names.sort((a,b)->Core.naturalCompare(a[0],b[0]));
            for(String[] entry:names)pages.add(DocumentsContract.buildDocumentUriUsingTree(uri,entry[1]));
            if(pages.isEmpty())throw new IOException("文件夹内没有支持的图片");
        }
        public int count(){return pages.size();}
        public Bitmap render(int index,int width)throws Exception{
            try(InputStream input=resolver.openInputStream(pages.get(index))){
                if(input==null)throw new IOException("图片授权不可用");
                return Books.image(Core.readBounded(input,LIMIT),width);
            }
        }
        public void close(){}
    }
    static final class Member {
        final int ordinal;final String name;final long size;
        Member(int ordinal,String name,long size){this.ordinal=ordinal;this.name=name;this.size=size;}
    }
    static final class Handle implements AutoCloseable {
        final ParcelFileDescriptor fd;long archive;
        Handle(ContentResolver resolver,Uri uri)throws Exception{
            fd=resolver.openFileDescriptor(uri,"r");
            if(fd==null)throw new IOException("压缩包授权不可用");
            try{
                archive=Archive.readNew();Archive.setCharset(archive,"UTF-8".getBytes(StandardCharsets.UTF_8));Archive.readSupportFilterAll(archive);Archive.readSupportFormatAll(archive);
                Archive.readOpenFd(archive,fd.getFd(),65536);
            }catch(Exception|LinkageError e){close();throw e;}
        }
        public void close()throws IOException{
            try{if(archive!=0){long a=archive;archive=0;Archive.free(a);}}finally{fd.close();}
        }
    }
    static final class Packed implements Books.Engine {
        final ContentResolver resolver;final Uri uri;final List<Member> pages=new ArrayList<>();
        Packed(ContentResolver r,Uri source)throws Exception{
            resolver=r;uri=source;
            try(Handle h=new Handle(r,uri)){
                long entry;int ordinal=0;
                while((entry=Archive.readNextHeader(h.archive))!=0){
                    String name=ArchiveEntry.pathnameUtf8(entry);
                    if(name==null){byte[] raw=ArchiveEntry.pathname(entry);if(raw!=null)name=new String(raw,StandardCharsets.UTF_8);}
                    if(page(name)&&(ArchiveEntry.filetype(entry)&0170000)==0100000){
                        if(ArchiveEntry.isEncrypted(entry))throw new IOException("暂不支持加密压缩包，请使用无密码的完整文件");
                        long size=ArchiveEntry.size(entry);
                        if(size<0||size>LIMIT)throw new IOException("压缩包中单页超过 32 MiB 或大小未知");
                        if(pages.size()>=20000)throw new IOException("单本书超过 20000 页，请分卷导入");
                        pages.add(new Member(ordinal,name,size));
                    }
                    ordinal++;
                }
            }
            pages.sort((a,b)->Core.naturalCompare(Core.archivePageKey(a.name),Core.archivePageKey(b.name)));
            if(pages.isEmpty())throw new IOException("压缩包中没有支持的图片");
        }
        public int count(){return pages.size();}
        public Bitmap render(int index,int width)throws Exception{
            Member page=pages.get(index);
            try(Handle h=new Handle(resolver,uri)){
                for(int i=0;i<=page.ordinal;i++)if(Archive.readNextHeader(h.archive)==0)throw new EOFException("压缩包内容已变化，请重新打开");
                ByteArrayOutputStream output=new ByteArrayOutputStream((int)page.size);
                ByteBuffer buffer=ByteBuffer.allocateDirect(65536);int total=0;
                while(true){
                    buffer.clear();Archive.readData(h.archive,buffer);int n=buffer.position();
                    if(n==0)break;
                    total+=n;if(total>LIMIT)throw new IOException("单页超过 32 MiB");
                    buffer.flip();byte[] bytes=new byte[n];buffer.get(bytes);output.write(bytes);
                }
                return Books.image(output.toByteArray(),width);
            }
        }
        public void close(){}
    }
}
