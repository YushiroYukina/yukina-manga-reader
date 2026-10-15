package cn.migi.reader;

import android.content.Context;
import android.animation.ValueAnimator;
import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.graphics.*;
import android.view.*;
import android.view.animation.AccelerateDecelerateInterpolator;
import java.util.*;

/** Full-size reading canvas. Controls are siblings, never layout children here. */
public final class ReaderSurface extends View {
    public interface Listener {void turn(int step);void center();default boolean preview(int step,long request){return false;}default void commitPreview(int step){turn(step);}}
    public Listener listener; public boolean rtl=true;public int gap=16; public String effect="book";
    private List<Bitmap> pages=new ArrayList<>(),old=new ArrayList<>();
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
    private ValueAnimator animation; private float progress=1,zoom=1,panX=0,panY=0;private int side;
    private float downX,downY;private boolean dragEligible,dragTurned;
    private boolean dragging,settling,released,commitRequested;private int dragStep,dragSign;private long previewRequest;
    private final GestureDetector gestures;private final ScaleGestureDetector scaling;
    public ReaderSurface(Context context) {
        super(context);setBackgroundColor(Color.rgb(16,20,22));setFocusable(true);
        scaling=new ScaleGestureDetector(context,new ScaleGestureDetector.SimpleOnScaleGestureListener(){
            public boolean onScale(ScaleGestureDetector detector){zoom=Math.max(1,Math.min(3,zoom*detector.getScaleFactor()));clampPan();invalidate();return true;}
        });
        gestures=new GestureDetector(context,new GestureDetector.SimpleOnGestureListener(){
            public boolean onDown(MotionEvent e){return true;}
            public boolean onSingleTapConfirmed(MotionEvent e){if(listener!=null){int r=Core.region(e.getX(),getWidth());if(r==0)listener.center();else listener.turn((r<0)==rtl?1:-1);}return true;}
            public boolean onDoubleTap(MotionEvent e){zoom=zoom>1?1:2;panX=panY=0;invalidate();return true;}
            public boolean onScroll(MotionEvent e1,MotionEvent e2,float dx,float dy){if(zoom>1&&!scaling.isInProgress()){panX-=dx;panY-=dy;clampPan();invalidate();}return true;}

        });
    }
    private void clampPan(){float x=getWidth()*(zoom-1)/2,y=getHeight()*(zoom-1)/2;panX=Math.max(-x,Math.min(x,panX));panY=Math.max(-y,Math.min(y,panY));}
    public boolean isInteracting(){return dragging||settling;}
    public boolean onTouchEvent(MotionEvent event){
        int action=event.getActionMasked();
        if(action==MotionEvent.ACTION_DOWN){
            if(isInteracting())return true;
            finish();downX=event.getX();downY=event.getY();dragEligible=zoom==1&&Core.region(downX,getWidth())!=0;dragTurned=false;
        }
        if(settling)return true;
        if(action==MotionEvent.ACTION_POINTER_DOWN||action==MotionEvent.ACTION_CANCEL){dragEligible=false;if(dragging)releaseDrag(false);}
        scaling.onTouchEvent(event);if(scaling.isInProgress()||zoom>1)dragEligible=false;
        float dx=event.getX()-downX,dy=event.getY()-downY;
        if(action==MotionEvent.ACTION_MOVE&&dragEligible&&!dragging&&!dragTurned&&event.getPointerCount()==1&&Math.abs(dx)>ViewConfiguration.get(getContext()).getScaledTouchSlop()&&Math.abs(dx)>Math.abs(dy)*1.3f){
            dragSign=dx>0?1:-1;dragStep=(dx>0)==rtl?1:-1;
            long request=++previewRequest;
            if(listener!=null&&listener.preview(dragStep,request)){
                dragging=true;released=false;commitRequested=false;side=-dragSign;old=pages;pages=new ArrayList<>();progress=0;
            }else dragEligible=false;
            dragTurned=true;MotionEvent cancel=MotionEvent.obtain(event);cancel.setAction(MotionEvent.ACTION_CANCEL);gestures.onTouchEvent(cancel);cancel.recycle();
        }
        if(dragging&&!released){
            progress=Math.max(0,Math.min(.98f,dx*dragSign/Math.max(1,getWidth())));invalidate();
            if(action==MotionEvent.ACTION_UP){boolean crossed=dragSign>0?downX<getWidth()/2f&&event.getX()>getWidth()/2f:downX>getWidth()/2f&&event.getX()<getWidth()/2f;releaseDrag(crossed&&Math.abs(dx)>Math.abs(dy)*1.3f);}
        }
        if(!dragTurned&&!dragging)gestures.onTouchEvent(event);
        return true;
    }
    public void supplyPreview(long request,List<Bitmap> images){
        if(request!=previewRequest||!dragging){recycle(images);return;}
        pages=new ArrayList<>(images);invalidate();if(released)settleDrag(commitRequested);
    }
    public void previewFailed(long request){if(request==previewRequest&&dragging){released=true;settleDrag(false);}}
    private void releaseDrag(boolean commit){
        released=true;commitRequested=commit;
        if(!commit||!pages.isEmpty())settleDrag(commit);
    }
    private void settleDrag(boolean commit){
        if(settling)return;settling=true;float end=commit?1:0;
        animation=ValueAnimator.ofFloat(progress,end);animation.setDuration(Math.max(100,(long)(260*Math.abs(end-progress))));animation.setInterpolator(new AccelerateDecelerateInterpolator());
        animation.addUpdateListener(a->{progress=(float)a.getAnimatedValue();invalidate();});
        animation.addListener(new AnimatorListenerAdapter(){boolean cancelled;public void onAnimationCancel(Animator a){cancelled=true;}public void onAnimationEnd(Animator a){if(cancelled)return;
            animation=null;dragging=settling=false;released=false;
            if(commit){recycle(old);}else{List<Bitmap> preview=pages;pages=old;old=new ArrayList<>();recycle(preview);}
            progress=1;invalidate();if(commit&&listener!=null)listener.commitPreview(dragStep);
        }});animation.start();
    }
    private void recycle(List<Bitmap> list){for(Bitmap b:list)if(!b.isRecycled()&&!pages.contains(b))b.recycle();list.clear();}
    public void setPages(List<Bitmap> images,int direction,boolean animate) {
        finish();old=pages;pages=new ArrayList<>(images);panX=panY=0;
        if(!animate||old.isEmpty()||effect.equals("none")){recycle(old);progress=1;invalidate();return;}
        side=(direction>0)==rtl?-1:1;progress=0;
        animation=ValueAnimator.ofFloat(0,1);animation.setDuration(360);animation.setInterpolator(t->t<.5f?4*t*t*t:1-(float)Math.pow(-2*t+2,3)/2);
        animation.addUpdateListener(a->{progress=(float)a.getAnimatedValue();invalidate();if(progress>=1)recycle(old);});animation.start();
    }
    public void finish(){if(animation!=null){animation.cancel();animation=null;}if(dragging){List<Bitmap> preview=pages;pages=old;old=new ArrayList<>();recycle(preview);}dragging=settling=released=false;++previewRequest;recycle(old);progress=1;}
    public void clear(){finish();List<Bitmap> previous=pages;pages=new ArrayList<>();recycle(previous);invalidate();}
    private void drawPages(Canvas canvas,List<Bitmap> images) {
        if(images.isEmpty())return;
        float sum=0,max=1;for(Bitmap b:images){sum+=b.getWidth();max=Math.max(max,b.getHeight());}
        float margin=12*getResources().getDisplayMetrics().density,gutter=gap*getResources().getDisplayMetrics().density*(images.size()-1);
        float factor=Math.min((getWidth()-2*margin-gutter)/sum,(getHeight()-2*margin)/max);
        float x=(getWidth()-(sum*factor+gutter))/2;
        for(int i=0;i<images.size();i++) {
            Bitmap b=images.get(rtl?images.size()-1-i:i);float width=b.getWidth()*factor,height=b.getHeight()*factor;
            paint.setAlpha(255);canvas.drawBitmap(b,null,new RectF(x,(getHeight()-height)/2,x+width,(getHeight()+height)/2),paint);
            x+=width+gap*getResources().getDisplayMetrics().density;
        }
    }
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);canvas.save();canvas.translate(panX,panY);canvas.scale(zoom,zoom,getWidth()/2f,getHeight()/2f);
        if(old.isEmpty()||progress>=1)drawPages(canvas,pages);
        else if(effect.equals("slide")||effect.equals("none")) {
            canvas.save();canvas.translate(-side*getWidth()*progress,0);drawPages(canvas,old);canvas.restore();
            canvas.save();canvas.translate(side*getWidth()*(1-progress),0);drawPages(canvas,pages);canvas.restore();
        } else if(effect.equals("cover")) {
            drawPages(canvas,old);canvas.save();canvas.translate(side*getWidth()*(1-progress),0);drawPages(canvas,pages);canvas.restore();
        } else if(effect.equals("fade")) {
            drawPages(canvas,old);int layer=canvas.saveLayerAlpha(0,0,getWidth(),getHeight(),(int)(255*progress));drawPages(canvas,pages);canvas.restoreToCount(layer);
        } else {
            drawBook(canvas);

        }
        canvas.restore();
    }
    private RectF pageBounds(List<Bitmap> images){
        float sum=0,max=1;for(Bitmap b:images){sum+=b.getWidth();max=Math.max(max,b.getHeight());}
        float margin=12*getResources().getDisplayMetrics().density,gutter=gap*getResources().getDisplayMetrics().density*(images.size()-1);
        float scale=Math.min((getWidth()-2*margin-gutter)/sum,(getHeight()-2*margin)/max),w=sum*scale+gutter,h=max*scale;
        return new RectF((getWidth()-w)/2,(getHeight()-h)/2,(getWidth()+w)/2,(getHeight()+h)/2);
    }
    private void drawBook(Canvas canvas){
        drawPages(canvas,pages);RectF r=pageBounds(old);float t=progress,sine=(float)Math.sin(Math.PI*t);
        boolean single=old.size()==1;float hinge=single?(side<0?r.right:r.left):r.centerX();
        RectF source=single?new RectF(r):new RectF(side<0?r.left:hinge,r.top,side<0?hinge:r.right,r.bottom);
        RectF target=single?new RectF(r):new RectF(side<0?hinge:r.left,r.top,side<0?r.right:hinge,r.bottom);
        if(!single){canvas.save();canvas.clipRect(target);drawPages(canvas,old);canvas.restore();}
        float extent=(single?r.width():r.width()/2)*(float)Math.cos(Math.PI*t/(single?2:1))*side;
        float lift=sine*Math.min((single?40:52)*getResources().getDisplayMetrics().density,r.height()*(single?.05f:.07f));
        float edge=hinge+extent,left=Math.min(hinge,edge),right=Math.max(hinge,edge),shadow=32*getResources().getDisplayMetrics().density;
        paint.setAlpha(255);paint.setShader(new LinearGradient(edge-shadow,0,edge+shadow,0,new int[]{Color.TRANSPARENT,Color.argb((int)(110*sine),0,0,0),Color.TRANSPARENT},null,Shader.TileMode.CLAMP));canvas.drawRect(edge-shadow,r.top,edge+shadow,r.bottom,paint);paint.setShader(null);
        if(Math.abs(extent)<.7f)return;
        float[] quad={left,r.top-(edge<hinge?lift:0),right,r.top-(edge>hinge?lift:0),right,r.bottom+(edge>hinge?lift:0),left,r.bottom+(edge<hinge?lift:0)};
        RectF sample=single||t<.5f?source:target;List<Bitmap> image=single||t<.5f?old:pages;
        float[] src={sample.left,sample.top,sample.right,sample.top,sample.right,sample.bottom,sample.left,sample.bottom};Matrix matrix=new Matrix();
        if(matrix.setPolyToPoly(src,0,quad,0,4)){canvas.save();canvas.concat(matrix);canvas.clipRect(sample);drawPages(canvas,image);canvas.restore();}
        Path path=new Path();path.moveTo(quad[0],quad[1]);for(int i=2;i<8;i+=2)path.lineTo(quad[i],quad[i+1]);path.close();
        int dark=(int)(single?t*95:100*sine);paint.setShader(new LinearGradient(left,0,right,0,new int[]{Color.argb(edge<hinge?dark:0,0,0,0),Color.argb((int)(28*sine),255,255,255),Color.argb(edge>hinge?dark:0,0,0,0)},new float[]{0,.75f,1},Shader.TileMode.CLAMP));canvas.drawPath(path,paint);paint.setShader(null);
    }
    protected void onSizeChanged(int w,int h,int ow,int oh){super.onSizeChanged(w,h,ow,oh);finish();clampPan();}
}
