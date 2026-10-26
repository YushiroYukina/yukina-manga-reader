package cn.migi.reader;
import android.app.*;
import android.os.*;
import android.net.Uri;
import android.graphics.Bitmap;
import org.json.*;
import me.zhanghai.android.libarchive.Archive;
import me.zhanghai.android.libarchive.ArchiveEntry;

/** Uses an existing, user-selected QA library URI; never writes to a book. */
public final class RealStorageChecks extends Instrumentation {
    public void onCreate(Bundle args){super.onCreate(args);start();}
    public void onStart(){Bundle result=new Bundle();try{
        Store store=new Store(getTargetContext());JSONObject source=null;
        for(int i=0;i<store.books().length();i++){
            JSONObject book=store.books().getJSONObject(i);
            if(book.optString("uri").contains("externalstorage")&&ScanBooks.archive(book.optString("title"))){source=book;break;}
        }
        if(source==null)throw new AssertionError("Select a real archive in the QA library first");
        StringBuilder report=new StringBuilder();
        try(ScanBooks.Handle h=new ScanBooks.Handle(getTargetContext().getContentResolver(),Uri.parse(source.getString("uri")))){
            for(int i=0;i<12;i++){
                long entry=Archive.readNextHeader(h.archive);if(entry==0)break;
                report.append("ENTRY ").append(ArchiveEntry.pathnameUtf8(entry)).append(" type=").append(Integer.toOctalString(ArchiveEntry.filetype(entry))).append(" size=").append(ArchiveEntry.size(entry)).append('\n');
            }
        }
        result.putString("stream",report.toString());sendStatus(0,result);
        try(Books.Engine engine=Books.open(getTargetContext().getContentResolver(),source)){
            if(engine.count()<2)throw new AssertionError("Not a multi-page book");
            for(int index:new int[]{0,1,engine.count()/2,engine.count()-1}){
                Bitmap page=engine.render(index,1000);
                if(page==null||page.getWidth()<16)throw new AssertionError("Page did not decode");page.recycle();
            }
            result.putString("stream","REAL_STORAGE_PASSED pages="+engine.count()+"; first, next, middle and last rendered\n");
        }
        finish(Activity.RESULT_OK,result);
    }catch(Throwable e){result.putString("stream",android.util.Log.getStackTraceString(e));finish(Activity.RESULT_CANCELED,result);}}
}
