package cn.migi.reader;

import android.content.*;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.net.Uri;
import android.provider.DocumentsContract;
import org.json.*;
import java.io.*;
import java.net.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Original AGPL adapters for public APIs. No scripts, cookies, or extension APKs are executed. */
public final class Online {
    static Online instance;
    final Context context; final Store store;
    final OnlineMemory pageMemory=new OnlineMemory(96L*1024*1024),manifestMemory=new OnlineMemory(2L*1024*1024);
    static final int LIMIT=32*1024*1024;
    Online(Context c,Store s) throws Exception {context=c.getApplicationContext();store=s;
        if(!s.data.has("onlineSources"))s.data.put("onlineSources",new JSONArray());
        try(InputStream in=context.getAssets().open("builtin-sources.json")){
            JSONObject presets=new JSONObject(new String(Core.readBounded(in,1024*1024),"UTF-8"));
            if(mergePresets(s.data,presets))s.save();
        }
        if(!s.settings().has("onlineCacheRoots"))s.settings().put("onlineCacheRoots",new JSONArray());
    }
    static boolean mergePresets(JSONObject data,JSONObject presets)throws Exception{
        if(data.optInt("onlineBuiltinRevision",0)>=presets.getInt("revision"))return false;
        JSONArray sources=data.optJSONArray("onlineSources");if(sources==null){sources=new JSONArray();data.put("onlineSources",sources);}
        Set<String> known=new HashSet<>();for(int i=0;i<sources.length();i++)known.add(sources.getJSONObject(i).getString("id"));
        JSONArray additions=presets.getJSONArray("sources");List<JSONObject> valid=new ArrayList<>();for(int i=0;i<additions.length();i++)valid.add(normalize(additions.getJSONObject(i)));
        for(JSONObject source:valid)if(known.add(source.getString("id")))sources.put(source);
        data.put("onlineBuiltinRevision",presets.getInt("revision"));return true;
    }
    JSONArray sources(){return store.data.optJSONArray("onlineSources");}
    JSONObject source(String id) throws Exception {for(int i=0;i<sources().length();i++){JSONObject s=sources().getJSONObject(i);if(id.equals(s.optString("id"))&&s.optBoolean("enabled",true))return s;}throw new IOException("书源已停用或移除，已下载章节仍可阅读");}
    static String enc(Object value) throws Exception{return URLEncoder.encode(String.valueOf(value),"UTF-8");}
    static String hash(String value) throws Exception{return digest(value.getBytes("UTF-8"));}
    static String digest(byte[] data) throws Exception{byte[] d=MessageDigest.getInstance("SHA-256").digest(data);StringBuilder out=new StringBuilder();for(byte b:d)out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
    static URL checked(String raw) throws Exception{URL url=new URL(raw);if(!(url.getProtocol().equals("https")||url.getProtocol().equals("http"))||url.getHost().isEmpty()||url.getUserInfo()!=null)throw new IOException("仅支持 HTTP(S) 书源地址，账号请填认证字段");
        // Preserve existing percent escapes; percent-encode UTF-8 path/query bytes.
        String host=url.getHost();if(!host.contains(":"))host=IDN.toASCII(host);String value=url.getProtocol()+"://"+host+(url.getPort()<0?"":":"+url.getPort())+url.getFile();StringBuilder ascii=new StringBuilder();for(byte b:value.getBytes("UTF-8")){int c=b&255;if(c>32&&c<127&&"\"<>\\^`{|}".indexOf(c)<0)ascii.append((char)c);else ascii.append(String.format(Locale.ROOT,"%%%02X",c));}return new URL(ascii.toString());}
    static String base(JSONObject s){String b=s.optString("base_url");while(b.endsWith("/"))b=b.substring(0,b.length()-1);return b;}
    static boolean same(URL a,URL b){return a.getProtocol().equalsIgnoreCase(b.getProtocol())&&a.getHost().equalsIgnoreCase(b.getHost())&&(a.getPort()<0?a.getDefaultPort():a.getPort())==(b.getPort()<0?b.getDefaultPort():b.getPort());}
    static final Map<String,Long> last=new HashMap<>();
    static final ThreadLocal<Boolean> background=new ThreadLocal<>(),searching=new ThreadLocal<>();
    static final class SourceHttpError extends IOException {final int code;SourceHttpError(int value){super("书源返回 HTTP "+value+"，请检查服务、认证或稍后重试");code=value;}}
    static byte[] fetch(JSONObject s,String raw,int limit) throws Exception{
        int attempts=Boolean.TRUE.equals(background.get())||Boolean.TRUE.equals(searching.get())?1:3;for(int attempt=0;attempt<attempts;attempt++)try{return fetchOnce(s,raw,limit);}
        catch(SocketTimeoutException|SocketException|UnknownHostException error){if(attempt==attempts-1)throw error;Thread.sleep(500L*(attempt+1));}
        throw new IOException("书源请求未完成");
    }
    static byte[] fetchOnce(JSONObject s,String raw,int limit) throws Exception{
        URL url=checked(raw),root=checked(base(s));
        String key=url.getProtocol()+"://"+url.getAuthority();long interval=s.optString("type").equals("manhuagui")?(same(url,root)?3000:1000):raw.contains("/at-home/")?1600:350;long wait;synchronized(last){long now=System.currentTimeMillis(),due=Math.max(now,last.getOrDefault(key,0L)+interval);last.put(key,due);wait=due-now;}if(wait>0)Thread.sleep(wait);
        int retries=0;
        for(int redirect=0;redirect<6;redirect++){
            HttpURLConnection c=(HttpURLConnection)url.openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(Boolean.TRUE.equals(searching.get())?10000:Boolean.TRUE.equals(background.get())?6000:20000);c.setReadTimeout(Boolean.TRUE.equals(searching.get())?12000:Boolean.TRUE.equals(background.get())?8000:25000);c.setRequestProperty("User-Agent","YukinaOnline/0.1.4-android (personal manga reader; Java)");c.setRequestProperty("Accept","*/*");
            if(SourceHtml.handles(s.optString("type"))||SourceExtra.handles(s.optString("type")))c.setRequestProperty("Referer",s.optString("type").equals("comicabc")?"https://articles.onemoreplace.tw/":base(s)+"/");
            if(same(url,root)){
                if(!s.optString("api_key").isEmpty())c.setRequestProperty("X-API-Key",s.optString("api_key"));
                if(!s.optString("username").isEmpty())c.setRequestProperty("Authorization","Basic "+android.util.Base64.encodeToString((s.optString("username")+":"+s.optString("password")).getBytes("UTF-8"),android.util.Base64.NO_WRAP));
                else if(!s.optString("token").isEmpty())c.setRequestProperty("Authorization","Bearer "+s.optString("token"));
            }
            try{
                int status=c.getResponseCode();
                if(status==429&&!Boolean.TRUE.equals(searching.get())&&retries++<2){int seconds=3;try{seconds=Math.max(1,Math.min(60,Integer.parseInt(c.getHeaderField("Retry-After"))));}catch(Exception ignored){}Thread.sleep(seconds*1000L);redirect--;continue;}
                if(status>=300&&status<400){URL next=checked(new URL(url,c.getHeaderField("Location")).toString());if(url.getProtocol().equals("https")&&!next.getProtocol().equals("https"))throw new IOException("拒绝 HTTPS 降级跳转");url=next;continue;}
                if(status!=200)throw new SourceHttpError(status);
                if(c.getContentLengthLong()>limit)throw new IOException("书源响应过大");
                try(InputStream in=c.getInputStream()){return Core.readBounded(in,limit);}
            }finally{c.disconnect();}
        }throw new IOException("书源重定向次数过多");
    }
    static Object json(JSONObject s,String url) throws Exception{return new JSONTokener(new String(fetch(s,url,8*1024*1024),"UTF-8")).nextValue();}
    static JSONObject api(JSONObject s,String path) throws Exception{return (JSONObject)json(s,base(s)+path);}
    static JSONArray array(JSONObject s,String path) throws Exception{return (JSONArray)json(s,base(s)+path);}
    static JSONObject normalize(JSONObject raw) throws Exception{
        String type=raw.optString("type");if(!Arrays.asList("mangadex","manhuagui","mangapill","goda","comicabc","mangakatana","komga","suwayomi","catalog").contains(type))throw new IOException("不支持的书源类型");checked(raw.optString("base_url"));
        JSONObject s=new JSONObject();for(String k:new String[]{"id","name","type","base_url","language","source_id","username","password","api_key","token","enabled"})if(raw.has(k))s.put(k,raw.get(k));
        if(s.optString("id").isEmpty())s.put("id",UUID.randomUUID().toString());if(s.optString("name").isEmpty())s.put("name",type);if(!s.has("enabled"))s.put("enabled",true);return s;
    }
    void putSource(JSONObject raw) throws Exception{JSONObject s=normalize(raw);for(int i=0;i<sources().length();i++)if(String.valueOf(s.get("id")).equals(sources().getJSONObject(i).optString("id"))){sources().put(i,s);store.save();return;}sources().put(s);store.save();}
    int importSources(String text) throws Exception{
        Object parsed=new JSONTokener(text).nextValue();JSONArray all=parsed instanceof JSONArray?(JSONArray)parsed:((JSONObject)parsed).getJSONArray("sources");if(all.length()>100)throw new IOException("一次最多导入 100 个书源");List<JSONObject> validated=new ArrayList<>();for(int i=0;i<all.length();i++){JSONObject s=normalize(all.getJSONObject(i));for(String k:new String[]{"username","password","api_key","token"})s.remove(k);validated.add(s);}int count=0;
        for(JSONObject s:validated){boolean exists=false;for(int i=0;i<sources().length();i++)if(s.optString("id").equals(sources().getJSONObject(i).optString("id")))exists=true;if(!exists){sources().put(s);count++;}}store.save();return count;
    }
    static class Result {JSONArray books=new JSONArray();boolean more;}
    static JSONObject item(String id,String title,String cover) throws Exception{return new JSONObject().put("id",id).put("title",title).put("cover",cover);}
    static Result search(JSONObject s,String term,int page) throws Exception{
        String type=s.getString("type");Result r=new Result();JSONObject d;
        if(SourceExtra.handles(type))return SourceExtra.search(s,term,page);
        if(SourceHtml.handles(type))return SourceHtml.search(s,term,page);
        if(type.equals("mangadex")){
            d=api(s,"/manga?limit=30&offset="+((page-1)*30)+"&includes%5B%5D=cover_art&contentRating%5B%5D=safe&contentRating%5B%5D=suggestive&order%5BfollowedCount%5D=desc&availableTranslatedLanguage%5B%5D="+enc(s.optString("language","zh"))+(s.optString("language","zh").equals("zh")?"&availableTranslatedLanguage%5B%5D=zh-hk":"")+(term.isEmpty()?"":"&title="+enc(term)));
            JSONArray data=d.getJSONArray("data");for(int i=0;i<data.length();i++){JSONObject b=data.getJSONObject(i),titles=b.getJSONObject("attributes").getJSONObject("title");String title=titles.optString("zh",titles.optString("ja",titles.optString("en","")));if(title.isEmpty()&&titles.keys().hasNext())title=titles.optString(titles.keys().next());String cover="";JSONArray rel=b.optJSONArray("relationships");if(rel!=null)for(int j=0;j<rel.length();j++){JSONObject x=rel.getJSONObject(j);if(x.optString("type").equals("cover_art")&&x.has("attributes"))cover="https://uploads.mangadex.org/covers/"+String.valueOf(b.get("id"))+"/"+enc(x.getJSONObject("attributes").getString("fileName"))+".256.jpg";}r.books.put(item(String.valueOf(b.get("id")),title,cover));}r.more=(page-1)*30+data.length()<d.optInt("total");
        }else if(type.equals("komga")){
            d=api(s,"/api/v1/series?search="+enc(term)+"&page="+(page-1)+"&size=30&sort=metadata.titleSort,asc");JSONArray data=d.getJSONArray("content");for(int i=0;i<data.length();i++){JSONObject b=data.getJSONObject(i);r.books.put(item(String.valueOf(b.get("id")),b.optJSONObject("metadata")==null?b.optString("name"):b.getJSONObject("metadata").optString("title",b.optString("name")),base(s)+"/api/v1/series/"+String.valueOf(b.get("id"))+"/thumbnail"));}r.more=!d.optBoolean("last",true);
        }else if(type.equals("suwayomi")){
            String sid=s.optString("source_id");if(sid.isEmpty())throw new IOException("请先选择 Suwayomi 的已安装扩展书源");d=api(s,"/api/v1/source/"+enc(sid)+(term.isEmpty()?"/popular/"+page:"/search?searchTerm="+enc(term)+"&pageNum="+page));JSONArray data=d.getJSONArray("mangaList");for(int i=0;i<data.length();i++){JSONObject b=data.getJSONObject(i);r.books.put(item(String.valueOf(b.get("id")),b.optString("title"),base(s)+"/api/v1/manga/"+String.valueOf(b.get("id"))+"/thumbnail"));}r.more=d.optBoolean("hasNextPage");
        }else{
            d=(JSONObject)json(s,base(s));JSONArray data=d.getJSONArray("books");int found=0;for(int i=0;i<data.length();i++){JSONObject b=data.getJSONObject(i);if(!b.optString("title").toLowerCase(Locale.ROOT).contains(term.toLowerCase(Locale.ROOT)))continue;if(found>=(page-1)*30&&found<page*30)r.books.put(item(String.valueOf(b.get("id")),b.optString("title"),b.optString("cover").isEmpty()?"":new URL(checked(base(s)),b.optString("cover")).toString()));found++;}r.more=found>page*30;
        }return r;
    }
    static JSONArray chapters(JSONObject s,String book) throws Exception{
        String type=s.getString("type"),bid=enc(book);JSONArray out=new JSONArray();
        if(SourceExtra.handles(type))return SourceExtra.chapters(s,book);
        if(SourceHtml.handles(type))return SourceHtml.chapters(s,book);
        if(type.equals("mangadex")){
            int offset=0;String language=s.optString("language","zh"),langs="&translatedLanguage%5B%5D="+enc(language)+(language.equals("zh")?"&translatedLanguage%5B%5D=zh-hk":"");
            while(true){JSONObject d=api(s,"/manga/"+bid+"/feed?limit=100&offset="+offset+langs+"&order%5Bvolume%5D=asc&order%5Bchapter%5D=asc&includeExternalUrl=0&contentRating%5B%5D=safe&contentRating%5B%5D=suggestive");JSONArray rows=d.getJSONArray("data");for(int i=0;i<rows.length();i++){JSONObject c=rows.getJSONObject(i),a=c.getJSONObject("attributes");if(a.optInt("pages")<=0||!a.isNull("externalUrl")&&!a.optString("externalUrl").isEmpty())continue;String title=(a.isNull("volume")?"":"卷 "+a.optString("volume")+" · ")+(a.isNull("chapter")?"":"第 "+a.optString("chapter")+" 话 · ")+a.optString("title","")+" · "+a.optString("translatedLanguage");out.put(new JSONObject().put("id",String.valueOf(c.get("id"))).put("title",title));}offset+=rows.length();if(rows.length()==0||offset>=d.optInt("total"))break;if(offset>=10000)throw new IOException("章节超过 10000 条，请缩小语言范围");}
        }else if(type.equals("komga")){
            for(int page=0;page<100;page++){JSONObject d=api(s,"/api/v1/series/"+bid+"/books?page="+page+"&size=100&sort=metadata.numberSort,asc");JSONArray rows=d.getJSONArray("content");for(int i=0;i<rows.length();i++){JSONObject b=rows.getJSONObject(i);out.put(new JSONObject().put("id",String.valueOf(b.get("id"))).put("title",b.optJSONObject("metadata")==null?b.optString("name"):b.getJSONObject("metadata").optString("title",b.optString("name"))));}if(d.optBoolean("last",true))return out;}throw new IOException("章节超过 10000 条");
        }else if(type.equals("suwayomi")){
            JSONArray rows=array(s,"/api/v1/manga/"+bid+"/chapters?onlineFetch=true");List<JSONObject> sorted=new ArrayList<>();for(int i=0;i<rows.length();i++)sorted.add(rows.getJSONObject(i));sorted.sort((a,b)->Double.compare(a.optDouble("chapterNumber",a.optInt("index")),b.optDouble("chapterNumber",b.optInt("index"))));for(JSONObject c:sorted)out.put(new JSONObject().put("id",String.valueOf(c.get("id"))).put("title",c.optString("name")).put("index",c.getInt("index")));
        }else{
            JSONArray books=((JSONObject)json(s,base(s))).getJSONArray("books");for(int i=0;i<books.length();i++)if(books.getJSONObject(i).getString("id").equals(book)){JSONArray rows=books.getJSONObject(i).getJSONArray("chapters");for(int j=0;j<rows.length();j++){JSONObject c=rows.getJSONObject(j);JSONArray urls=new JSONArray();for(int k=0;k<c.getJSONArray("pages").length();k++)urls.put(new URL(checked(base(s)),c.getJSONArray("pages").getString(k)).toString());out.put(new JSONObject().put("id",String.valueOf(c.get("id"))).put("title",c.optString("title")).put("pages",urls));}return out;}throw new IOException("书源未找到作品");
        }return out;
    }
    static List<String> pages(JSONObject s,JSONObject meta) throws Exception{
        JSONObject ch=meta.getJSONObject("chapter");String type=s.getString("type"),bid=enc(meta.getString("book_id")),cid=enc(String.valueOf(ch.get("id")));List<String> pages=new ArrayList<>();
        if(type.equals("mangadex")){
            JSONObject d=api(s,"/at-home/server/"+cid+"?forcePort443=true"),c=d.getJSONObject("chapter");boolean original=s.optString("_quality","original").equals("original");JSONArray files=c.optJSONArray(original?"data":"dataSaver");String mode=original?"data":"data-saver";if(files==null||files.length()==0){files=c.getJSONArray(original?"dataSaver":"data");mode=original?"data-saver":"data";}for(int i=0;i<files.length();i++)pages.add(d.getString("baseUrl")+"/"+mode+"/"+enc(c.getString("hash"))+"/"+enc(files.getString(i)));
        }else if(SourceExtra.handles(type)){pages=SourceExtra.pages(s,ch);
        }else if(SourceHtml.handles(type)){pages=SourceHtml.pages(s,ch);
        }else if(type.equals("komga")){JSONArray d=array(s,"/api/v1/books/"+cid+"/pages");for(int i=0;i<d.length();i++)pages.add(base(s)+"/api/v1/books/"+cid+"/pages/"+d.getJSONObject(i).getInt("number"));
        }else if(type.equals("suwayomi")){int idx=ch.getInt("index"),count=api(s,"/api/v1/manga/"+bid+"/chapter/"+idx).getInt("pageCount");for(int i=0;i<count;i++)pages.add(base(s)+"/api/v1/manga/"+bid+"/chapter/"+idx+"/page/"+i);
        }else{JSONArray arr=ch.optJSONArray("pages");if(arr==null){JSONArray rows=chapters(s,meta.getString("book_id"));for(int i=0;i<rows.length();i++)if(rows.getJSONObject(i).getString("id").equals(String.valueOf(ch.get("id"))))arr=rows.getJSONObject(i).optJSONArray("pages");}if(arr!=null)for(int i=0;i<arr.length();i++)pages.add(arr.getString(i));}
        if(pages.isEmpty()||pages.size()>10000)throw new IOException("章节没有可读页面或超过 10000 页");for(String url:pages)checked(url);return pages;
    }
    static byte[] pageBytes(JSONObject s,JSONObject meta,List<String> urls,int index)throws Exception{String current;synchronized(urls){current=urls.get(index);}try{return fetch(s,current,LIMIT);}catch(SourceHttpError e){if(!(s.optString("type").equals("mangadex")||s.optString("type").equals("manhuagui"))||!(e.code==401||e.code==403||e.code==404))throw e;List<String> fresh=pages(s,meta);synchronized(urls){if(fresh.size()!=urls.size())throw new IOException("章节页数已变化，请重新打开章节");for(int i=0;i<fresh.size();i++)urls.set(i,fresh.get(i));}return fetch(s,fresh.get(index),LIMIT);}}
    static String pageIdentity(JSONObject source,String url)throws Exception{if(source.optString("type").equals("manhuagui")){URL u=checked(url);return new URI(u.getProtocol(),u.getAuthority(),u.getPath(),null,null).toString();}String[] parts=checked(url).getPath().split("/");if(source.optString("type").equals("mangadex")&&parts.length>=3&&(parts[parts.length-3].equals("data")||parts[parts.length-3].equals("data-saver")))return parts[parts.length-3]+"/"+parts[parts.length-2]+"/"+parts[parts.length-1];return url;}
    JSONObject add(JSONObject s,JSONObject book,JSONArray chapters) throws Exception{
        if(chapters.length()==0)throw new IOException("没有当前语言的可读章节");String uri="online://"+enc(String.valueOf(s.get("id")))+"/"+enc(String.valueOf(book.get("id")));JSONObject owner=null;
        for(int i=0;i<store.books().length();i++)if(uri.equals(store.books().getJSONObject(i).optString("uri")))owner=store.books().getJSONObject(i);
        boolean isNew=owner==null;if(isNew)owner=Store.file(book.getString("title"),uri);JSONArray children=new JSONArray();Map<String,JSONObject> old=new LinkedHashMap<>();JSONArray prior=owner.optJSONArray("volumes");if(prior!=null)for(int i=0;i<prior.length();i++)old.put(prior.getJSONObject(i).optString("uri"),prior.getJSONObject(i));
        Set<String> seen=new HashSet<>();for(int i=0;i<chapters.length();i++){JSONObject ch=chapters.getJSONObject(i);String path=uri+"/"+enc(String.valueOf(ch.get("id")));if(!seen.add(path))continue;JSONObject v=old.remove(path);if(v==null)v=Store.file(ch.optString("title"),path);v.put("kind","online").put("title",ch.optString("title")).put("online",new JSONObject().put("source_id",String.valueOf(s.get("id"))).put("book_id",String.valueOf(book.get("id"))).put("chapter",ch));children.put(v);}for(JSONObject v:old.values())children.put(v);
        owner.put("kind","folder").put("volumes",children).put("online",new JSONObject().put("source_id",String.valueOf(s.get("id"))).put("book_id",String.valueOf(book.get("id"))).put("title",book.getString("title")).put("cover",book.optString("cover")));if(isNew)store.books().put(owner);store.save();return owner;
    }
    static class Doc {
        final ContentResolver resolver;final Uri tree,uri;
        Doc(ContentResolver r,Uri t,Uri u){resolver=r;tree=t;uri=u;}
        static Doc root(ContentResolver r,Uri tree){return new Doc(r,tree,DocumentsContract.buildDocumentUriUsingTree(tree,DocumentsContract.getTreeDocumentId(tree)));}
        Doc find(String name) throws Exception{Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(tree,DocumentsContract.getDocumentId(uri));try(Cursor c=resolver.query(children,new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME},null,null,null)){while(c!=null&&c.moveToNext())if(name.equals(c.getString(1)))return new Doc(resolver,tree,DocumentsContract.buildDocumentUriUsingTree(tree,c.getString(0)));}return null;}
        Doc create(String name,boolean directory) throws Exception{Doc d=find(name);if(d!=null)return d;Uri u=DocumentsContract.createDocument(resolver,uri,directory?DocumentsContract.Document.MIME_TYPE_DIR:"application/octet-stream",name);if(u==null)throw new IOException("无法在所选目录创建缓存文件");return new Doc(resolver,tree,u);}
        byte[] read() throws Exception{try(InputStream in=resolver.openInputStream(uri)){return Core.readBounded(in,LIMIT);}}
        void write(byte[] data) throws Exception{try(OutputStream out=resolver.openOutputStream(uri,"wt")){if(out==null)throw new IOException("缓存目录不可写");out.write(data);}}
    }
    void selectCache(Uri tree) throws Exception{
        Doc parent=Doc.root(context.getContentResolver(),tree),root=parent.find("YukinaOnlineDownloads");if(root!=null&&root.find(".yukina-online-cache")==null)throw new IOException("同名目录存在其他内容，请选择其他目录");if(root==null)root=parent.create("YukinaOnlineDownloads",true);root.create(".yukina-online-cache",false).write("Yukina Online chapter cache v1".getBytes("UTF-8"));
        JSONArray prev=store.settings().getJSONArray("onlineCacheRoots"),next=new JSONArray();next.put(tree.toString());for(int i=0;i<prev.length();i++)if(!tree.toString().equals(prev.getString(i)))next.put(prev.getString(i));store.settings().put("onlineCacheRoots",next);store.save();
    }
    Doc root(String tree,boolean create) throws Exception{Doc p=Doc.root(context.getContentResolver(),Uri.parse(tree)),root=p.find("YukinaOnlineDownloads");if(root==null||root.find(".yukina-online-cache")==null)throw new IOException("缓存路径不可用，请重新授权目录");Doc chapters=root.find("chapters");return chapters==null&&create?root.create("chapters",true):chapters;}
    static class Cached {Doc folder;JSONObject manifest;Cached(Doc f,JSONObject m){folder=f;manifest=m;}}
    Cached cached(JSONObject volume,boolean complete){JSONArray roots=store.settings().optJSONArray("onlineCacheRoots");for(int i=0;i<roots.length();i++)try{Doc base=root(roots.getString(i),false);if(base==null)continue;Doc folder=base.find(hash(volume.getString("uri")));if(folder==null)continue;Doc file=folder.find("chapter.json");if(file==null)continue;JSONObject m=new JSONObject(new String(file.read(),"UTF-8"));if(!volume.getString("uri").equals(m.optString("path"))||complete&&!m.optBoolean("complete"))continue;JSONArray pages=m.optJSONArray("pages");if(pages==null||pages.length()==0||pages.length()>10000)continue;boolean valid=true;for(int j=0;j<pages.length();j++)if(!String.format(Locale.ROOT,"%06d.img",j+1).equals(pages.getJSONObject(j).optString("file")))valid=false;if(valid)return new Cached(folder,m);}catch(Exception ignored){}return null;}
    byte[] cachedPage(Cached cached,int index) throws Exception{JSONObject page=cached.manifest.getJSONArray("pages").getJSONObject(index);Doc f=cached.folder.find(page.getString("file"));if(f==null)throw new IOException("离线页面缺失，请重新下载章节");byte[] data=f.read();if(!digest(data).equals(page.getString("sha256")))throw new IOException("离线页面校验失败，请重新下载章节");return data;}
    static String bookPath(JSONObject volume){String uri=volume.optString("uri");int slash=uri.lastIndexOf('/');return slash>"online://".length()?uri.substring(0,slash):uri;}
    interface Progress {void update(String title,int page,int total);}
    void download(JSONObject volume,AtomicBoolean cancel,Progress progress) throws Exception{
        JSONArray roots=store.settings().getJSONArray("onlineCacheRoots");if(roots.length()==0)throw new IOException("请先选择独立下载路径");Doc base=root(roots.getString(0),true),folder=base.create(hash(volume.getString("uri")),true);JSONObject meta=volume.getJSONObject("online"),s=source(meta.getString("source_id"));List<String> urls=pages(s,meta);Cached previous=cached(volume,false);Map<String,Integer> old=new HashMap<>();if(previous!=null&&previous.folder.uri.equals(folder.uri)){JSONArray p=previous.manifest.getJSONArray("pages");for(int i=0;i<p.length();i++)old.put(pageIdentity(s,p.getJSONObject(i).getString("url")),i);}
        JSONObject manifest=new JSONObject().put("version",1).put("path",volume.getString("uri")).put("title",volume.optString("title")).put("book_title",volume.optString("_bookTitle")).put("book_path",bookPath(volume)).put("complete",false).put("pages",new JSONArray());
        for(int i=0;i<urls.size();i++){if(cancel.get())throw new IOException("下载已暂停，可继续");String name=String.format(Locale.ROOT,"%06d.img",i+1),url=urls.get(i);byte[] data=null;Integer prior=old.get(pageIdentity(s,url));if(prior!=null&&prior==i)try{data=cachedPage(previous,prior);}catch(Exception ignored){}
            if(data==null){data=pageBytes(s,meta,urls,i);url=urls.get(i);Bitmap check=Books.image(data,240);check.recycle();folder.create(name,false).write(data);}manifest.getJSONArray("pages").put(new JSONObject().put("file",name).put("url",url).put("sha256",digest(data)).put("size",data.length));folder.create("chapter.json",false).write(manifest.toString().getBytes("UTF-8"));progress.update(volume.optString("title"),i+1,urls.size());
        }manifest.put("complete",true);folder.create("chapter.json",false).write(manifest.toString().getBytes("UTF-8"));
    }
    void clearCache(JSONObject volume) throws Exception{JSONArray roots=store.settings().getJSONArray("onlineCacheRoots");for(int i=0;i<roots.length();i++){Doc base=root(roots.getString(i),false);if(base==null)continue;Doc folder=base.find(hash(volume.getString("uri")));if(folder==null)continue;Doc file=folder.find("chapter.json");if(file==null)continue;JSONObject m=new JSONObject(new String(file.read(),"UTF-8"));if(!volume.getString("uri").equals(m.optString("path")))continue;JSONArray pages=m.optJSONArray("pages");if(pages!=null)for(int j=0;j<pages.length();j++){String name=pages.getJSONObject(j).optString("file");if(!name.matches("[0-9]{6}\\.img"))continue;Doc f=folder.find(name);if(f!=null)DocumentsContract.deleteDocument(context.getContentResolver(),f.uri);}DocumentsContract.deleteDocument(context.getContentResolver(),file.uri);}}
    List<JSONObject> knownCachedVolumes()throws Exception{Map<String,JSONObject> found=new LinkedHashMap<>();JSONArray roots=store.settings().getJSONArray("onlineCacheRoots");for(int i=0;i<roots.length();i++){
        Doc base;try{base=root(roots.getString(i),false);}catch(Exception ignored){continue;}if(base==null)continue;Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(base.tree,DocumentsContract.getDocumentId(base.uri));try(Cursor cursor=context.getContentResolver().query(children,new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME},null,null,null)){while(cursor!=null&&cursor.moveToNext()){
            String name=cursor.getString(1);if(!name.matches("[0-9a-f]{64}"))continue;try{Doc folder=new Doc(context.getContentResolver(),base.tree,DocumentsContract.buildDocumentUriUsingTree(base.tree,cursor.getString(0))),file=folder.find("chapter.json");if(file==null)continue;JSONObject m=new JSONObject(new String(file.read(),"UTF-8"));String uri=m.optString("path");if(uri.startsWith("online://")&&hash(uri).equals(name))found.put(uri,new JSONObject().put("uri",uri).put("title",m.optString("title")).put("book_title",m.optString("book_title")).put("book_path",m.optString("book_path")).put("complete",m.optBoolean("complete")));}catch(Exception ignored){}
        }}}
        return new ArrayList<>(found.values());
    }
    final class Engine implements Books.Engine {
        final JSONObject volume,source;final List<String> urls;final Cached cache;final String quality,key;
        volatile boolean closed;
        Engine(JSONObject v) throws Exception{
            volume=v;quality=store.settings().optString("onlineQuality","smooth");cache=cached(v,true);
            if(cache!=null){source=null;key=hash(v.getString("uri")+"/offline/"+cache.manifest.toString());urls=new ArrayList<>();JSONArray p=cache.manifest.getJSONArray("pages");for(int i=0;i<p.length();i++)urls.add(p.getJSONObject(i).getString("url"));}
            else{JSONObject m=v.getJSONObject("online"),configured=source(m.getString("source_id"));source=new JSONObject(configured.toString()).put("_quality",quality);String mode=configured.optString("type").equals("mangadex")&&!quality.equals("original")?"saver":"original";key=hash(v.getString("uri")+configured.toString()+mode);byte[] data=manifestMemory.load(key,()->{List<String> loaded=pages(source,m);JSONArray arr=new JSONArray();for(String url:loaded)arr.put(url);return arr.toString().getBytes("UTF-8");},300000);JSONArray arr=new JSONArray(new String(data,"UTF-8"));urls=new ArrayList<>();for(int i=0;i<arr.length();i++)urls.add(arr.getString(i));}
        }
        public int count(){return urls.size();}
        public Bitmap render(int page,int width)throws Exception{
            if(closed)throw new IOException("章节已关闭");String rawKey="raw/"+key+"/"+page;
            String preparedKey="image/"+quality+"/"+key+"/"+page;try{byte[] prepared=pageMemory.load(preparedKey,()->{byte[] raw=pageMemory.load(rawKey,()->{byte[] original=pageMemory.get("image/original/"+key+"/"+page);if(original!=null)return original;return cache!=null?cachedPage(cache,page):pageBytes(source,volume.getJSONObject("online"),urls,page);});return OnlineQuality.prepare(raw,quality);});
            if(closed)throw new IOException("章节已关闭");return OnlineQuality.decode(prepared,"original");}catch(Exception e){pageMemory.remove(rawKey);pageMemory.remove(preparedKey);throw e;}
        }
        public void close(){closed=true;}
    }
}
