package cn.migi.reader;

import android.app.*;
import android.content.*;
import android.os.*;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.util.concurrent.*;
import java.util.LinkedHashMap;
import java.util.concurrent.atomic.AtomicBoolean;

/** Foreground, resumable, user-started downloads. Does not write the reader library. */
public final class OnlineDownloadService extends Service {
    static volatile boolean running=false;
    static volatile String message="尚无下载任务";
    static final AtomicBoolean cancel=new AtomicBoolean();
    final ExecutorService worker=Executors.newSingleThreadExecutor();
    static AtomicFile queueFile(Context c){return new AtomicFile(new File(c.getFilesDir(),"online-download-queue.json"));}
    static synchronized void saveQueue(Context c,JSONArray queue) throws Exception{AtomicFile f=queueFile(c);FileOutputStream out=null;try{out=f.startWrite();out.write(queue.toString().getBytes("UTF-8"));f.finishWrite(out);}catch(Exception e){if(out!=null)f.failWrite(out);throw e;}}
    static synchronized JSONArray loadQueue(Context c) throws Exception{AtomicFile f=queueFile(c);if(!f.getBaseFile().exists())return new JSONArray();try(InputStream in=f.openRead()){return new JSONArray(new String(Core.readBounded(in,8*1024*1024),"UTF-8"));}}
    static JSONArray mergeJobs(JSONArray prior,JSONArray chosen)throws Exception{LinkedHashMap<String,JSONObject> items=new LinkedHashMap<>();for(int i=0;i<prior.length();i++)items.put(prior.getJSONObject(i).getString("uri"),prior.getJSONObject(i));for(int i=0;i<chosen.length();i++)items.put(chosen.getJSONObject(i).getString("uri"),chosen.getJSONObject(i));JSONArray out=new JSONArray();for(JSONObject item:items.values())out.put(item);return out;}
    static JSONArray scopedJobs(JSONArray queue,String scope)throws Exception{JSONArray out=new JSONArray();for(int i=0;i<queue.length();i++){JSONObject ch=queue.getJSONObject(i);if(scope.equals(Online.bookPath(ch)))out.put(ch);}return out;}
    static synchronized void enqueue(Context context,JSONArray chosen)throws Exception{saveQueue(context,mergeJobs(loadQueue(context),chosen));}
    static synchronized void completed(Context context,String uri)throws Exception{JSONArray prior=loadQueue(context),next=new JSONArray();for(int i=0;i<prior.length();i++)if(!uri.equals(prior.getJSONObject(i).optString("uri")))next.put(prior.getJSONObject(i));saveQueue(context,next);}
    public IBinder onBind(Intent intent){return null;}
    Notification notification(String text){
        Intent open=new Intent(this,MainActivity.class);PendingIntent pending=PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Intent pause=new Intent(this,OnlineDownloadService.class).setAction("pause");PendingIntent stop=PendingIntent.getService(this,1,pause,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this,"online-downloads").setSmallIcon(android.R.drawable.stat_sys_download).setContentTitle("yukina 在线版 · 章节下载").setContentText(text).setContentIntent(pending).setOnlyAlertOnce(true).setOngoing(running).addAction(new Notification.Action.Builder(null,"暂停",stop).build()).build();
    }
    void update(String text){message=text;((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(31,notification(text));}
    public void onCreate(){super.onCreate();NotificationManager manager=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);manager.createNotificationChannel(new NotificationChannel("online-downloads","在线漫画下载",NotificationManager.IMPORTANCE_LOW));}
    public int onStartCommand(Intent intent,int flags,int startId){
        if(intent!=null&&"pause".equals(intent.getAction())){cancel.set(true);return START_NOT_STICKY;}
        if(running)return START_NOT_STICKY;running=true;cancel.set(false);message="正在准备本书章节…";startForeground(31,notification(message));
        final String scope=intent==null?"":intent.getStringExtra("scope");
        worker.execute(()->{int success=0,failed=0;try{
            Store snapshot=new Store(this);Online online=new Online(this,snapshot);JSONArray queue=scope==null||scope.isEmpty()?new JSONArray():scopedJobs(loadQueue(this),scope);
            while(queue.length()>0&&!cancel.get()){
                JSONObject ch=queue.getJSONObject(0);
                try{online.download(ch,cancel,(title,page,total)->update(title+" · "+page+" / "+total+" 页"));success++;completed(this,ch.getString("uri"));}
                catch(Exception e){if(cancel.get())break;failed++;message="章节下载失败："+ch.optString("title")+" · "+e.getMessage();}
                queue.remove(0);
            }
            update(cancel.get()?"已暂停，剩余 "+queue.length()+" 个章节可继续":"下载完成 "+success+" 个章节，失败 "+failed+" 个（失败章节保留在该书待下载队列）");
        }catch(Exception e){update("下载已停止："+e.getMessage());}finally{new Handler(Looper.getMainLooper()).post(()->{running=false;stopForeground(STOP_FOREGROUND_DETACH);stopSelf(startId);});}});
        return START_NOT_STICKY;
    }
    public void onDestroy(){cancel.set(true);worker.shutdown();super.onDestroy();}
}
