package cn.migi.reader;
import android.graphics.*;
import java.io.*;

final class OnlineQuality {
    static Bitmap decode(byte[] data,String quality)throws Exception{
        BitmapFactory.Options o=new BitmapFactory.Options();o.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(data,0,data.length,o);
        if(o.outWidth<=0||o.outHeight<=0||(long)o.outWidth*o.outHeight>120000000)throw new IOException("图片无效或尺寸过大");
        if(quality.equals("original")&&(long)o.outWidth*o.outHeight*4>Math.min(128L*1024*1024,Runtime.getRuntime().maxMemory()/4))throw new IOException("原图超出当前可用解码预算，请改用流畅或低画质");
        int edge=OnlineMemory.profile(quality,data.length,(long)o.outWidth*o.outHeight)[0];o.inJustDecodeBounds=false;o.inPreferredConfig=Bitmap.Config.ARGB_8888;o.inSampleSize=1;
        if(edge>0)while(Math.max(o.outWidth,o.outHeight)/o.inSampleSize>edge*2)o.inSampleSize*=2;
        Bitmap bitmap=BitmapFactory.decodeByteArray(data,0,data.length,o);if(bitmap==null)throw new IOException("图片解码失败");
        if(edge>0&&Math.max(bitmap.getWidth(),bitmap.getHeight())>edge){float ratio=edge/(float)Math.max(bitmap.getWidth(),bitmap.getHeight());Bitmap fitted=Bitmap.createScaledBitmap(bitmap,Math.max(1,Math.round(bitmap.getWidth()*ratio)),Math.max(1,Math.round(bitmap.getHeight()*ratio)),true);if(fitted!=bitmap)bitmap.recycle();bitmap=fitted;}
        return bitmap;
    }
    static byte[] prepare(byte[] raw,String quality)throws Exception{
        if(quality.equals("original"))return raw;
        BitmapFactory.Options bounds=new BitmapFactory.Options();bounds.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(raw,0,raw.length,bounds);int qualityValue=OnlineMemory.profile(quality,raw.length,(long)bounds.outWidth*bounds.outHeight)[1];
        Bitmap bitmap=decode(raw,quality);try{
            if(bitmap.hasAlpha()){Bitmap opaque=Bitmap.createBitmap(bitmap.getWidth(),bitmap.getHeight(),Bitmap.Config.ARGB_8888);Canvas c=new Canvas(opaque);c.drawColor(Color.WHITE);c.drawBitmap(bitmap,0,0,null);bitmap.recycle();bitmap=opaque;}
            ByteArrayOutputStream out=new ByteArrayOutputStream();if(!bitmap.compress(Bitmap.CompressFormat.JPEG,qualityValue,out))throw new IOException("图片压缩失败");byte[] packed=out.toByteArray();if(bitmap.getWidth()==bounds.outWidth&&bitmap.getHeight()==bounds.outHeight&&packed.length>=raw.length)return raw;return packed;
        }finally{bitmap.recycle();}
    }
}
