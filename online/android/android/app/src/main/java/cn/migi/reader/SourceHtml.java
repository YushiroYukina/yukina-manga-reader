package cn.migi.reader;

import org.json.*;
import java.net.*;
import java.io.*;
import java.util.*;
import java.util.regex.*;

/** Fixed HTML adapters; never executes website JavaScript. Endpoint references:
 * Keiyoushi MangaPill / Manhuagui (Apache-2.0); LZ format: lz-string (MIT).
 * Original bounded parser/decoder implementation, AGPL-3.0-only. */
final class SourceHtml {
    static boolean handles(String type){return type.equals("mangapill")||type.equals("manhuagui");}
    static String entity(String raw){
        Matcher m=Pattern.compile("&(#x[0-9a-fA-F]+|#[0-9]+|amp|quot|apos|lt|gt|nbsp);").matcher(raw);StringBuffer out=new StringBuffer();
        while(m.find()){String v=m.group(1),r;try{r=v.startsWith("#")?new String(Character.toChars(Integer.parseInt(v.substring(v.startsWith("#x")?2:1),v.startsWith("#x")?16:10))):v.equals("amp")?"&":v.equals("quot")?"\"":v.equals("apos")?"'":v.equals("lt")?"<":v.equals("gt")?">":" ";}catch(Exception e){r=m.group();}m.appendReplacement(out,Matcher.quoteReplacement(r));}m.appendTail(out);return out.toString();
    }
    static Map<String,String> attrs(String tag){Map<String,String> out=new HashMap<>();Matcher m=Pattern.compile("([\\w:-]+)\\s*=\\s*(?:\"([^\"]*)\"|'([^']*)'|([^\\s>]+))").matcher(tag);while(m.find())out.put(m.group(1).toLowerCase(Locale.ROOT),entity(m.group(2)!=null?m.group(2):m.group(3)!=null?m.group(3):m.group(4)));return out;}
    static String text(String raw){return entity(raw.replaceAll("(?s)<[^>]*>"," ")).replaceAll("\\s+"," ").trim();}
    static class Anchor {Map<String,String> a;String text,cover;Anchor(Map<String,String> x,String inner){a=x;text=x.getOrDefault("title",SourceHtml.text(inner));Matcher im=Pattern.compile("(?is)<img\\b([^>]+)>").matcher(inner);cover="";if(im.find()){Map<String,String> at=attrs(im.group(1));cover=at.getOrDefault("data-src",at.getOrDefault("data-original",at.getOrDefault("src","")));}}}
    static List<Anchor> anchors(String raw){List<Anchor> out=new ArrayList<>();Matcher m=Pattern.compile("(?is)<a\\b([^>]*)>(.*?)</a\\s*>").matcher(raw);while(m.find()){Anchor a=new Anchor(attrs(m.group(1)),m.group(2));a.a.put("_position",String.valueOf(m.start()));out.add(a);}return out;}
    static String get(JSONObject s,String path)throws Exception{byte[] data=Online.fetch(s,new URL(Online.checked(Online.base(s)+"/"),path).toString(),8*1024*1024);String header=new String(data,0,Math.min(data.length,4096),"US-ASCII").toLowerCase(Locale.ROOT);return new String(data,header.matches("(?s).*charset\\s*=\\s*[\"']?(gbk|gb2312|gb18030).*" )?"GB18030":"UTF-8");}
    static String local(JSONObject s,String href)throws Exception{URL root=Online.checked(Online.base(s));try{URL url=new URL(root,entity(href));return Online.same(root,url)?url.getPath():"";}catch(MalformedURLException ignored){return "";}}
    static Online.Result search(JSONObject s,String term,int page)throws Exception{
        boolean mp=s.getString("type").equals("mangapill");String path=mp?"/search?q="+Online.enc(term)+"&page="+page:term.isEmpty()?"/list/view_p"+page+".html":"/s/"+Online.enc(term).replace("+","%20")+"_p"+page+".html";
        Map<String,JSONObject> rows=new LinkedHashMap<>();Online.Result result=new Online.Result();
        for(Anchor a:anchors(get(s,path))){String id=local(s,a.a.getOrDefault("href",""));if(id.matches(mp?"/manga/[0-9]+/[^/]+":"/comic/[0-9]+/")){
            JSONObject item=rows.get(id);if(item==null){item=Online.item(id,"","");rows.put(id,item);}if(!a.text.isEmpty()&&(item.optString("title").isEmpty()||a.a.getOrDefault("class","").contains("bcover")))item.put("title",a.text);if(!a.cover.isEmpty())item.put("cover",new URL(Online.checked(Online.base(s)),a.cover).toString());
        }String href=entity(a.a.getOrDefault("href",""));if(mp&&id.equals("/search")&&Pattern.compile("[?&]page="+(page+1)+"(?:&|$)").matcher(href).find()||!mp&&id.endsWith("_p"+(page+1)+".html"))result.more=true;}
        for(JSONObject b:rows.values())if(!b.optString("title").isEmpty())result.books.put(b);return result;
    }
    static JSONArray chapters(JSONObject s,String book)throws Exception{
        boolean mp=s.getString("type").equals("mangapill");Matcher valid=Pattern.compile(mp?"/manga/([0-9]+)/[^/]+":"/comic/([0-9]+)/").matcher(book);if(!valid.matches())throw new IOException("作品地址无效");String pattern=mp?"/chapters/"+valid.group(1)+"-[^/]+/[^/]+":Pattern.quote(book)+"[0-9]+\\.html";
        String raw=get(s,book);List<Integer> groups=new ArrayList<>();Matcher marker=Pattern.compile("(?is)<div\\b[^>]*\\bid\\s*=\\s*['\"]chapter-list-[^'\"]+['\"]").matcher(raw);while(marker.find())groups.add(marker.start());
        List<JSONObject> rows=new ArrayList<>();Set<String> seen=new HashSet<>();for(Anchor a:anchors(raw)){String id=local(s,a.a.getOrDefault("href",""));if(id.matches(pattern)&&(mp||Arrays.asList(a.a.getOrDefault("class","").split("\\s+")).contains("status0"))&&seen.add(id)){int group=0;for(int position:groups)if(position<Integer.parseInt(a.a.get("_position")))group++;rows.add(new JSONObject().put("id",id).put("title",a.text).put("_group",group));}}
        if(mp)Collections.reverse(rows);else rows.sort((a,b)->a.optInt("_group")==b.optInt("_group")?Double.compare(chapterNumber(a.optString("title")),chapterNumber(b.optString("title"))):Integer.compare(a.optInt("_group"),b.optInt("_group")));JSONArray out=new JSONArray();for(JSONObject r:rows){r.remove("_group");out.put(r);}return out;
    }
    static double chapterNumber(String title){Matcher m=Pattern.compile("[0-9]+(?:\\.[0-9]+)?").matcher(title);return m.find()?Double.parseDouble(m.group()):1e10;}
    static List<String> pages(JSONObject s,JSONObject chapter)throws Exception{
        String id=chapter.getString("id");if(!id.matches("/chapters/[^/]+/[^/]+|/comic/[0-9]+/[0-9]+\\.html"))throw new IOException("章节地址无效");String raw=get(s,id);List<String> pages=new ArrayList<>();
        if(s.getString("type").equals("mangapill")){Matcher pictures=Pattern.compile("(?is)<picture\\b[^>]*>(.*?)</picture\\s*>").matcher(raw);while(pictures.find()){Matcher images=Pattern.compile("(?is)<img\\b([^>]+)>").matcher(pictures.group(1));while(images.find()){Map<String,String> a=attrs(images.group(1));String url=a.getOrDefault("data-src",a.getOrDefault("src",""));if(!url.isEmpty())pages.add(new URL(Online.checked(Online.base(s)),url).toString());}}}
        else{JSONObject meta=unpack(raw),signature=meta.optJSONObject("sl");String query="";if(signature!=null)for(String key:new String[]{"e","m"})if(signature.has(key))query+=(query.isEmpty()?"?":"&")+key+"="+Online.enc(signature.get(key));JSONArray files=meta.getJSONArray("files");for(int i=0;i<files.length();i++)pages.add("https://i.hamreus.com"+meta.getString("path")+Online.enc(files.getString(i)).replace("%2F","/").replace("+","%20")+query);}
        return pages;
    }
    static String literal(String raw)throws Exception{StringBuilder out=new StringBuilder();for(int i=1;i<raw.length()-1;i++){char c=raw.charAt(i);if(c!='\\'){out.append(c);continue;}if(++i>=raw.length()-1)throw new IOException("字符串转义不完整");c=raw.charAt(i);if(c=='x'||c=='u'){int n=c=='x'?2:4;if(i+n>=raw.length())throw new IOException("字符串转义不完整");out.append((char)Integer.parseInt(raw.substring(i+1,i+1+n),16));i+=n;}else out.append(c=='n'?'\n':c=='r'?'\r':c=='t'?'\t':c);}return out.toString();}
    static JSONObject unpack(String raw)throws Exception{
        String str="'((?:\\\\.|[^'\\\\])*)'";Matcher m=Pattern.compile("\\}\\s*\\(\\s*("+str+")\\s*,\\s*([0-9]+)\\s*,\\s*([0-9]+)\\s*,\\s*("+str+")").matcher(raw);
        if(!m.find())throw new IOException("未找到公开图片清单，章节可能不可用");String payload=literal(m.group(1)),symbols=literal(m.group(5));int radix=Integer.parseInt(m.group(3)),count=Integer.parseInt(m.group(4));if(radix<2||radix>62||count>10000)throw new IOException("图片清单字典超出范围");if(raw.substring(m.end()).trim().startsWith("["))symbols=lz(symbols);
        String[] words=symbols.split("\\|",-1);Map<String,String> table=new HashMap<>();String digits="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";for(int i=0;i<Math.min(count,words.length);i++){int n=i;String key="";do{key=digits.charAt(n%radix)+key;n/=radix;}while(n>0);if(!words[i].isEmpty())table.put(key,words[i]);}
        Matcher token=Pattern.compile("\\b[0-9A-Za-z]+\\b").matcher(payload);StringBuffer decoded=new StringBuffer();while(token.find())token.appendReplacement(decoded,Matcher.quoteReplacement(table.getOrDefault(token.group(),token.group())));token.appendTail(decoded);int start=decoded.indexOf("{");if(start<0)throw new IOException("图片清单缺少数据");JSONObject result=(JSONObject)new JSONTokener(decoded.substring(start)).nextValue();result.getJSONArray("files");result.getString("path");return result;
    }
    static final class Bits {final String data;int index,mask=32;Bits(String s){data=s;}int read(int n)throws Exception{int out=0;String alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";for(int shift=0;shift<n;shift++){if(index>=data.length())throw new IOException("压缩图片清单不完整");int value=alphabet.indexOf(data.charAt(index));if(value<0)throw new IOException("压缩字符无效");if((value&mask)!=0)out|=1<<shift;mask>>=1;if(mask==0){mask=32;index++;}}return out;}}
    static String lz(String value)throws Exception{Bits bits=new Bits(value);int lead=bits.read(2);if(lead==2)return "";if(lead>1)throw new IOException("压缩格式无效");String previous=String.valueOf((char)bits.read(lead==0?8:16));List<String> dict=new ArrayList<>(Arrays.asList("","","",previous));StringBuilder result=new StringBuilder(previous);int width=3,left=4;while(result.length()<2*1024*1024&&dict.size()<65536){int code=bits.read(width);if(code==2)return result.toString();if(code<2){dict.add(String.valueOf((char)bits.read(code==0?8:16)));code=dict.size()-1;left--;}if(left==0){left=1<<width;width++;}String entry;if(code<dict.size())entry=dict.get(code);else if(code==dict.size())entry=previous+previous.charAt(0);else throw new IOException("图片字典无效");result.append(entry);dict.add(previous+entry.charAt(0));left--;previous=entry;if(left==0){left=1<<width;width++;}}throw new IOException("图片清单解码超过限制");}
}
