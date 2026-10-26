package cn.migi.reader;
import java.util.*;
import java.util.concurrent.*;

/** RAM only. Pure Java so budgets/coalescing can be verified on the host JVM. */
final class OnlineMemory {
    interface Loader {byte[] load()throws Exception;}
    static final class Entry {final byte[] bytes;final long expires;Entry(byte[] b,long t){bytes=b;expires=t;}}
    final long limit;long used;final LinkedHashMap<String,Entry> values=new LinkedHashMap<>(16,.75f,true);
    final ConcurrentHashMap<String,FutureTask<byte[]>> flights=new ConcurrentHashMap<>();
    OnlineMemory(long bytes){limit=bytes;}
    synchronized byte[] get(String key){Entry e=values.get(key);if(e==null)return null;if(e.expires>0&&System.currentTimeMillis()>e.expires){values.remove(key);used-=e.bytes.length;return null;}return e.bytes;}
    synchronized void put(String key,byte[] value,long ttl){Entry old=values.remove(key);if(old!=null)used-=old.bytes.length;if(value.length>limit)return;values.put(key,new Entry(value,ttl>0?System.currentTimeMillis()+ttl:0));used+=value.length;Iterator<Entry> it=values.values().iterator();while(used>limit){used-=it.next().bytes.length;it.remove();}}
    byte[] load(String key,Loader loader)throws Exception{return load(key,loader,0);}
    byte[] load(String key,Loader loader,long ttl)throws Exception{byte[] ready=get(key);if(ready!=null)return ready;FutureTask<byte[]> task=new FutureTask<>(()->{byte[] again=get(key);if(again!=null)return again;byte[] result=loader.load();put(key,result,ttl);return result;});FutureTask<byte[]> other=flights.putIfAbsent(key,task);if(other==null){try{task.run();return task.get();}catch(ExecutionException e){Throwable cause=e.getCause();if(cause instanceof Exception)throw (Exception)cause;throw new RuntimeException(cause);}finally{flights.remove(key,task);}}try{return other.get();}catch(ExecutionException e){Throwable cause=e.getCause();if(cause instanceof Exception)throw (Exception)cause;throw new RuntimeException(cause);}}
    synchronized void clear(){values.clear();used=0;}
    synchronized void remove(String key){Entry old=values.remove(key);if(old!=null)used-=old.bytes.length;}
    static int[] profile(String quality,int bytes,long pixels){if(quality.equals("original"))return new int[]{0,100};if(quality.equals("low"))return new int[]{1280,65};return bytes>4*1024*1024||pixels>12000000?new int[]{1600,78}:new int[]{2000,85};}
}
