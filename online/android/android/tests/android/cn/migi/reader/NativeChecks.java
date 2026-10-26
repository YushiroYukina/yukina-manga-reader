package cn.migi.reader;
import android.app.*;
import android.content.*;
import android.content.pm.ActivityInfo;
import android.graphics.*;
import android.net.Uri;
import android.os.*;
import android.provider.DocumentsContract;
import org.json.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import java.time.*;

public final class NativeChecks extends Instrumentation {
    int passed=0;
    void check(boolean value,String name){if(!value)throw new AssertionError(name);passed++;Bundle b=new Bundle();b.putString("stream","PASS: "+name+"\n");sendStatus(0,b);}
    void waitUntil(java.util.function.BooleanSupplier condition)throws Exception{long end=SystemClock.elapsedRealtime()+12000;while(SystemClock.elapsedRealtime()<end){final boolean[] okay={false};runOnMainSync(()->okay[0]=condition.getAsBoolean());if(okay[0])return;Thread.sleep(100);}throw new AssertionError("Timed out waiting for UI");}
    byte[] hash(Uri uri)throws Exception{try(InputStream in=getTargetContext().getContentResolver().openInputStream(uri)){return MessageDigest.getInstance("SHA-256").digest(Core.readBounded(in,8*1024*1024));}}
    long touchStart;
    void touch(ReaderSurface view,int action,float x){long now=SystemClock.uptimeMillis();if(action==android.view.MotionEvent.ACTION_DOWN)touchStart=now;android.view.MotionEvent e=android.view.MotionEvent.obtain(touchStart,now,action,x*view.getWidth(),view.getHeight()*.5f,0);view.onTouchEvent(e);e.recycle();}
    void swipe(ReaderSurface view,float from,float to){long now=SystemClock.uptimeMillis();for(int i=0;i<5;i++){int action=i==0?android.view.MotionEvent.ACTION_DOWN:i==4?android.view.MotionEvent.ACTION_UP:android.view.MotionEvent.ACTION_MOVE;android.view.MotionEvent e=android.view.MotionEvent.obtain(now,now+i*100,action,from+(to-from)*i/4,350,0);view.onTouchEvent(e);e.recycle();
        try{java.lang.reflect.Field preview=ReaderSurface.class.getDeclaredField("pages"),request=ReaderSurface.class.getDeclaredField("previewRequest");preview.setAccessible(true);request.setAccessible(true);if(view.isInteracting()&&((List<?>)preview.get(view)).isEmpty()){Bitmap page=Bitmap.createBitmap(200,300,Bitmap.Config.RGB_565);page.eraseColor(Color.BLUE);view.supplyPreview(request.getLong(view),java.util.Collections.singletonList(page));}}catch(Exception ex){throw new RuntimeException(ex);}
    }try{java.lang.reflect.Field animation=ReaderSurface.class.getDeclaredField("animation");animation.setAccessible(true);android.animation.ValueAnimator animator=(android.animation.ValueAnimator)animation.get(view);if(animator!=null)animator.end();}catch(Exception e){throw new RuntimeException(e);}}
    List<Bitmap> solid(int color){List<Bitmap> images=new ArrayList<>();for(int i=0;i<2;i++){Bitmap b=Bitmap.createBitmap(200,300,Bitmap.Config.RGB_565);b.eraseColor(color);images.add(b);}return images;}
    Bitmap captureGpu(MainActivity a)throws Exception{final Bitmap[] frame={null};final int[] code={-1};java.util.concurrent.CountDownLatch done=new java.util.concurrent.CountDownLatch(1);runOnMainSync(()->{frame[0]=Bitmap.createBitmap(a.root.getWidth(),a.root.getHeight(),Bitmap.Config.ARGB_8888);android.view.PixelCopy.request(a.getWindow(),frame[0],value->{code[0]=value;done.countDown();},a.handler);});if(!done.await(3,java.util.concurrent.TimeUnit.SECONDS)||code[0]!=android.view.PixelCopy.SUCCESS)throw new AssertionError("GPU capture failed");return frame[0];}
    boolean colorNear(int a,int b){return Math.abs(Color.red(a)-Color.red(b))<20&&Math.abs(Color.green(a)-Color.green(b))<20&&Math.abs(Color.blue(a)-Color.blue(b))<20;}
    void renderingChecks(){try{
        ReaderSurface view=new ReaderSurface(getTargetContext());view.layout(0,0,1000,700);view.gap=32;int paper=0xff101416;view.setBackgroundColor(paper);
        java.lang.reflect.Field progress=ReaderSurface.class.getDeclaredField("progress");progress.setAccessible(true);Bitmap frame=Bitmap.createBitmap(1000,700,Bitmap.Config.ARGB_8888);
        for(boolean rtl:new boolean[]{true,false}){view.rtl=rtl;view.effect="book";view.setPages(solid(Color.RED),1,false);view.setPages(solid(Color.BLUE),1,true);
            for(float t:new float[]{0,.25f,.5f,.75f,.99f}){progress.setFloat(view,t);view.draw(new Canvas(frame));int c=frame.getPixel(500,350);check(Color.red(c)<60&&Color.blue(c)<60,"book gutter opaque rtl="+rtl+" progress="+t);}
            view.clear();
        }
        view.rtl=true;view.effect="cover";view.setPages(solid(Color.RED),1,false);view.draw(new Canvas(frame));int before=0;while(before<1000&&Color.red(frame.getPixel(before,350))<200)before++;
        view.setPages(solid(Color.BLUE),1,true);progress.setFloat(view,.3f);view.draw(new Canvas(frame));int after=0;while(after<1000&&!(Color.red(frame.getPixel(after,350))>200&&Color.blue(frame.getPixel(after,350))<30))after++;
        check(after>before+150&&after<1000,"cover outgoing spread moves opposite incoming spread");view.clear();frame.recycle();
        final int[] commits={0};view.listener=new ReaderSurface.Listener(){public void turn(int step){commits[0]+=step;}public void center(){}public boolean preview(int step,long request){view.supplyPreview(request,solid(Color.BLUE));return true;}};view.setPages(solid(Color.RED),1,false);swipe(view,200,800);check(commits[0]==1,"synchronous RAM preview participates in drag without losing bitmaps");view.clear();
        Bitmap large=Bitmap.createBitmap(1600,2400,Bitmap.Config.RGB_565);large.eraseColor(Color.GREEN);ByteArrayOutputStream encoded=new ByteArrayOutputStream();large.compress(Bitmap.CompressFormat.JPEG,80,encoded);large.recycle();Bitmap fitted=Books.image(encoded.toByteArray(),600);check(fitted.getWidth()==600&&fitted.getHeight()==900,"oversized scans are fitted to requested texture resolution");fitted.recycle();
    }catch(Exception e){throw new RuntimeException(e);}}
    public void onCreate(Bundle args){super.onCreate(args);start();}
    public void onStart(){Bundle result=new Bundle();try{
        check(Core.xml("<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.1//EN' 'http://invalid.example/xhtml.dtd'><html><body><img src='cover.png'/></body></html>".getBytes("UTF-8")).getDocumentElement().getNodeName().equals("html"),"Android XHTML doctype without external fetch");
        boolean rejected=false;try{Core.xml("<!DOCTYPE html [<!ENTITY x SYSTEM 'file:///private'>]><html>&x;</html>".getBytes("UTF-8"));}catch(IOException expected){rejected=true;}check(rejected,"Android custom entity rejected");
        final int[] turns={0};
        runOnMainSync(()->{
            ReaderSurface view=new ReaderSurface(getTargetContext());view.layout(0,0,1000,700);view.listener=new ReaderSurface.Listener(){public void turn(int step){turns[0]+=step;}public void center(){}public boolean preview(int step,long request){return true;}};
            Bitmap initial=Bitmap.createBitmap(200,300,Bitmap.Config.RGB_565);initial.eraseColor(Color.RED);view.setPages(java.util.Collections.singletonList(initial),1,false);
            swipe(view,200,800);check(turns[0]==1,"RTL drag crosses center once");
            swipe(view,800,200);check(turns[0]==0,"RTL reverse drag");
            swipe(view,500,900);check(turns[0]==0,"center-start drag does not turn");
            swipe(view,200,550);check(turns[0]==1,"crossing midpoint turns before far center boundary");
            swipe(view,800,450);check(turns[0]==0,"reverse midpoint crossing turns");
            swipe(view,200,490);check(turns[0]==0,"same-half drag does not turn");
            swipe(view,200,500);check(turns[0]==0,"exact midpoint does not turn");
            view.rtl=false;swipe(view,200,800);check(turns[0]==-1,"LTR drag reverses direction");
            try{java.lang.reflect.Field zoom=ReaderSurface.class.getDeclaredField("zoom");zoom.setAccessible(true);zoom.setFloat(view,2);swipe(view,200,800);check(turns[0]==-1,"zoomed drag pans without turning");zoom.setFloat(view,1);}catch(Exception e){throw new RuntimeException(e);}
            view.rtl=true;view.effect="book";java.util.List<Bitmap> first=new java.util.ArrayList<>(),next=new java.util.ArrayList<>();
            for(int i=0;i<2;i++){Bitmap b=Bitmap.createBitmap(200,300,Bitmap.Config.RGB_565);b.eraseColor(Color.RED);first.add(b);b=Bitmap.createBitmap(200,300,Bitmap.Config.RGB_565);b.eraseColor(Color.BLUE);next.add(b);}
            view.setPages(first,1,false);view.setPages(next,1,true);
            try{java.lang.reflect.Field progress=ReaderSurface.class.getDeclaredField("progress");progress.setAccessible(true);Bitmap frame=Bitmap.createBitmap(1000,700,Bitmap.Config.ARGB_8888);for(float t:new float[]{.25f,.5f,.75f}){progress.setFloat(view,t);view.draw(new Canvas(frame));try(FileOutputStream out=new FileOutputStream(new File(getTargetContext().getExternalFilesDir("qa-frames"),"book-"+(int)(t*100)+".png"))){frame.compress(Bitmap.CompressFormat.PNG,100,out);}}frame.recycle();check(true,"book leaf projections render before and after spine");}catch(Exception e){throw new RuntimeException(e);}view.clear();
        });
        runOnMainSync(this::renderingChecks);
        android.content.Context target=getTargetContext(),test=getContext();
        List<JSONObject> sources=new ArrayList<>();Uri tree=DocumentsContract.buildTreeDocumentUri(test.getPackageName()+".documents","root");
        Bundle ready=new Bundle();ready.putString("stream","READY_FIXTURE_GRANT\n");sendStatus(0,ready);
        long grantDeadline=SystemClock.elapsedRealtime()+15000;boolean granted=false;
        while(SystemClock.elapsedRealtime()<grantDeadline){try{target.getContentResolver().takePersistableUriPermission(tree,Intent.FLAG_GRANT_READ_URI_PERMISSION);granted=true;break;}catch(SecurityException pending){Thread.sleep(100);}}
        if(!granted)throw new AssertionError("Fixture provider grant timed out");
        for(String name:test.getAssets().list(""))if(name.endsWith(".pdf")||name.endsWith(".epub")||name.endsWith(".mobi")) {
            Uri uri=DocumentsContract.buildDocumentUriUsingTree(tree,name);byte[] before=hash(uri);
            try(Books.Engine engine=Books.open(target.getContentResolver(),uri,name)){
                check(engine.count()==(name.endsWith(".mobi")?2:5),"page count "+name);
                Bitmap first=engine.render(0,600);int color=first.getPixel(first.getWidth()/2,first.getHeight()/2);check(Color.red(color)>230&&Color.green(color)<30,"first page "+name);first.recycle();
                Bitmap next=engine.render(1,600);color=next.getPixel(next.getWidth()/2,next.getHeight()/2);check(name.endsWith(".mobi")?Color.blue(color)>230:Color.green(color)>90,"next page "+name);next.recycle();
            }
            check(Arrays.equals(before,hash(uri)),"source unchanged "+name);sources.add(Store.file(name,uri.toString()));
        }
        for(String name:new String[]{"scan.zip","scan.rar","scan.7z","unicode.zip"}){
            Uri uri=DocumentsContract.buildDocumentUriUsingTree(tree,name);byte[] before=hash(uri);
            try(Books.Engine book=Books.open(target.getContentResolver(),uri,name)){
                check(book.count()==5,"archive page count "+name);
                Bitmap b=book.render(0,600);check(Color.red(b.getPixel(10,10))>230&&Color.green(b.getPixel(10,10))<30,"natural first page "+name);b.recycle();
                b=book.render(4,600);check(Color.red(b.getPixel(10,10))>90&&Color.blue(b.getPixel(10,10))>90,"natural last page "+name);b.recycle();
            }
            check(Arrays.equals(before,hash(uri)),"archive unchanged "+name);
        }
        JSONObject images=Store.file("散图",DocumentsContract.buildDocumentUriUsingTree(tree,"images").toString());images.put("kind","images");
        try(Books.Engine book=Books.open(target.getContentResolver(),images)){
            check(book.count()==2,"image folder is one book with two pages");
            Bitmap b=book.render(0,600);check(Color.red(b.getPixel(10,10))>230,"image folder natural order");b.recycle();
        }
        Intent intent=new Intent(target,MainActivity.class);intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        ready.putString("stream","READY_UI\n");sendStatus(0,ready);
        MainActivity a=(MainActivity)startActivitySync(intent);
        runOnMainSync(()->{try{a.persist(tree);a.store.add(sources);a.openBook(sources.stream().filter(b->b.optString("title").endsWith(".epub")).findFirst().get(),0);}catch(Exception e){throw new RuntimeException(e);}});
        waitUntil(()->a.engine!=null&&!a.busy);runOnMainSync(()->a.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE));waitUntil(()->a.root.getWidth()>a.root.getHeight()&&!a.busy);
        runOnMainSync(()->a.display(1,false));waitUntil(()->!a.busy&&a.volume.optInt("page")==1);
        waitUntil(()->a.nearby.size()==2);check(a.nearby.size()==2,"both neighbouring spreads predecoded in bounded RAM cache");
        waitUntil(()->a.surface.getWidth()>0&&a.surface.getHeight()>0);
        java.lang.reflect.Field pages=ReaderSurface.class.getDeclaredField("pages");pages.setAccessible(true);
        check(((List<?>)pages.get(a.surface)).size()==2,"landscape dual pages");
        final Bitmap[] frames=new Bitmap[2];final int[] size=new int[2];
        runOnMainSync(()->{size[0]=a.surface.getWidth();size[1]=a.surface.getHeight();frames[0]=Bitmap.createBitmap(size[0],size[1],Bitmap.Config.ARGB_8888);a.surface.draw(new Canvas(frames[0]));a.center();frames[1]=Bitmap.createBitmap(a.surface.getWidth(),a.surface.getHeight(),Bitmap.Config.ARGB_8888);a.surface.draw(new Canvas(frames[1]));});
        check(a.surface.getWidth()==size[0]&&a.surface.getHeight()==size[1]&&frames[0].sameAs(frames[1]),"overlay keeps page size and pixels");frames[0].recycle();frames[1].recycle();
        final double[] seconds={0};runOnMainSync(()->{a.paused=false;a.tick();seconds[0]=a.owner.optDouble("seconds");a.onWindowFocusChanged(false);});Thread.sleep(1250);runOnMainSync(a::tick);check(a.owner.optDouble("seconds")-seconds[0]>=1,"visible reader time survives focus loss");
        runOnMainSync(()->{a.tick();a.paused=true;a.tick();seconds[0]=a.owner.optDouble("seconds");});Thread.sleep(1100);runOnMainSync(a::tick);check(a.owner.optDouble("seconds")==seconds[0],"manual pause stops time");
        waitUntil(()->a.nearby.containsKey(a.turnTarget(1)));
        runOnMainSync(()->{if(a.controls)a.center();a.surface.effect="book";touch(a.surface,android.view.MotionEvent.ACTION_DOWN,.2f);touch(a.surface,android.view.MotionEvent.ACTION_MOVE,.4f);});Thread.sleep(250);
        final Bitmap[] gpuFrame={null};final int[] copied={-1};java.util.concurrent.CountDownLatch capture=new java.util.concurrent.CountDownLatch(1);
        runOnMainSync(()->{gpuFrame[0]=Bitmap.createBitmap(a.root.getWidth(),a.root.getHeight(),Bitmap.Config.ARGB_8888);android.view.PixelCopy.request(a.getWindow(),gpuFrame[0],resultCode->{copied[0]=resultCode;capture.countDown();},a.handler);});
        check(capture.await(3,java.util.concurrent.TimeUnit.SECONDS)&&copied[0]==android.view.PixelCopy.SUCCESS&&a.surface.isHardwareAccelerated(),"capture actual GPU-rendered held book drag");int gutter=gpuFrame[0].getPixel(gpuFrame[0].getWidth()/2,gpuFrame[0].getHeight()/2);check(Color.red(gutter)<60&&Color.blue(gutter)<60,"GPU compositing preserves the opaque double-page gutter");
        try(FileOutputStream out=new FileOutputStream(new File(target.getExternalFilesDir("qa-frames"),"gpu-book-held.png"))){gpuFrame[0].compress(Bitmap.CompressFormat.PNG,100,out);}gpuFrame[0].recycle();
        runOnMainSync(()->touch(a.surface,android.view.MotionEvent.ACTION_UP,.4f));waitUntil(()->!a.surface.isInteracting());
        final int[] incoming={0},outgoing={0};runOnMainSync(()->{List<Bitmap> next=a.nearby.get(a.turnTarget(1));Bitmap first=next.get(0);incoming[0]=first.getPixel(first.getWidth()/2,first.getHeight()/2);try{Bitmap last=(Bitmap)((List<?>)pages.get(a.surface)).get(1);outgoing[0]=last.getPixel(last.getWidth()/2,last.getHeight()/2);}catch(Exception e){throw new RuntimeException(e);}a.surface.effect="cover";touch(a.surface,android.view.MotionEvent.ACTION_DOWN,.2f);touch(a.surface,android.view.MotionEvent.ACTION_MOVE,.45f);});Thread.sleep(250);Bitmap coverFrame=captureGpu(a);
        try(FileOutputStream out=new FileOutputStream(new File(target.getExternalFilesDir("qa-frames"),"gpu-cover-held.png"))){coverFrame.compress(Bitmap.CompressFormat.PNG,100,out);}
        runOnMainSync(()->{Bitmap software=Bitmap.createBitmap(a.root.getWidth(),a.root.getHeight(),Bitmap.Config.ARGB_8888);a.surface.draw(new Canvas(software));check(colorNear(software.getPixel(software.getWidth()/10,software.getHeight()/2),incoming[0]),"software cover shows incoming content");software.recycle();});
        check(colorNear(coverFrame.getPixel(coverFrame.getWidth()/10,coverFrame.getHeight()/2),incoming[0]),"GPU cover displays incoming spread while dragging actual="+Integer.toHexString(coverFrame.getPixel(coverFrame.getWidth()/10,coverFrame.getHeight()/2))+" expected="+Integer.toHexString(incoming[0]));check(colorNear(coverFrame.getPixel(coverFrame.getWidth()*4/10,coverFrame.getHeight()/2),outgoing[0]),"GPU cover simultaneously displays outgoing spread");coverFrame.recycle();
        runOnMainSync(()->touch(a.surface,android.view.MotionEvent.ACTION_UP,.45f));waitUntil(()->!a.surface.isInteracting());
        runOnMainSync(()->a.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT));waitUntil(()->a.root.getWidth()<a.root.getHeight()&&!a.busy);check(((List<?>)pages.get(a.surface)).size()==1,"portrait single page");
        waitUntil(()->a.nearby.containsKey(a.turnTarget(1)));final Bitmap[] prefetched={null};runOnMainSync(()->prefetched[0]=a.nearby.get(a.turnTarget(1)).get(0));
        final int dragPage=a.volume.optInt("page");final Bitmap[] dragFrames=new Bitmap[2];
        runOnMainSync(()->{dragFrames[0]=Bitmap.createBitmap(a.surface.getWidth(),a.surface.getHeight(),Bitmap.Config.ARGB_8888);a.surface.draw(new Canvas(dragFrames[0]));});
        runOnMainSync(()->{a.surface.effect="slide";touch(a.surface,android.view.MotionEvent.ACTION_DOWN,.2f);touch(a.surface,android.view.MotionEvent.ACTION_MOVE,.4f);});
        waitUntil(()->{try{java.lang.reflect.Field f=ReaderSurface.class.getDeclaredField("pages");f.setAccessible(true);return !((List<?>)f.get(a.surface)).isEmpty();}catch(Exception e){throw new RuntimeException(e);}});
        check(a.surface.isInteracting()&&a.volume.optInt("page")==dragPage,"held drag previews without committing page");
        check(((List<?>)pages.get(a.surface)).get(0)==prefetched[0],"drag takes prefetched texture without another decode");
        runOnMainSync(()->{dragFrames[1]=Bitmap.createBitmap(a.surface.getWidth(),a.surface.getHeight(),Bitmap.Config.ARGB_8888);a.surface.draw(new Canvas(dragFrames[1]));});check(!dragFrames[0].sameAs(dragFrames[1]),"held slide changes rendered position before finger release");for(Bitmap frame:dragFrames)frame.recycle();
        runOnMainSync(()->{try{java.lang.reflect.Field p=ReaderSurface.class.getDeclaredField("progress");p.setAccessible(true);check(p.getFloat(a.surface)>.15f&&p.getFloat(a.surface)<.3f,"slide progress follows finger displacement");}catch(Exception e){throw new RuntimeException(e);}touch(a.surface,android.view.MotionEvent.ACTION_UP,.4f);});
        waitUntil(()->!a.surface.isInteracting());check(a.volume.optInt("page")==dragPage,"short drag settles back without changing page");
        check(a.nearby.get(a.turnTarget(1)).get(0)==prefetched[0]&&!prefetched[0].isRecycled(),"cancelled drag keeps preview texture for reuse");
        runOnMainSync(()->{touch(a.surface,android.view.MotionEvent.ACTION_DOWN,.2f);touch(a.surface,android.view.MotionEvent.ACTION_MOVE,.55f);touch(a.surface,android.view.MotionEvent.ACTION_UP,.55f);});
        waitUntil(()->!a.surface.isInteracting()&&a.volume.optInt("page")!=dragPage);check(a.volume.optInt("page")==dragPage+1,"released drag commits already rendered preview once");
        runOnMainSync(()->a.scanFolder(tree,true,true));waitUntil(()->a.store.books().length()==4);JSONObject group=a.store.books().optJSONObject(3);check(group.optJSONArray("volumes").length()==3,"SAF tree imports three-volume group");
        runOnMainSync(()->{a.showDetail(group);ArrayList<android.view.View> menus=new ArrayList<>();a.root.findViewsWithText(menus,"分卷更多操作",android.view.View.FIND_VIEWS_WITH_CONTENT_DESCRIPTION);check(menus.size()==3,"each volume exposes one accessible overflow menu");ArrayList<android.view.View> inline=new ArrayList<>();a.root.findViewsWithText(inline,"移除此卷",android.view.View.FIND_VIEWS_WITH_TEXT);check(inline.isEmpty(),"volume actions are tucked into overflow menus");});
        runOnMainSync(()->{try{a.store.mark(group.optJSONArray("volumes").getJSONObject(0),"已读");}catch(Exception e){throw new RuntimeException(e);}});check(!Store.allRead(group),"collection requires every volume read");
        runOnMainSync(()->{try{for(int i=0;i<3;i++)a.store.mark(group.optJSONArray("volumes").getJSONObject(i),"已读");}catch(Exception e){throw new RuntimeException(e);}});check(Store.allRead(group),"all volumes read detected");
        runOnMainSync(()->{try{JSONObject fake=Store.file("跨午夜测试","test://fixture");a.store.addTime(fake,fake,2,ZonedDateTime.of(2026,10,11,23,59,59,0,ZoneId.systemDefault()).toInstant().toEpochMilli(),ZonedDateTime.of(2026,10,12,0,0,1,0,ZoneId.systemDefault()).toInstant().toEpochMilli());a.store.save();a.showStats();}catch(Exception e){throw new RuntimeException(e);}});
        check(a.store.data.optJSONObject("stats").optJSONObject("daily").has("2026-10-12"),"daily records split midnight");
        check(!a.running,"statistics page stops reading time");
        runOnMainSync(()->{a.showShelf();a.saveQuiet();});Store restored=new Store(target);check(restored.books().length()==4,"library persists URI references");
        File[] pageCache=target.getCacheDir().listFiles();boolean noBookCache=true;if(pageCache!=null)for(File cached:pageCache)if(!cached.isDirectory()||!cached.getName().equals("oat_primary"))noBookCache=false;check(noBookCache,"no book or page files in cache (excluding runtime oat_primary): "+Arrays.toString(pageCache));
        final JSONObject[] removed={null};final byte[][] original={null};
        runOnMainSync(()->{try{group.put("currentVolume",2);group.put("coverVolume",2);removed[0]=group.getJSONArray("volumes").getJSONObject(0);original[0]=hash(Uri.parse(removed[0].getString("uri")));a.performRemoveVolume(group,removed[0]);}catch(Exception e){throw new RuntimeException(e);}});
        check(group.optJSONArray("volumes").length()==2&&group.optInt("currentVolume")==1&&group.optInt("coverVolume")==1,"remove volume adjusts current and cover indices");
        check(Arrays.equals(original[0],hash(Uri.parse(removed[0].getString("uri")))),"removed volume source unchanged");
        runOnMainSync(()->{try{a.performRemoveVolume(group,group.getJSONArray("volumes").getJSONObject(0));a.performRemoveVolume(group,group.getJSONArray("volumes").getJSONObject(0));}catch(Exception e){throw new RuntimeException(e);}});
        check(a.store.find(group.optString("id"))==null&&a.store.books().length()==3,"last volume removes empty collection only");
        check(a.store.data.optJSONObject("stats").optDouble("totalSeconds")>0,"removal retains reading history");
        List<JSONObject> collections=a.collectFolders(tree,"batch");
        check(collections.size()==2&&collections.get(0).optString("title").equals("collection2"),"batch folders remain separate in natural order");
        check(collections.get(0).optJSONArray("volumes").length()==3&&collections.get(1).optJSONArray("volumes").length()==3,"batch scans all volumes per collection");
        JSONObject first=collections.get(0);String canonical=DocumentsContract.buildTreeDocumentUri(tree.getAuthority(),"collection2").toString();JSONObject direct=Store.file("direct",canonical).put("kind","folder");
        check(Store.sourceKey(first).equals(Store.sourceKey(direct)),"batch and individual folder imports deduplicate");
        try(Books.Engine book=Books.open(target.getContentResolver(),Uri.parse(first.getJSONArray("volumes").getJSONObject(0).getString("uri")),first.getJSONArray("volumes").getJSONObject(0).getString("title"))){check(book.count()>0,"batch collection keeps readable original URIs");}
        result.putString("stream","\nNative Android checks passed: "+passed+"\n");finish(Activity.RESULT_OK,result);
    }catch(Throwable e){result.putString("stream","FAIL: "+android.util.Log.getStackTraceString(e));finish(Activity.RESULT_CANCELED,result);}}
}
