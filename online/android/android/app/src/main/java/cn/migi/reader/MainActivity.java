package cn.migi.reader;

import android.app.*;
import android.content.*;
import android.content.res.Configuration;
import android.database.Cursor;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.*;
import android.os.storage.StorageManager;
import android.os.storage.StorageVolume;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import android.view.*;
import android.widget.*;
import android.util.LruCache;
import org.json.*;
import java.io.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;

public final class MainActivity extends Activity implements ReaderSurface.Listener {
    static final int SHELF=0,DETAIL=1,READER=2,STATS=3,FILES=100,FOLDER=101,COVER=102,BATCH_FOLDER=103;
    final Handler handler=new Handler(Looper.getMainLooper());
    final ExecutorService worker=Executors.newSingleThreadExecutor(),imports=Executors.newSingleThreadExecutor(),onlinePreloads=Executors.newSingleThreadExecutor();
    final Set<String> prompted=new HashSet<>(),coverPending=new HashSet<>();final LruCache<String,Bitmap> thumbs=new LruCache<>(32);
    OnlineUi onlineUi; Store store;FrameLayout root;ReaderSurface surface;LinearLayout top,bottom;TextView clock,counter;
    Books.Engine engine;JSONObject owner,volume,detail;GridView grid;ShelfAdapter adapter;
    // At most two neighbouring spreads in RAM. Never write page images to storage.
    final Map<Integer,List<Bitmap>> nearby=new HashMap<>();final Set<Integer> warming=new HashSet<>();
    final Map<Integer,Long> previewWaiters=new HashMap<>();int warmEpoch;
    int screen=SHELF,returnScreen=SHELF,generation=0;boolean visible=false,screenOn=true,paused=false,running=false,busy=false,controls=false,dead=false;
    long lastMono,lastWall,lastSave;String search="";int bg=0xff181e20,panel=0xff222c2e,text=0xffe7ebe5,accent=0xffa2c9b1,muted=0xff97a7a8;
    final Runnable heartbeat=new Runnable(){public void run(){tick();if(!dead)handler.postDelayed(this,1000);}};
    final BroadcastReceiver screenReceiver=new BroadcastReceiver(){public void onReceive(Context c,Intent i){tick();screenOn=!Intent.ACTION_SCREEN_OFF.equals(i.getAction());tick();}};

    public void onCreate(Bundle state) {
        super.onCreate(state);
        try {store=new Store(this);}catch(Exception e){new AlertDialog.Builder(this).setTitle("书库无法读取").setMessage("原书库数据未覆盖。请保留应用数据后排查："+e.getMessage()).setPositiveButton("关闭",(d,w)->finish()).setCancelable(false).show();return;}
        root=new FrameLayout(this);setContentView(root);loadTheme();
        try{onlineUi=new OnlineUi(this);}catch(Exception e){error("在线书源初始化失败",e);}
        lastMono=SystemClock.elapsedRealtime();lastWall=System.currentTimeMillis();lastSave=lastMono;
        IntentFilter filter=new IntentFilter();filter.addAction(Intent.ACTION_SCREEN_OFF);filter.addAction(Intent.ACTION_SCREEN_ON);
        if(Build.VERSION.SDK_INT>=33)registerReceiver(screenReceiver,filter,Context.RECEIVER_NOT_EXPORTED);else registerReceiver(screenReceiver,filter);
        showShelf();handler.postDelayed(heartbeat,1000);
        if(state!=null&&state.getInt("screen",SHELF)==READER){String id=state.getString("owner");JSONObject saved=store.find(id==null?"":id);boolean restorePause=state.getBoolean("paused");if(saved!=null){openBook(saved,state.getInt("volume",0));paused=restorePause;}}
    }
    public void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);state.putInt("screen",screen);state.putString("owner",owner==null?null:owner.optString("id"));state.putInt("volume",owner==null?0:owner.optInt("currentVolume"));state.putBoolean("paused",paused);saveQuiet();}
    public void onStart(){super.onStart();visible=true;PowerManager pm=(PowerManager)getSystemService(POWER_SERVICE);screenOn=pm.isInteractive();tick();}
    public void onStop(){tick();visible=false;tick();saveQuiet();super.onStop();}
    // Focus is intentionally ignored: a visible split-screen reader keeps time.
    public void onWindowFocusChanged(boolean focus){super.onWindowFocusChanged(focus);if(focus&&screen==READER)immersive();}
    public void onConfigurationChanged(Configuration configuration){super.onConfigurationChanged(configuration);if(screen==READER){placeOverlays();root.post(()->{if(engine!=null)display(volume.optInt("page"),false);});}else if(screen==SHELF)showShelf();else if(screen==OnlineUi.SCREEN)onlineUi.show();else if(screen==OnlineUi.CACHE)onlineUi.downloads();}
    public void onDestroy(){dead=true;if(onlineUi!=null)onlineUi.shutdown();clearNearby();handler.removeCallbacksAndMessages(null);tick();saveQuiet();try{unregisterReceiver(screenReceiver);}catch(Exception ignored){}Books.Engine old=engine;engine=null;if(old!=null)worker.execute(()->close(old));worker.shutdown();imports.shutdown();onlinePreloads.shutdownNow();if(surface!=null)surface.clear();super.onDestroy();}
    void tick(){
        if(store==null)return;long now=SystemClock.elapsedRealtime(),wall=System.currentTimeMillis();double elapsed=(now-lastMono)/1000.0;
        if(running&&elapsed>0&&elapsed<=5)try{store.addTime(owner,volume,elapsed,lastWall,wall);}catch(Exception e){error("计时记录失败",e);}
        lastMono=now;lastWall=wall;running=Core.reading(visible,screenOn,screen==READER,paused,engine!=null&&!busy);
        if(clock!=null&&screen==READER)clock.setText("本书 "+Core.duration(owner==null?0:owner.optDouble("seconds"))+" · "+(running?"计时中":"已暂停"));
        if(now-lastSave>=15000){saveQuiet();lastSave=now;}
    }
    void saveQuiet(){if(store!=null)try{store.save();}catch(Exception e){Toast.makeText(this,e.getMessage(),Toast.LENGTH_LONG).show();}}
    int dp(float value){return (int)(getResources().getDisplayMetrics().density*value+.5f);}
    void loadTheme(){
        String name=store.settings().optString("theme","sage");boolean paper=name.equals("paper");
        bg=paper?0xfff3eee4:0xff181e20;panel=paper?0xffe9e4d8:0xff222c2e;text=paper?0xff333c32:0xffe7ebe5;muted=paper?0xff7b8176:0xff97a7a8;
        accent=name.equals("ocean")?0xff99c4de:name.equals("violet")?0xffbba8db:name.equals("rose")?0xffdbabbc:name.equals("amber")?0xffd8bc82:name.equals("paper")?0xff637e53:0xffa2c9b1;
        root.setBackgroundColor(bg);getWindow().setStatusBarColor(bg);getWindow().setNavigationBarColor(bg);
    }
    GradientDrawable rounded(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
    LinearLayout column(){LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v;}
    LinearLayout row(){LinearLayout v=new LinearLayout(this);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
    TextView label(String value,int size,int color){TextView v=new TextView(this);v.setText(value);v.setTextColor(color);v.setTextSize(size);v.setPadding(dp(4),dp(6),dp(4),dp(6));return v;}
    Button button(String title,Runnable action){Button b=new Button(this);b.setAllCaps(false);b.setText(title);b.setTextColor(text);b.setTextSize(14);b.setBackground(rounded(panel,10));b.setPadding(dp(12),dp(3),dp(12),dp(3));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,dp(46));p.setMargins(dp(4),dp(4),dp(4),dp(4));b.setLayoutParams(p);b.setOnClickListener(v->action.run());return b;}
    void rowButton(LinearLayout row,String name,Runnable action){row.addView(button(name,action));}
    LinearLayout page(String title,Runnable back){
        systemBars();root.removeAllViews();LinearLayout page=column();page.setPadding(dp(24),dp(16),dp(24),dp(16));
        LinearLayout heading=row();heading.addView(label(title,26,text),new LinearLayout.LayoutParams(0,-2,1));if(back!=null)rowButton(heading,"返回",back);page.addView(heading);root.addView(page,new FrameLayout.LayoutParams(-1,-1));return page;
    }
    void systemBars(){getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE);getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);}
    void immersive(){getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_LAYOUT_STABLE);getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);}
    void changeScreen(int value){if(value!=READER){clearNearby();if(surface!=null)surface.finish();}tick();screen=value;tick();saveQuiet();}

    void showShelf(){
        if(store==null)return;changeScreen(SHELF);LinearLayout page=page("我的书库",null);
        HorizontalScrollView scroll=new HorizontalScrollView(this);LinearLayout tools=row();scroll.addView(tools);page.addView(scroll);
        rowButton(tools,"在线发现",()->onlineUi.show());rowButton(tools,"书源管理",()->onlineUi.sources());rowButton(tools,"下载与缓存",()->onlineUi.downloads());rowButton(tools,"＋ 批量文件",()->pickFiles());rowButton(tools,"＋ 文件夹",()->pickFolder());rowButton(tools,"＋ 批量合辑",()->pickBatchFolder());rowButton(tools,"＋ TF 卡",()->pickRemovable());rowButton(tools,"累计 "+Core.duration(store.data.optJSONObject("stats").optDouble("totalSeconds")),()->showStats());rowButton(tools,"主题",()->themeDialog());rowButton(tools,"清理封面",()->clearCovers());rowButton(tools,"清空书库",()->clearLibrary());if(engine!=null)rowButton(tools,"返回阅读",()->showReader());
        EditText query=new EditText(this);query.setTextColor(text);query.setHintTextColor(muted);query.setHint("搜索书名或分卷");query.setSingleLine(true);query.setText(search);page.addView(query);
        grid=new GridView(this);grid.setColumnWidth(dp(180));grid.setNumColumns(GridView.AUTO_FIT);grid.setStretchMode(GridView.STRETCH_COLUMN_WIDTH);grid.setHorizontalSpacing(dp(14));grid.setVerticalSpacing(dp(14));grid.setPadding(0,dp(12),0,0);grid.setClipToPadding(false);
        adapter=new ShelfAdapter();grid.setAdapter(adapter);page.addView(grid,new LinearLayout.LayoutParams(-1,0,1));
        grid.setOnItemClickListener((p,v,index,id)->showDetail(adapter.entries.get(index)));
        grid.setOnItemLongClickListener((p,v,index,id)->{statusDialog(adapter.entries.get(index),null);return true;});
        query.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int st,int c,int a){}public void onTextChanged(CharSequence s,int st,int before,int count){search=s.toString();adapter.refresh();}public void afterTextChanged(android.text.Editable s){}});
        for(int i=0;i<store.books().length();i++){
            JSONObject entry=store.books().optJSONObject(i);String id=entry.optString("id");
            if(entry.optString("coverUri").isEmpty()&&!coverFile(entry).exists()&&coverPending.add(id))imports.execute(()->{
                generateCover(entry);handler.post(()->{coverPending.remove(id);if(!dead&&screen==SHELF&&adapter!=null)adapter.notifyDataSetChanged();});
            });
        }
        if(store.books().length()==0)page.addView(label("导入 PDF、EPUB、MOBI、ZIP、RAR、7z 或散图文件夹开始阅读。仅记录授权地址，不复制原书。",14,muted));
    }
    final class ShelfAdapter extends BaseAdapter {
        final List<JSONObject> entries=new ArrayList<>();ShelfAdapter(){refresh();}
        void refresh(){entries.clear();for(int i=0;i<store.books().length();i++){JSONObject b=store.books().optJSONObject(i);if(b.toString().toLowerCase(Locale.ROOT).contains(search.toLowerCase(Locale.ROOT)))entries.add(b);}entries.sort((a,b)->Double.compare(b.optDouble("lastRead",0),a.optDouble("lastRead",0)));notifyDataSetChanged();}
        public int getCount(){return entries.size();}public Object getItem(int i){return entries.get(i);}public long getItemId(int i){return i;}
        public View getView(int index,View unused,android.view.ViewGroup parent){
            JSONObject b=entries.get(index);LinearLayout card=column();card.setPadding(dp(12),dp(10),dp(12),dp(10));card.setBackground(rounded(panel,16));
            ImageView cover=new ImageView(MainActivity.this);cover.setScaleType(ImageView.ScaleType.FIT_CENTER);Bitmap image=thumbnail(b);if(image!=null)cover.setImageBitmap(image);else {cover.setBackground(rounded(accent,10));cover.setImageResource(android.R.drawable.ic_menu_gallery);}card.addView(cover,new LinearLayout.LayoutParams(-1,dp(210)));
            TextView title=label(b.optString("title"),16,text);title.setMaxLines(2);title.setEllipsize(android.text.TextUtils.TruncateAt.END);card.addView(title);
            JSONArray vols=b.optJSONArray("volumes");card.addView(label((vols==null?b.optString("title").replaceAll("^.*\\.","").toUpperCase(Locale.ROOT):vols.length()+(b.has("online")?" 章":" 卷"))+" · "+b.optString("status","未标记"),12,muted));
            if(b.has("online"))card.addView(label(onlineUi.sourceName(b),12,accent));
            card.addView(label(Core.duration(b.optDouble("seconds")),12,muted));return card;
        }
    }
    File coverFile(JSONObject entry){File root=getExternalFilesDir("covers");if(root==null)root=new File(getFilesDir(),"covers");root.mkdirs();return new File(root,entry.optString("id")+".png");}
    Bitmap thumbnail(JSONObject entry){String key=entry.optString("id");Bitmap bitmap=thumbs.get(key);if(bitmap!=null)return bitmap;try{
        String custom=entry.optString("coverUri");if(!custom.isEmpty())try(InputStream in=getContentResolver().openInputStream(Uri.parse(custom))){bitmap=Books.image(Core.readBounded(in,32*1024*1024),240);}
        else{BitmapFactory.Options options=new BitmapFactory.Options();options.inSampleSize=2;bitmap=BitmapFactory.decodeFile(coverFile(entry).getAbsolutePath(),options);}
        if(bitmap!=null)thumbs.put(key,bitmap);
    }catch(Exception ignored){}return bitmap;}
    void generateCover(JSONObject entry){
        if(!entry.optString("coverUri").isEmpty()||coverFile(entry).exists())return;
        JSONObject source=entry;JSONArray children=entry.optJSONArray("volumes");if(children!=null&&children.length()>0)source=children.optJSONObject(Math.max(0,Math.min(children.length()-1,entry.optInt("coverVolume"))));
        try(Books.Engine book=Books.open(getContentResolver(),source)){
            Bitmap image=book.render(0,420),cover=Bitmap.createBitmap(420,600,Bitmap.Config.RGB_565);Canvas canvas=new Canvas(cover);canvas.drawColor(Color.WHITE);float scale=Math.min(420f/image.getWidth(),600f/image.getHeight());float w=image.getWidth()*scale,h=image.getHeight()*scale;canvas.drawBitmap(image,null,new RectF((420-w)/2,(600-h)/2,(420+w)/2,(600+h)/2),new Paint(Paint.FILTER_BITMAP_FLAG));
            File target=coverFile(entry),tmp=new File(target.getParentFile(),target.getName()+".tmp");try(FileOutputStream out=new FileOutputStream(tmp)){if(!cover.compress(Bitmap.CompressFormat.PNG,100,out))throw new IOException("封面保存失败");}if(!tmp.renameTo(target))tmp.delete();image.recycle();cover.recycle();
        }catch(Exception ignored){} // Failure leaves a placeholder, not a false cover.
    }
    void clearCovers(){new AlertDialog.Builder(this).setTitle("清理封面缩略图？").setMessage("只清理小图，不删除图书、进度和阅读历史。之后打开图书时会重新生成。").setPositiveButton("清理",(d,w)->{File directory=coverFile(new JSONObject()).getParentFile();File[] files=directory.listFiles();if(files!=null)for(File f:files)if(f.isFile()&&(f.getName().endsWith(".png")||f.getName().endsWith(".tmp")))f.delete();thumbs.evictAll();showShelf();}).setNegativeButton("取消",null).show();}

    void showDetail(JSONObject entry){
        detail=entry;changeScreen(DETAIL);LinearLayout page=page("图书详情",()->showShelf());
        if(entry.has("online")){LinearLayout tools=row();rowButton(tools,"刷新在线目录",()->onlineUi.refresh(entry));rowButton(tools,"下载与缓存",()->onlineUi.downloads(entry));page.addView(tools);}
        ScrollView scroller=new ScrollView(this);scroller.setFillViewport(true);LinearLayout content=column();scroller.addView(content);page.addView(scroller,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout hero=row();hero.setPadding(dp(20),dp(16),dp(20),dp(16));hero.setBackground(rounded(panel,20));
        ImageView cover=new ImageView(this);cover.setScaleType(ImageView.ScaleType.FIT_CENTER);Bitmap image=thumbnail(entry);if(image!=null)cover.setImageBitmap(image);else{cover.setBackground(rounded(bg,12));cover.setImageResource(android.R.drawable.ic_menu_gallery);}hero.addView(cover,new LinearLayout.LayoutParams(dp(120),dp(168)));
        LinearLayout info=column();info.setPadding(dp(20),0,0,0);hero.addView(info,new LinearLayout.LayoutParams(0,-2,1));TextView title=label(entry.optString("title"),24,text);title.setMaxLines(3);title.setEllipsize(android.text.TextUtils.TruncateAt.END);info.addView(title);
        if(entry.has("online"))info.addView(label(onlineUi.sourceName(entry),13,muted));
        JSONArray children=entry.optJSONArray("volumes");info.addView(label((children==null?"单卷图书":children.length()+(entry.has("online")?" 个章节":" 卷合辑"))+"  ·  "+entry.optString("status","未标记"),14,accent));
        TextView time=label("累计阅读  "+Core.duration(entry.optDouble("seconds")),15,muted);time.setOnClickListener(v->showStats());info.addView(time);
        LinearLayout actions=row();Button read=button("继续阅读",()->openBook(entry,entry.optInt("currentVolume")));read.setBackground(rounded(accent,10));read.setTextColor(bg);actions.addView(read);rowButton(actions,"阅读状态",()->statusDialog(entry,entry));info.addView(actions);
        Button more=button("⋮",()->{});more.setContentDescription("图书更多操作");more.setTextSize(26);more.setOnClickListener(v->{PopupMenu menu=new PopupMenu(this,v);menu.getMenu().add("更换封面").setOnMenuItemClickListener(m->{pickCover();return true;});menu.getMenu().add("查看图书位置").setOnMenuItemClickListener(m->{TextView location=label(entry.optString("uri"),14,text);location.setTextIsSelectable(true);new AlertDialog.Builder(this).setTitle("图书位置").setView(location).setPositiveButton("关闭",null).show();return true;});menu.getMenu().add("移出书库").setOnMenuItemClickListener(m->{remove(entry);return true;});menu.show();});hero.addView(more,new LinearLayout.LayoutParams(dp(48),dp(48)));content.addView(hero);
        LinearLayout heading=row();heading.setPadding(0,dp(16),0,dp(8));heading.addView(label(children==null?"阅读进度":entry.has("online")?"章节目录":"分卷目录",20,text),new LinearLayout.LayoutParams(0,-2,1));content.addView(heading);
        LinearLayout list=column();content.addView(list);
        if(children==null){list.setBackground(rounded(panel,14));list.setPadding(dp(16),dp(12),dp(16),dp(12));list.addView(label(progressLabel(entry),16,text));return;}
        EditText query=new EditText(this);query.setSingleLine(true);query.setTextColor(text);query.setHintTextColor(muted);query.setHint(entry.has("online")?"筛选章节…":"筛选分卷…");heading.addView(query,new LinearLayout.LayoutParams(dp(220),dp(48)));
        for(int i=0;i<children.length();i++){
            int index=i;JSONObject child=children.optJSONObject(i);LinearLayout line=row();line.setTag(child.optString("title").toLowerCase(Locale.ROOT));line.setPadding(dp(12),dp(10),dp(12),dp(10));line.setBackground(rounded(panel,14));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,0,0,dp(8));list.addView(line,lp);
            TextView number=label(String.format(Locale.ROOT,"%02d",i+1),18,accent);number.setGravity(Gravity.CENTER);line.addView(number,new LinearLayout.LayoutParams(dp(48),-1));
            LinearLayout body=column();TextView name=label(child.optString("title"),16,text);name.setMaxLines(2);name.setEllipsize(android.text.TextUtils.TruncateAt.END);body.addView(name);body.addView(label(progressLabel(child)+"   ·   "+Core.duration(child.optDouble("seconds"))+"   ·   "+child.optString("status","未标记"),13,muted));line.addView(body,new LinearLayout.LayoutParams(0,-2,1));body.setOnClickListener(v->openBook(entry,index));number.setOnClickListener(v->openBook(entry,index));
            Button overflow=button("⋮",()->{});overflow.setTextSize(25);overflow.setContentDescription("分卷更多操作："+child.optString("title"));overflow.setOnClickListener(v->volumeMenu(v,entry,child,index));line.addView(overflow,new LinearLayout.LayoutParams(dp(48),dp(48)));
        }
        query.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int st,int c,int a){}public void afterTextChanged(android.text.Editable s){}public void onTextChanged(CharSequence s,int st,int before,int count){String key=s.toString().toLowerCase(Locale.ROOT);for(int i=0;i<list.getChildCount();i++){View child=list.getChildAt(i);child.setVisibility(child.getTag().toString().contains(key)?View.VISIBLE:View.GONE);}}});
    }
    String progressLabel(JSONObject book){return book.has("total")?(book.optInt("page")+1)+" / "+book.optInt("total")+" 页":"尚未开始";}
    void volumeMenu(View anchor,JSONObject entry,JSONObject child,int index){PopupMenu menu=new PopupMenu(this,anchor);menu.getMenu().add("阅读此卷").setOnMenuItemClickListener(m->{openBook(entry,index);return true;});menu.getMenu().add("标记状态").setOnMenuItemClickListener(m->{statusDialog(child,entry);return true;});menu.getMenu().add("设为总封面").setOnMenuItemClickListener(m->{try{entry.remove("coverUri");entry.put("coverVolume",index);store.save();coverFile(entry).delete();thumbs.remove(entry.optString("id"));imports.execute(()->{generateCover(entry);handler.post(()->{if(!dead&&screen==DETAIL&&detail==entry)showDetail(entry);});});Toast.makeText(this,"已选此卷为总封面",Toast.LENGTH_SHORT).show();}catch(Exception e){error("设置封面失败",e);}return true;});menu.getMenu().add("移除此卷").setOnMenuItemClickListener(m->{removeVolume(entry,child);return true;});menu.show();}
    void remove(JSONObject entry){new AlertDialog.Builder(this).setTitle("移出书库？").setMessage("不会删除原图书，阅读历史也会保留。").setPositiveButton("移出",(d,w)->{try{JSONArray next=new JSONArray();for(int i=0;i<store.books().length();i++)if(store.books().optJSONObject(i)!=entry)next.put(store.books().get(i));store.data.put("books",next);store.save();if(owner==entry)releaseBook();showShelf();}catch(Exception e){error("移出失败",e);}}).setNegativeButton("取消",null).show();}
    void clearLibrary(){new AlertDialog.Builder(this).setTitle("清空书库？").setMessage("移除所有单卷和多卷合辑的书库记录。保留阅读历史、设置及所有原图书文件。").setPositiveButton("清空书库",(d,w)->{try{releaseBook();store.data.put("books",new JSONArray());store.save();detail=null;prompted.clear();showShelf();}catch(Exception e){error("清空失败",e);}}).setNegativeButton("取消",null).show();}
    void removeVolume(JSONObject group,JSONObject child){new AlertDialog.Builder(this).setTitle("移除此卷？").setMessage("仅将《"+child.optString("title")+"》移出合辑，不改动原文件和阅读历史。最后一卷移除后，合辑也会移出书库。").setPositiveButton("移除",(d,w)->{try{
        performRemoveVolume(group,child);
    }catch(Exception e){error("移除此卷失败",e);}}).setNegativeButton("取消",null).show();}
    void performRemoveVolume(JSONObject group,JSONObject child)throws Exception {
        if(owner==group)releaseBook();
        JSONArray old=group.getJSONArray("volumes"),next=new JSONArray();int removed=-1;
        for(int i=0;i<old.length();i++){JSONObject v=old.getJSONObject(i);if(v==child)removed=i;else next.put(v);}
        if(removed<0)return;
        if(next.length()==0){JSONArray books=new JSONArray();for(int i=0;i<store.books().length();i++)if(store.books().optJSONObject(i)!=group)books.put(store.books().get(i));store.data.put("books",books);store.save();showShelf();return;}
        int current=group.optInt("currentVolume"),cover=group.optInt("coverVolume");
        group.put("volumes",next);group.put("currentVolume",Math.max(0,Math.min(next.length()-1,current>removed?current-1:current)));
        group.put("coverVolume",Math.max(0,Math.min(next.length()-1,cover>removed?cover-1:cover)));
        store.save();prompted.remove("group:"+group.optString("id"));
        if(cover==removed&&group.optString("coverUri").isEmpty()){coverFile(group).delete();thumbs.remove(group.optString("id"));imports.execute(()->{generateCover(group);handler.post(()->{if(!dead&&screen==DETAIL&&detail==group)showDetail(group);});});}
        showDetail(group);
    }
    void statusDialog(JSONObject entry,JSONObject group){
        List<String> names=new ArrayList<>(Arrays.asList(Store.STATUSES));names.add("自定义…");
        new AlertDialog.Builder(this).setTitle("阅读状态").setItems(names.toArray(new String[0]),(d,i)->{if(i<Store.STATUSES.length)mark(entry,Store.STATUSES[i],group);else{EditText field=new EditText(this);field.setText(entry.optString("status"));new AlertDialog.Builder(this).setTitle("自定义状态（最多 30 字）").setView(field).setPositiveButton("保存",(a,b)->mark(entry,field.getText().toString(),group)).setNegativeButton("取消",null).show();}}).show();
    }
    void mark(JSONObject entry,String status,JSONObject group){try{store.mark(entry,status);if(screen==DETAIL&&detail!=null)showDetail(detail);else if(screen==SHELF)adapter.refresh();if(group!=null)checkGroup(group);}catch(Exception e){error("标记失败",e);}}
    void checkGroup(JSONObject group){String key="group:"+group.optString("id");if(!Store.allRead(group)){prompted.remove(key);return;}if("已读".equals(group.optString("status"))||!prompted.add(key))return;
        new AlertDialog.Builder(this).setTitle("合辑阅读完成").setMessage("所有分卷都已标为已读。是否将《"+group.optString("title")+"》整本标为已读？").setPositiveButton("标为已读",(d,w)->mark(group,"已读",null)).setNegativeButton("暂不标记",null).show();}
    void completion(){if(engine==null||volume==null)return;int[] spread=Core.spread(volume.optInt("page"),engine.count(),landscape(),true);String id=volume.optString("id");if(spread[spread.length-1]!=engine.count()-1){prompted.remove(id);return;}if("已读".equals(volume.optString("status"))||!prompted.add(id))return;
        JSONObject done=volume,group=owner;handler.postDelayed(()->{if(dead||screen!=READER||volume!=done)return;new AlertDialog.Builder(this).setTitle("阅读完成").setMessage("已到《"+done.optString("title")+"》最后一页。是否标为已读？").setPositiveButton("标为已读",(d,w)->mark(done,"已读",group==done?null:group)).setNegativeButton("暂不标记",null).show();},450);
    }

    void pickFiles(){Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("*/*");intent.putExtra(Intent.EXTRA_LOCAL_ONLY,true);intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true);intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(intent,FILES);}
    void pickFolder(){Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);intent.putExtra(Intent.EXTRA_LOCAL_ONLY,true);intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(intent,FOLDER);}
    void pickBatchFolder(){new AlertDialog.Builder(this).setTitle("批量导入多卷书").setMessage("请选择作品目录的上一级文件夹，例如 Manga。其下每个子文件夹分别作为一本书，内部文件作为分卷。扫描后可勾选需要导入的作品。").setPositiveButton("选择目录",(d,w)->{Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);intent.putExtra(Intent.EXTRA_LOCAL_ONLY,true);intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(intent,BATCH_FOLDER);}).setNegativeButton("取消",null).show();}
    void pickRemovable(){
        StorageManager manager=(StorageManager)getSystemService(STORAGE_SERVICE);
        List<StorageVolume> cards=new ArrayList<>();List<String> labels=new ArrayList<>();
        for(StorageVolume card:manager.getStorageVolumes())if(card.isRemovable()){
            cards.add(card);String state=card.getState();String status=Environment.MEDIA_MOUNTED.equals(state)?"可读取":Environment.MEDIA_MOUNTED_READ_ONLY.equals(state)?"只读，可导入":Environment.MEDIA_CHECKING.equals(state)?"正在检查":Environment.MEDIA_UNMOUNTED.equals(state)?"未挂载":Environment.MEDIA_SHARED.equals(state)?"被 USB 占用":Environment.MEDIA_UNMOUNTABLE.equals(state)?"无法挂载":"不可用";
            labels.add(card.getDescription(this)+" · "+status);
        }
        if(cards.isEmpty()){new AlertDialog.Builder(this).setTitle("未检测到外置存储卡").setMessage("请确认 TF 卡已插入，并在系统设置的存储页面检查是否已挂载。插入后可重新打开此入口。").setPositiveButton("知道了",null).show();return;}
        new AlertDialog.Builder(this).setTitle("选择 TF 卡 / 外置存储").setItems(labels.toArray(new String[0]),(d,index)->{
            StorageVolume card=cards.get(index);String state=card.getState();
            if(!Environment.MEDIA_MOUNTED.equals(state)&&!Environment.MEDIA_MOUNTED_READ_ONLY.equals(state)){new AlertDialog.Builder(this).setTitle("存储卡暂不可读取").setMessage("请先在系统设置的存储页面挂载这张卡，再返回导入。阅读器不会格式化存储卡。").setPositiveButton("知道了",null).show();return;}
            new AlertDialog.Builder(this).setTitle("从 "+card.getDescription(this)+" 导入").setItems(new String[]{"批量选择文件","选择文件夹（多卷合辑或独立图书）","批量合辑（每个子文件夹一本）"},(dialog,mode)->{
                try{
                    Intent tree=Build.VERSION.SDK_INT>=29?card.createOpenDocumentTreeIntent():new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                    Intent intent=tree;
                    if(mode==0){intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("*/*");intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true);Uri initial=tree.getParcelableExtra(DocumentsContract.EXTRA_INITIAL_URI);if(initial!=null)intent.putExtra(DocumentsContract.EXTRA_INITIAL_URI,initial);}
                    intent.putExtra(Intent.EXTRA_LOCAL_ONLY,true);intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(intent,mode==0?FILES:mode==2?BATCH_FOLDER:FOLDER);
                }catch(Exception e){error("无法打开存储卡选择器",e);}
            }).setNegativeButton("取消",null).show();
        }).setNegativeButton("取消",null).show();
    }
    void pickCover(){Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("image/*");intent.putExtra(Intent.EXTRA_LOCAL_ONLY,true);intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(intent,COVER);}
    void persist(Uri uri){getContentResolver().takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);}
    String name(Uri uri){try(Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())return cursor.getString(0);}catch(Exception ignored){}return uri.getLastPathSegment()==null?"未命名":uri.getLastPathSegment();}
    protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(onlineUi!=null&&onlineUi.result(request,result,data))return;if(result!=RESULT_OK||data==null)return;
        try {
            if(request==COVER&&detail!=null){Uri uri=data.getData();if(uri==null)return;persist(uri);detail.put("coverUri",uri.toString());store.save();thumbs.remove(detail.optString("id"));showDetail(detail);return;}
            if(request==FILES){List<JSONObject> entries=new ArrayList<>();int skipped=0;List<Uri> sources=new ArrayList<>();if(data.getClipData()!=null)for(int i=0;i<data.getClipData().getItemCount();i++)sources.add(data.getClipData().getItemAt(i).getUri());else if(data.getData()!=null)sources.add(data.getData());for(Uri uri:sources){try{String title=name(uri);if(!Core.format(title)){skipped++;continue;}persist(uri);entries.add(Store.file(title,uri.toString()));}catch(Exception failed){skipped++;}}importEntries(entries,skipped);}
            if(request==BATCH_FOLDER&&data.getData()!=null){Uri tree=data.getData();persist(tree);scanCollections(tree);return;}
            if(request==FOLDER&&data.getData()!=null){Uri tree=data.getData();persist(tree);CheckBox recursive=new CheckBox(this);recursive.setText("包含子文件夹");recursive.setChecked(true);new AlertDialog.Builder(this).setTitle("文件夹导入方式").setView(recursive).setPositiveButton("合为多卷书",(d,w)->scanFolder(tree,true,recursive.isChecked())).setNeutralButton("每个文件独立",(d,w)->scanFolder(tree,false,recursive.isChecked())).setNegativeButton("取消",null).show();}
        }catch(Exception e){error("导入失败",e);}
    }
    void importEntries(List<JSONObject> entries,int skipped)throws Exception {int added=store.add(entries);List<JSONObject> accepted=new ArrayList<>();for(JSONObject entry:entries)if(store.find(entry.optString("id"))!=null)accepted.add(entry);showShelf();Toast.makeText(this,"新增 "+added+" 本，重复 "+(entries.size()-added)+" 项，跳过 "+skipped+" 项",Toast.LENGTH_LONG).show();imports.execute(()->{for(JSONObject entry:accepted){if(dead)break;generateCover(entry);handler.post(()->{if(!dead&&screen==SHELF&&adapter!=null)adapter.notifyDataSetChanged();});}});}
    void scanFolder(Uri tree,boolean grouped,boolean recursive){ProgressDialog progress=ProgressDialog.show(this,"扫描文件夹","读取授权目录，不复制图书…",true,false);
        imports.execute(()->{try {List<JSONObject> files=new ArrayList<>();walk(tree,DocumentsContract.getTreeDocumentId(tree),files,recursive,0);files.sort((a,b)->Core.naturalCompare(a.optString("title"),b.optString("title")));if(files.isEmpty())throw new IOException("该目录没有支持的图书、压缩包或图片");List<JSONObject> entries=files;if(grouped&&!(files.size()==1&&"images".equals(files.get(0).optString("kind")))){JSONObject group=Store.file(name(DocumentsContract.buildDocumentUriUsingTree(tree,DocumentsContract.getTreeDocumentId(tree))),tree.toString());group.put("kind","folder");group.put("volumes",new JSONArray(files));group.put("currentVolume",0);entries=Collections.singletonList(group);}List<JSONObject> result=entries;handler.post(()->{progress.dismiss();if(dead)return;try{importEntries(result,0);}catch(Exception e){error("导入失败",e);}});}catch(Exception e){handler.post(()->{progress.dismiss();if(!dead)error("扫描失败",e);});}});
    }
    List<JSONObject> collectFolders(Uri tree)throws Exception {return collectFolders(tree,DocumentsContract.getTreeDocumentId(tree));}
    List<JSONObject> collectFolders(Uri tree,String parentId)throws Exception {
        List<JSONObject> result=new ArrayList<>();int total=0;
        Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(tree,parentId);
        try(Cursor cursor=getContentResolver().query(children,new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE},null,null,null)){
            if(cursor==null)throw new IOException("文件夹读取权限不可用");
            while(cursor.moveToNext()){
                String id=cursor.getString(0),title=cursor.getString(1);
                if(!DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(2)))continue;
                List<JSONObject> volumes=new ArrayList<>();walk(tree,id,volumes,true,0);if(volumes.isEmpty())continue;
                total+=volumes.size();if(total>5000)throw new IOException("图书超过 5000 卷，请分批选择目录");
                volumes.sort((a,b)->Core.naturalCompare(a.optString("title"),b.optString("title")));
                JSONObject group=Store.file(title,DocumentsContract.buildDocumentUriUsingTree(tree,id).toString());group.put("kind","folder");group.put("volumes",new JSONArray(volumes));group.put("currentVolume",0);result.add(group);
            }
        }
        result.sort((a,b)->Core.naturalCompare(a.optString("title"),b.optString("title")));return result;
    }
    void scanCollections(Uri tree){ProgressDialog progress=ProgressDialog.show(this,"扫描多卷书库","按子文件夹整理作品，不复制图书…",true,false);
        imports.execute(()->{try{List<JSONObject> groups=collectFolders(tree);handler.post(()->{progress.dismiss();if(dead)return;if(groups.isEmpty()){error("未找到合辑",new IOException("请选择包含作品子文件夹的上一级目录；各作品文件夹内可放图书、压缩包或散图文件夹。"));return;}
            boolean[] chosen=new boolean[groups.size()];Arrays.fill(chosen,true);String[] titles=new String[groups.size()];for(int i=0;i<titles.length;i++)titles[i]=groups.get(i).optString("title")+" · "+groups.get(i).optJSONArray("volumes").length()+" 卷";
            AlertDialog dialog=new AlertDialog.Builder(this).setTitle("选择导入合辑（"+groups.size()+" 部）").setMultiChoiceItems(titles,chosen,(d,i,value)->chosen[i]=value).setPositiveButton("导入所选",(d,w)->{List<JSONObject> entries=new ArrayList<>();for(int i=0;i<chosen.length;i++)if(chosen[i])entries.add(groups.get(i));try{if(!entries.isEmpty())importEntries(entries,0);}catch(Exception e){error("批量导入失败",e);}}).setNeutralButton("全选 / 全不选",null).setNegativeButton("取消",null).create();dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->{boolean all=true;for(boolean selected:chosen)all&=selected;for(int i=0;i<chosen.length;i++){chosen[i]=!all;dialog.getListView().setItemChecked(i,!all);}}));dialog.show();
        });}catch(Exception e){handler.post(()->{progress.dismiss();if(!dead)error("批量扫描失败",e);});}});
    }
    void walk(Uri tree,String id,List<JSONObject> files,boolean recursive,int depth)throws Exception {
        if(depth>12||files.size()>5000)throw new IOException("目录过深或图书超过 5000 个，请分文件夹导入");
        Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(tree,id);boolean images=false;
        try(Cursor cursor=getContentResolver().query(children,new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE},null,null,null)){
            if(cursor==null)throw new IOException("文件夹读取权限不可用");
            while(cursor.moveToNext()){
                String child=cursor.getString(0),title=cursor.getString(1),mime=cursor.getString(2);
                if(title.startsWith(".")||title.equals("__MACOSX"))continue;
                if(DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)){if(recursive)walk(tree,child,files,true,depth+1);}
                else if(ScanBooks.page(title))images=true;
                else if(Core.format(title)){
                    if(files.size()>=5000)throw new IOException("图书超过 5000 个，请分文件夹导入");
                    files.add(Store.file(title,DocumentsContract.buildDocumentUriUsingTree(tree,child).toString()));
                }
            }
        }
        if(images){
            Uri folder=DocumentsContract.buildDocumentUriUsingTree(tree,id);
            JSONObject book=Store.file(name(folder),folder.toString());book.put("kind","images");files.add(book);
        }
    }

    boolean landscape(){return root.getWidth()>0?root.getWidth()>root.getHeight():getResources().getConfiguration().orientation==Configuration.ORIENTATION_LANDSCAPE;}
    void openBook(JSONObject entry,int index){
        clearNearby();
        tick();paused=false;Books.Engine old=engine;engine=null;running=false;owner=entry;JSONArray children=entry.optJSONArray("volumes");volume=children==null?entry:children.optJSONObject(Math.max(0,Math.min(children.length()-1,index)));if(volume==null){error("无法打开",new IOException("合辑没有分卷"));return;}try{entry.put("currentVolume",index);}catch(Exception ignored){}
        int token=++generation;busy=true;if(surface!=null)surface.clear();showReader();JSONObject requested=volume;
        worker.execute(()->{close(old);try{Books.Engine opened=Books.open(getContentResolver(),requested);handler.post(()->{if(dead||token!=generation){close(opened);return;}engine=opened;busy=false;display(Math.min(opened.count()-1,requested.optInt("page")),false);});}catch(Exception e){handler.post(()->{if(!dead&&token==generation){busy=false;showDetail(entry);error("无法打开图书",e);}});}});
    }
    void releaseBook(){clearNearby();tick();generation++;Books.Engine previous=engine;engine=null;owner=volume=null;if(surface!=null)surface.clear();worker.execute(()->close(previous));running=false;}
    static void close(Books.Engine engine){if(engine!=null)try{engine.close();}catch(Exception ignored){}}
    void showReader(){
        changeScreen(READER);root.removeAllViews();if(surface==null){surface=new ReaderSurface(this);surface.listener=this;}configureSurface();root.addView(surface,new FrameLayout.LayoutParams(-1,-1));controls=false;
        top=column();top.setPadding(dp(12),dp(8),dp(12),dp(8));top.setBackground(rounded(panel,14));
        LinearLayout line=row();rowButton(line,"书库",()->showShelf());TextView title=label(owner==null?"阅读":owner.optString("title"),16,text);title.setMaxLines(1);title.setEllipsize(android.text.TextUtils.TruncateAt.END);line.addView(title,new LinearLayout.LayoutParams(0,-2,1));clock=label("",13,muted);clock.setOnClickListener(v->showStats());line.addView(clock);top.addView(line);
        HorizontalScrollView toolsScroll=new HorizontalScrollView(this);LinearLayout tools=row();toolsScroll.addView(tools);top.addView(toolsScroll);
        rowButton(tools,"暂停 / 继续",()->{tick();paused=!paused;tick();saveQuiet();});rowButton(tools,"阅读外观",()->appearance());if(volume!=null&&volume.has("online"))rowButton(tools,"在线画质 / 预加载",()->onlineUi.readingSettings());rowButton(tools,"分卷目录",()->{if(owner!=null)showDetail(owner);});rowButton(tools,"标记状态",()->{if(volume!=null)statusDialog(volume,owner==volume?null:owner);});
        bottom=row();bottom.setPadding(dp(12),dp(8),dp(12),dp(8));bottom.setBackground(rounded(panel,14));rowButton(bottom,"← 下一页",()->turn(1));counter=label("加载中…",14,text);counter.setGravity(Gravity.CENTER);bottom.addView(counter,new LinearLayout.LayoutParams(0,-2,1));counter.setOnClickListener(v->jump());rowButton(bottom,"上一页 →",()->turn(-1));
        root.addView(top,new FrameLayout.LayoutParams(-1,-2,Gravity.TOP));root.addView(bottom,new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM));top.setVisibility(View.GONE);bottom.setVisibility(View.GONE);immersive();tick();
        if(engine!=null){updateCounter();if(surface!=null)root.post(()->display(volume.optInt("page"),false));}
    }
    void configureSurface(){surface.rtl=store.settings().optBoolean("rtl",true);surface.gap=store.settings().optInt("gap",16);surface.effect=store.settings().optString("effect","book");surface.setBackgroundColor(store.settings().optString("theme").equals("paper")?0xffe5dfd2:0xff101416);}
    void placeOverlays(){if(top==null||screen!=READER)return;FrameLayout.LayoutParams t=(FrameLayout.LayoutParams)top.getLayoutParams(),b=(FrameLayout.LayoutParams)bottom.getLayoutParams();t.setMargins(dp(12),dp(12),dp(12),0);b.setMargins(dp(12),0,dp(12),dp(12));top.setLayoutParams(t);bottom.setLayoutParams(b);}
    public void center(){if(screen!=READER)return;controls=!controls;top.setVisibility(controls?View.VISIBLE:View.GONE);bottom.setVisibility(controls?View.VISIBLE:View.GONE);placeOverlays();immersive();}
    int turnTarget(int step){if(engine==null||volume==null)return -1;int page=volume.optInt("page");int[] spread=Core.spread(page,engine.count(),landscape(),true);int next=step>0?spread[spread.length-1]+1:Math.max(0,page-(landscape()?2:1));return next>=engine.count()||next==page?-1:next;}
    public boolean preview(int step,long request){
        if(engine==null||busy||screen!=READER)return false;int target=turnTarget(step);if(target<0)return false;
        List<Bitmap> ready=nearby.remove(target);if(ready!=null){surface.supplyPreview(request,ready);return true;}
        previewWaiters.put(target,request);warmSpread(target);return true;
    }
    static void dispose(List<Bitmap> images){if(images!=null)for(Bitmap b:images)if(!b.isRecycled())b.recycle();}
    void clearNearby(){warmEpoch++;for(List<Bitmap> images:nearby.values())dispose(images);nearby.clear();warming.clear();if(surface!=null)for(long request:previewWaiters.values())surface.previewFailed(request);previewWaiters.clear();}
    public void onTrimMemory(int level){super.onTrimMemory(level);if(level>=TRIM_MEMORY_RUNNING_LOW){clearNearby();if(Online.instance!=null){Online.instance.pageMemory.clear();Online.instance.manifestMemory.clear();}}}
    void keepNearby(int target,List<Bitmap> images){long bytes=0;for(List<Bitmap> spread:nearby.values())for(Bitmap b:spread)bytes+=b.getAllocationByteCount();for(Bitmap b:images)bytes+=b.getAllocationByteCount();if(bytes<=32L*1024*1024)nearby.put(target,images);else dispose(images);}
    void warmNeighbours(){if(dead||screen!=READER||engine==null||busy||engine instanceof Online.Engine&&!store.settings().optBoolean("onlinePreload",true))return;for(int step:new int[]{1,-1}){int target=turnTarget(step);if(target>=0)warmSpread(target);}}
    public boolean retainSpread(int step,List<Bitmap> images){int target=turnTarget(step);if(target<0||dead||screen!=READER)return false;dispose(nearby.remove(target));keepNearby(target,images);return true;}
    public void previewSettled(){warmEpoch++;warming.clear();previewWaiters.clear();int next=turnTarget(1),previous=turnTarget(-1);Iterator<Map.Entry<Integer,List<Bitmap>>> iterator=nearby.entrySet().iterator();while(iterator.hasNext()){Map.Entry<Integer,List<Bitmap>> item=iterator.next();if(item.getKey()!=next&&item.getKey()!=previous){dispose(item.getValue());iterator.remove();}}warmNeighbours();}
    void warmSpread(int target){
        if(nearby.containsKey(target)||!warming.add(target))return;
        Books.Engine book=engine;JSONObject current=volume;ReaderSurface view=surface;int token=generation;int[] indices=Core.spread(target,book.count(),landscape(),true);int width=Math.max(600,root.getWidth()/indices.length);
        int epoch=warmEpoch;
        boolean background=book instanceof Online.Engine&&!previewWaiters.containsKey(target);
        (background?onlinePreloads:worker).execute(()->{Online.background.set(background);List<Bitmap> images=new ArrayList<>();try{if(dead||epoch!=warmEpoch||engine!=book)return;for(int index:indices){Bitmap image=book.render(index,width);image.prepareToDraw();images.add(image);}handler.post(()->{if(dead||engine!=book||volume!=current||token!=generation||surface!=view||epoch!=warmEpoch){dispose(images);return;}warming.remove(target);Long request=previewWaiters.remove(target);if(request!=null)view.supplyPreview(request,images);else keepNearby(target,images);});}catch(Exception e){dispose(images);handler.post(()->{if(!dead&&epoch==warmEpoch){warming.remove(target);Long request=previewWaiters.remove(target);if(request!=null){view.previewFailed(request);error("页面读取失败",e);}}});}});
    }
    public void commitPreview(int step){if(screen!=READER)return;int target=turnTarget(step);if(target<0)return;try{volume.put("page",target);volume.put("total",engine.count());owner.put("lastRead",System.currentTimeMillis());updateCounter();saveQuiet();tick();completion();}catch(Exception e){error("页面记录失败",e);}}
    public void turn(int step){if(engine==null||busy||screen!=READER||surface!=null&&surface.isInteracting())return;int page=volume.optInt("page");int[] spread=Core.spread(page,engine.count(),landscape(),true);int next=step>0?spread[spread.length-1]+1:Math.max(0,page-(landscape()?2:1));if(next>=engine.count()||next==page)return;display(next,true);}
    void display(int page,boolean animate){
        if(engine==null||screen!=READER)return;tick();busy=true;tick();Books.Engine book=engine;JSONObject current=volume;int target=Math.max(0,Math.min(book.count()-1,page)),previous=current.optInt("page");int[] indices=Core.spread(target,book.count(),landscape(),true);int width=Math.max(600,root.getWidth()/indices.length);int token=++generation;
        List<Bitmap> ready=animate?nearby.remove(target):null;clearNearby();
        if(ready!=null){presentSpread(book,current,target,previous,ready,animate);return;}
        worker.execute(()->{List<Bitmap> images=new ArrayList<>();try{for(int index:indices){Bitmap image=book.render(index,width);image.prepareToDraw();images.add(image);}handler.post(()->{if(dead||token!=generation||engine!=book||screen!=READER){dispose(images);return;}presentSpread(book,current,target,previous,images,animate);});}catch(Exception e){dispose(images);handler.post(()->{if(!dead&&token==generation){busy=false;tick();error("页面读取失败",e);}});}});
    }
    void presentSpread(Books.Engine book,JSONObject current,int target,int previous,List<Bitmap> images,boolean animate){try{current.put("page",target);current.put("total",book.count());owner.put("lastRead",System.currentTimeMillis());surface.setPages(images,target>=previous?1:-1,animate);busy=false;updateCounter();saveQuiet();tick();completion();warmNeighbours();JSONObject cover=owner;imports.execute(()->generateCover(cover));}catch(Exception e){busy=false;error("页面显示失败",e);}}
    void updateCounter(){if(counter!=null&&engine!=null){int[] pages=Core.spread(volume.optInt("page"),engine.count(),landscape(),true);counter.setText((pages[0]+1)+(pages.length>1?"–"+(pages[1]+1):"")+" / "+engine.count()+" 页 · 点此跳页");}}
    void jump(){if(engine==null)return;EditText input=new EditText(this);input.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);input.setText(String.valueOf(volume.optInt("page")+1));new AlertDialog.Builder(this).setTitle("跳转页码").setView(input).setPositiveButton("跳转",(d,w)->{try{display(Integer.parseInt(input.getText().toString())-1,false);}catch(Exception e){Toast.makeText(this,"请输入有效页码",Toast.LENGTH_SHORT).show();}}).setNegativeButton("取消",null).show();}
    void appearance(){new AlertDialog.Builder(this).setTitle("阅读外观").setItems(new String[]{"翻页动画  ›","页间距","阅读方向","主题"},(d,i)->{if(i==0)animationDialog();else if(i==1){SeekBar bar=new SeekBar(this);bar.setMax(64);bar.setProgress(surface.gap);new AlertDialog.Builder(this).setTitle("页间距 0–64 dp").setView(bar).setPositiveButton("应用",(a,b)->{try{store.settings().put("gap",bar.getProgress());configureSurface();surface.invalidate();saveQuiet();}catch(Exception e){error("设置失败",e);}}).setNegativeButton("取消",null).show();}else if(i==2){new AlertDialog.Builder(this).setTitle("阅读方向").setSingleChoiceItems(new String[]{"从右向左（日漫）","从左向右"},surface.rtl?0:1,(a,choice)->{try{store.settings().put("rtl",choice==0);configureSurface();surface.invalidate();saveQuiet();a.dismiss();}catch(Exception e){error("设置失败",e);}}).show();}else themeDialog();}).show();}
    void animationDialog(){String[] keys={"book","slide","cover","fade","none"};int selected=Arrays.asList(keys).indexOf(store.settings().optString("effect","book"));new AlertDialog.Builder(this).setTitle("翻页动画").setSingleChoiceItems(new String[]{"书籍翻页","平移","覆盖","淡入淡出","无动画"},Math.max(0,selected),(d,i)->{try{surface.finish();store.settings().put("effect",keys[i]);configureSurface();surface.invalidate();saveQuiet();d.dismiss();}catch(Exception e){error("设置失败",e);}}).setNegativeButton("返回",(d,w)->appearance()).show();}
    void themeDialog(){String[] keys={"sage","ocean","violet","rose","amber","paper"};new AlertDialog.Builder(this).setTitle("主题").setItems(new String[]{"鼠尾草绿","海湾蓝","紫藤","玫瑰","琥珀","暖纸白"},(d,i)->{try{store.settings().put("theme",keys[i]);saveQuiet();loadTheme();if(screen==READER){showReader();}else if(screen==DETAIL)showDetail(detail);else if(screen==STATS)showStats();else showShelf();}catch(Exception e){error("设置失败",e);}}).show();}

    LocalDate statsDate=LocalDate.now();String statsMode="week";
    void showStats(){
        if(screen!=STATS)returnScreen=screen;changeScreen(STATS);LinearLayout page=page("阅读统计",()->statsBack());
        LinearLayout modes=row();for(String mode:new String[]{"week","month","year"})rowButton(modes,mode.equals("week")?"周":mode.equals("month")?"月":"年",()->{statsMode=mode;showStats();});rowButton(modes,"上一期",()->{statsDate=statsMode.equals("week")?statsDate.minusWeeks(1):statsMode.equals("month")?statsDate.minusMonths(1):statsDate.minusYears(1);showStats();});rowButton(modes,"下一期",()->{statsDate=statsMode.equals("week")?statsDate.plusWeeks(1):statsMode.equals("month")?statsDate.plusMonths(1):statsDate.plusYears(1);showStats();});rowButton(modes,"今天",()->{statsDate=LocalDate.now();showStats();});HorizontalScrollView modesScroll=new HorizontalScrollView(this);modesScroll.addView(modes);page.addView(modesScroll);
        ScrollView scroll=new ScrollView(this);LinearLayout body=column();scroll.addView(body);page.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        JSONObject stats=store.data.optJSONObject("stats"),daily=stats.optJSONObject("daily");LocalDate start=statsMode.equals("week")?statsDate.minusDays(statsDate.getDayOfWeek().getValue()-1):statsMode.equals("month")?statsDate.withDayOfMonth(1):statsDate.withDayOfYear(1);int count=statsMode.equals("week")?7:statsMode.equals("month")?start.lengthOfMonth():start.lengthOfYear();
        double[] values=new double[count];Map<String,Double> totals=new HashMap<>();Map<String,String> titles=new HashMap<>();double total=0;int active=0;
        for(int i=0;i<count;i++){JSONObject bucket=daily.optJSONObject(start.plusDays(i).toString());if(bucket==null)continue;values[i]=bucket.optDouble("seconds");total+=values[i];if(values[i]>0)active++;JSONObject books=bucket.optJSONObject("books");if(books==null)continue;for(Iterator<String> keys=books.keys();keys.hasNext();){String key=keys.next();JSONObject entry=books.optJSONObject(key);totals.put(key,totals.getOrDefault(key,0d)+entry.optDouble("seconds"));titles.put(key,entry.optString("title"));}}
        body.addView(label(start+" — "+start.plusDays(count-1),14,muted));
        body.addView(label("阅读 "+Core.duration(total)+"  ·  "+totals.size()+" 本  ·  活跃 "+active+" 天  ·  活跃日均 "+Core.duration(active==0?0:total/active),18,accent));
        body.addView(label("每日阅读趋势 · 点击选择日期",18,text));StatsChart chart=new StatsChart(this,start,values);body.addView(chart,new LinearLayout.LayoutParams(-1,dp(260)));
        body.addView(label("本期阅读 Top 10",20,text));List<String> ranked=new ArrayList<>(totals.keySet());ranked.sort((a,b)->Double.compare(totals.get(b),totals.get(a)));int index=0;for(String key:ranked){if(index>=10)break;body.addView(label((++index)+".  "+titles.get(key)+"    "+Core.duration(totals.get(key)),16,text));}
        if(ranked.isEmpty())body.addView(label("本期暂无阅读记录",14,muted));
        LinearLayout day=row();day.addView(label("当天阅读 · "+statsDate,20,text),new LinearLayout.LayoutParams(0,-2,1));rowButton(day,"选择日期",()->new DatePickerDialog(this,(picker,y,m,d)->{statsDate=LocalDate.of(y,m+1,d);showStats();},statsDate.getYear(),statsDate.getMonthValue()-1,statsDate.getDayOfMonth()).show());body.addView(day);
        JSONObject bucket=daily.optJSONObject(statsDate.toString()),entries=bucket==null?null:bucket.optJSONObject("books");if(entries==null||entries.length()==0)body.addView(label("当天暂无阅读记录",14,muted));else for(Iterator<String> keys=entries.keys();keys.hasNext();){JSONObject entry=entries.optJSONObject(keys.next());body.addView(label(entry.optString("title")+"    "+Core.duration(entry.optDouble("seconds")),17,text));JSONObject volumes=entry.optJSONObject("volumes");if(volumes!=null)for(Iterator<String> v=volumes.keys();v.hasNext();){JSONObject child=volumes.optJSONObject(v.next());body.addView(label("    └ "+child.optString("title")+"    "+Core.duration(child.optDouble("seconds")),14,muted));}}
        body.addView(label("累计阅读 "+Core.duration(stats.optDouble("totalSeconds"))+" · 合辑只累计一次。每日记录在本机保存；不包含小时分布。",13,muted));
    }
    void statsBack(){if(returnScreen==READER&&engine!=null)showReader();else if(returnScreen==DETAIL&&detail!=null)showDetail(detail);else showShelf();}
    final class StatsChart extends View {
        final LocalDate first;final double[] values;final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);StatsChart(Context c,LocalDate start,double[] values){super(c);first=start;this.values=values;setBackground(rounded(panel,14));}
        protected void onDraw(Canvas canvas){super.onDraw(canvas);float left=dp(54),right=getWidth()-dp(16),top=dp(18),bottom=getHeight()-dp(32);double max=60;for(double v:values)max=Math.max(max,v*1.15);p.setTextSize(dp(11));for(int i=0;i<5;i++){float y=bottom-(bottom-top)*i/4;p.setColor(muted);p.setAlpha(70);canvas.drawLine(left,y,right,y,p);p.setAlpha(255);canvas.drawText(String.format(Locale.ROOT,"%.0fm",max*i/240),dp(6),y+dp(3),p);}Path path=new Path();for(int i=0;i<values.length;i++){float x=left+(right-left)*i/Math.max(1,values.length-1),y=bottom-(float)(values[i]/max)*(bottom-top);if(i==0)path.moveTo(x,y);else path.lineTo(x,y);if(values.length<=31){p.setColor(accent);canvas.drawCircle(x,y,dp(3),p);}boolean show=values.length==7||values.length<=31&&i%5==0||values.length>31&&first.plusDays(i).getDayOfMonth()==1;if(show){p.setColor(muted);String label=values.length>31?first.plusDays(i).getMonthValue()+"月":String.valueOf(first.plusDays(i).getDayOfMonth());canvas.drawText(label,x-dp(8),bottom+dp(20),p);}}p.setColor(accent);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(dp(2));canvas.drawPath(path,p);p.setStyle(Paint.Style.FILL);}
        public boolean onTouchEvent(MotionEvent event){if(event.getAction()==MotionEvent.ACTION_UP){float start=dp(54),width=getWidth()-dp(70);int i=Math.max(0,Math.min(values.length-1,Math.round((event.getX()-start)/Math.max(1,width)*(values.length-1))));statsDate=first.plusDays(i);showStats();}return true;}
    }
    public void onBackPressed(){if(screen==OnlineUi.SCREEN||screen==OnlineUi.CACHE){showShelf();return;}if(screen==READER){if(controls)center();else showShelf();}else if(screen==STATS)statsBack();else if(screen==DETAIL)showShelf();else super.onBackPressed();}
    void error(String title,Exception e){if(dead||isFinishing())return;new AlertDialog.Builder(this).setTitle(title).setMessage(e.getMessage()==null?e.toString():e.getMessage()).setPositiveButton("确定",null).show();}
}
