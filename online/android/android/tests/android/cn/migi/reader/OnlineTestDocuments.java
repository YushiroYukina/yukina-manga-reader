package cn.migi.reader;
import android.provider.DocumentsProvider;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsContract.Root;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.os.*;
import java.io.*;

/** Writable SAF fixture. This provider is included only in the separate QA test APK. */
public final class OnlineTestDocuments extends DocumentsProvider {
    File root(){return new File(getContext().getFilesDir(),"online-saf-fixture");}
    File file(String id)throws FileNotFoundException{try{File base=root().getCanonicalFile();File f=id.equals("root")?base:new File(base,id).getCanonicalFile();if(!f.equals(base)&&!f.getPath().startsWith(base.getPath()+File.separator))throw new IOException("Traversal");return f;}catch(IOException e){throw new FileNotFoundException(e.getMessage());}}
    public boolean onCreate(){root().mkdirs();return true;}
    String id(File f){return f.equals(root())?"root":f.getPath().substring(root().getPath().length()+1).replace(File.separatorChar,'/');}
    String[] columns(){return new String[]{Document.COLUMN_DOCUMENT_ID,Document.COLUMN_DISPLAY_NAME,Document.COLUMN_MIME_TYPE,Document.COLUMN_FLAGS,Document.COLUMN_SIZE};}
    void add(MatrixCursor c,File f){c.addRow(new Object[]{id(f),f.getName(),f.isDirectory()?Document.MIME_TYPE_DIR:"application/octet-stream",f.isDirectory()?Document.FLAG_DIR_SUPPORTS_CREATE:Document.FLAG_SUPPORTS_WRITE|Document.FLAG_SUPPORTS_DELETE,f.length()});}
    public Cursor queryRoots(String[] projection){MatrixCursor c=new MatrixCursor(new String[]{Root.COLUMN_ROOT_ID,Root.COLUMN_DOCUMENT_ID,Root.COLUMN_TITLE,Root.COLUMN_FLAGS,Root.COLUMN_MIME_TYPES});c.addRow(new Object[]{"online-root","root","Yukina Online QA",Root.FLAG_SUPPORTS_CREATE,"*/*"});return c;}
    public Cursor queryDocument(String id,String[] projection)throws FileNotFoundException{MatrixCursor c=new MatrixCursor(columns());add(c,file(id));return c;}
    public Cursor queryChildDocuments(String id,String[] projection,String sort)throws FileNotFoundException{MatrixCursor c=new MatrixCursor(columns());File[] children=file(id).listFiles();if(children!=null)for(File f:children)add(c,f);return c;}
    public boolean isChildDocument(String parent,String child){try{return file(child).getCanonicalPath().startsWith(file(parent).getCanonicalPath()+File.separator);}catch(Exception e){return false;}}
    public String createDocument(String parent,String mime,String name)throws FileNotFoundException{if(name.contains("/")||name.contains("\\")||name.equals(".."))throw new FileNotFoundException("Bad name");File f=new File(file(parent),name);try{if(mime.equals(Document.MIME_TYPE_DIR)){if(!f.isDirectory()&&!f.mkdir())throw new IOException("mkdir");}else if(!f.exists()&&!f.createNewFile())throw new IOException("create");return id(f);}catch(IOException e){throw new FileNotFoundException(e.getMessage());}}
    public ParcelFileDescriptor openDocument(String id,String mode,CancellationSignal signal)throws FileNotFoundException{return ParcelFileDescriptor.open(file(id),ParcelFileDescriptor.parseMode(mode));}
    public void deleteDocument(String id)throws FileNotFoundException{File f=file(id);if(f.equals(root())||!f.delete())throw new FileNotFoundException("Cannot delete");}
}
