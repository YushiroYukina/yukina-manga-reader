package cn.migi.reader;

import android.content.Context;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.time.*;
import java.util.*;

public final class Store {
    public static final String[] STATUSES={"未标记","想读","在读","已读","搁置","弃读"};
    final AtomicFile file; public final JSONObject data;
    public Store(Context context) throws Exception {
        File directory=new File(context.getFilesDir(),"data");if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("无法创建书库目录");
        file=new AtomicFile(new File(directory,"library.json"));
        if(file.getBaseFile().exists())try(InputStream in=file.openRead()){data=new JSONObject(new String(Core.readBounded(in,16*1024*1024),"UTF-8"));}
        else {data=new JSONObject();data.put("books",new JSONArray());data.put("stats",new JSONObject().put("totalSeconds",0).put("daily",new JSONObject()));data.put("settings",new JSONObject().put("rtl",true).put("gap",16).put("effect","book").put("theme","sage"));}
        if(!data.has("stats"))data.put("stats",new JSONObject().put("totalSeconds",0).put("daily",new JSONObject()));
        if(!data.getJSONObject("stats").has("daily"))data.getJSONObject("stats").put("daily",new JSONObject());
    }
    public synchronized void save() throws IOException {
        FileOutputStream out=null;
        try {out=file.startWrite();out.write(data.toString().getBytes("UTF-8"));file.finishWrite(out);}
        catch(Exception e){if(out!=null)file.failWrite(out);throw new IOException("书库保存失败",e);}
    }
    public JSONArray books() {return data.optJSONArray("books");}
    public JSONObject settings(){return data.optJSONObject("settings");}
    public static JSONObject file(String title,String uri) throws JSONException {
        return new JSONObject().put("id",UUID.randomUUID().toString()).put("title",title).put("uri",uri).put("page",0).put("seconds",0).put("status","未标记");
    }
    public JSONObject find(String id) {
        for(int i=0;i<books().length();i++){JSONObject b=books().optJSONObject(i);if(id.equals(b.optString("id")))return b;}return null;
    }
    static String sourceKey(JSONObject b){
        String raw=b.optString("uri");try{android.net.Uri uri=android.net.Uri.parse(raw);String id=uri.getPathSegments().contains("document")?android.provider.DocumentsContract.getDocumentId(uri):android.provider.DocumentsContract.getTreeDocumentId(uri);raw=uri.getAuthority()+":"+id;}catch(Exception ignored){}
        return raw+":"+b.optString("kind");
    }
    public int add(List<JSONObject> incoming) throws Exception {
        Set<String> known=new HashSet<>();for(int i=0;i<books().length();i++){JSONObject b=books().getJSONObject(i);known.add(sourceKey(b));}
        int count=0;for(JSONObject b:incoming)if(known.add(sourceKey(b))){books().put(b);count++;}
        save();return count;
    }
    public void mark(JSONObject entry,String value) throws Exception {
        String status=value.trim();if(status.length()>30||status.contains("\n"))throw new IOException("状态最多 30 个字");
        entry.put("status",status.isEmpty()?"未标记":status);save();
    }
    public static boolean allRead(JSONObject owner) {
        JSONArray volumes=owner.optJSONArray("volumes");if(volumes==null||volumes.length()==0)return false;
        for(int i=0;i<volumes.length();i++)if(!"已读".equals(volumes.optJSONObject(i).optString("status")))return false;return true;
    }
    public void addTime(JSONObject owner,JSONObject volume,double seconds,long wallStart,long wallEnd) throws Exception {
        if(owner==null||seconds<=0)return;
        owner.put("seconds",owner.optDouble("seconds")+seconds);
        if(volume!=null&&owner!=volume)volume.put("seconds",volume.optDouble("seconds")+seconds);
        JSONObject stats=data.getJSONObject("stats");stats.put("totalSeconds",stats.optDouble("totalSeconds")+seconds);
        if(Math.abs((wallEnd-wallStart)/1000.0-seconds)>2)wallStart=wallEnd-(long)(seconds*1000);
        JSONObject daily=stats.getJSONObject("daily");double remaining=seconds;long cursor=wallStart;
        while(remaining>0.000001) {
            ZonedDateTime local=Instant.ofEpochMilli(cursor).atZone(ZoneId.systemDefault());String day=local.toLocalDate().toString();
            long midnight=local.toLocalDate().plusDays(1).atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli();
            double chunk=Math.min(remaining,Math.max(.001,(midnight-cursor)/1000.0));
            if(!stats.has("dailyStarted"))stats.put("dailyStarted",day);
            JSONObject bucket=daily.optJSONObject(day);if(bucket==null){bucket=new JSONObject().put("seconds",0).put("books",new JSONObject());daily.put(day,bucket);}
            bucket.put("seconds",bucket.optDouble("seconds")+chunk);
            JSONObject entries=bucket.getJSONObject("books");String id=owner.getString("id");JSONObject record=entries.optJSONObject(id);
            if(record==null){record=new JSONObject().put("seconds",0).put("volumes",new JSONObject());entries.put(id,record);}
            record.put("title",owner.optString("title"));record.put("seconds",record.optDouble("seconds")+chunk);
            if(volume!=null&&owner!=volume){JSONObject children=record.getJSONObject("volumes");String vid=volume.getString("id");JSONObject v=children.optJSONObject(vid);if(v==null){v=new JSONObject().put("seconds",0);children.put(vid,v);}v.put("title",volume.optString("title"));v.put("seconds",v.optDouble("seconds")+chunk);}
            cursor+=(long)(chunk*1000);remaining-=chunk;
        }
    }
}
