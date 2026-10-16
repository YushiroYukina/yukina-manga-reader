package cn.migi.reader;
import android.provider.DocumentsProvider;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsContract.Root;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.os.*;
import java.io.*;
public final class TestDocuments extends DocumentsProvider {
    static final String[] DOCS={Document.COLUMN_DOCUMENT_ID,Document.COLUMN_DISPLAY_NAME,Document.COLUMN_MIME_TYPE,Document.COLUMN_FLAGS,Document.COLUMN_SIZE};
    public boolean onCreate(){try{directory().mkdirs();for(String name:getContext().getAssets().list("")){if(!name.matches(".*\\.(pdf|epub|mobi|zip|rar|7z|png)$"))continue;File file=new File(directory(),name);if(file.exists())continue;try(InputStream in=getContext().getAssets().open(name);OutputStream out=new FileOutputStream(file)){byte[] b=new byte[16384];int n;while((n=in.read(b))!=-1)out.write(b,0,n);}}return true;}catch(Exception e){throw new RuntimeException(e);}}
    File directory(){return new File(getContext().getFilesDir(),"fixtures");}
    public Cursor queryRoots(String[] projection){MatrixCursor c=new MatrixCursor(new String[]{Root.COLUMN_ROOT_ID,Root.COLUMN_DOCUMENT_ID,Root.COLUMN_TITLE,Root.COLUMN_FLAGS,Root.COLUMN_MIME_TYPES});c.addRow(new Object[]{"migi-qa","root","MIGI 测试图书",0,"*/*"});return c;}
    void add(MatrixCursor c,String id){if(id.equals("root")||id.equals("batch")||id.equals("collection2")||id.equals("collection10")||id.equals("images"))c.addRow(new Object[]{id,id.equals("root")?"漫画测试合辑":id,Document.MIME_TYPE_DIR,0,0});else{File f=new File(directory(),id);c.addRow(new Object[]{id,id,id.endsWith(".pdf")?"application/pdf":id.endsWith(".epub")?"application/epub+zip":"application/x-mobipocket-ebook",0,f.length()});}}
    public Cursor queryDocument(String id,String[] projection)throws FileNotFoundException{MatrixCursor c=new MatrixCursor(DOCS);add(c,id);return c;}
    public Cursor queryChildDocuments(String id,String[] projection,String sort){MatrixCursor c=new MatrixCursor(DOCS);if(id.equals("batch")){add(c,"collection10");add(c,"collection2");return c;}if(id.equals("images")){for(File f:directory().listFiles())if(f.getName().endsWith(".png"))add(c,f.getName());return c;}if(id.startsWith("collection")){for(File f:directory().listFiles())if(f.getName().endsWith(".pdf")||f.getName().endsWith(".epub")||f.getName().endsWith(".mobi"))add(c,id+"|"+f.getName());return c;}File[] files=directory().listFiles();if(id.equals("root")&&files!=null)for(File f:files)if(f.getName().endsWith(".pdf")||f.getName().endsWith(".epub")||f.getName().endsWith(".mobi"))add(c,f.getName());return c;}
    public boolean isChildDocument(String parent,String child){return parent.equals("root")&&!child.equals("root")&&(child.equals("batch")||child.equals("images")||child.startsWith("collection")||new File(directory(),child).isFile());}
    public ParcelFileDescriptor openDocument(String id,String mode,CancellationSignal signal)throws FileNotFoundException{
        if(!mode.equals("r")||id.contains("/")||id.contains("\\")||id.contains(".."))throw new FileNotFoundException("Read-only test provider");
        return ParcelFileDescriptor.open(new File(directory(),id.contains("|")?id.substring(id.indexOf("|")+1):id),ParcelFileDescriptor.MODE_READ_ONLY);
    }
}
