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
    public interface Listener {void turn(int step);void center();default boolean preview(int step,long request){return false;}default void commitPreview(int step){turn(step);}default boolean retainSpread(int step,List<Bitmap> images){return false;}default void previewSettled(){}}
    public Listener listener; public boolean rtl=true;public int gap=16; public String effect="book";
    private List<Bitmap> pages=new ArrayList<>(),old=new ArrayList<>();
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
    private int paper=Color.rgb(16,20,22),opacity=255;
    private final RectF destination=new RectF(),bounds=new RectF(),source=new RectF(),target=new RectF();
    private final Matrix projection=new Matrix(),shaderMatrix=new Matrix();
    private final Path leaf=new Path();private final float[] quad=new float[8],corners=new float[8];
    private final LinearGradient shadowGradient=new LinearGradient(0,0,1,0,new int[]{Color.TRANSPARENT,0xff000000,Color.TRANSPARENT},null,Shader.TileMode.CLAMP);
    private final LinearGradient leafGradient=new LinearGradient(0,0,1,0,new int[]{0xff000000,0x38ffffff,0xff000000},new float[]{0,.75f,1},Shader.TileMode.CLAMP);
    private HardwareSpreads hardware;
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
            dragging=true;released=false;commitRequested=false;side=-dragSign;old=pages;pages=new ArrayList<>();progress=0;
            if(listener==null||!listener.preview(dragStep,request)){pages=old;old=new ArrayList<>();dragging=false;progress=1;dragEligible=false;}
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
            List<Bitmap> spare;if(commit){spare=old;old=new ArrayList<>();}else{spare=pages;pages=old;old=new ArrayList<>();}
            progress=1;invalidate();if(commit&&listener!=null)listener.commitPreview(dragStep);
            if(spare.isEmpty()||listener==null||!listener.retainSpread(commit?-dragStep:dragStep,spare))recycle(spare);
            if(hardware!=null)hardware.trim();
            if(listener!=null)listener.previewSettled();
        }});animation.start();
    }
    private void recycle(List<Bitmap> list){for(Bitmap b:list)if(!b.isRecycled()&&!pages.contains(b))b.recycle();list.clear();}
    public void setPages(List<Bitmap> images,int direction,boolean animate) {
        finish();old=pages;pages=new ArrayList<>(images);panX=panY=0;
        if(!animate||old.isEmpty()||effect.equals("none")){recycle(old);progress=1;invalidate();return;}
        side=(direction>0)==rtl?-1:1;progress=0;
        animation=ValueAnimator.ofFloat(0,1);animation.setDuration(360);animation.setInterpolator(t->t<.5f?4*t*t*t:1-(float)Math.pow(-2*t+2,3)/2);
        animation.addUpdateListener(a->{progress=(float)a.getAnimatedValue();invalidate();if(progress>=1){recycle(old);if(hardware!=null)hardware.trim();}});animation.start();
    }
    public void finish(){if(animation!=null){animation.cancel();animation=null;}if(dragging){List<Bitmap> preview=pages;pages=old;old=new ArrayList<>();recycle(preview);}dragging=settling=released=false;++previewRequest;recycle(old);if(hardware!=null)hardware.trim();progress=1;}
    public void clear(){finish();List<Bitmap> previous=pages;pages=new ArrayList<>();recycle(previous);if(hardware!=null)hardware.clear();invalidate();}
    public void setBackgroundColor(int color){paper=color;if(hardware!=null)hardware.clear();super.setBackgroundColor(color);}
    private void drawPages(Canvas canvas,List<Bitmap> images) {
        if(images.isEmpty())return;
        float sum=0,max=1;for(Bitmap b:images){sum+=b.getWidth();max=Math.max(max,b.getHeight());}
        float margin=12*getResources().getDisplayMetrics().density,gutter=gap*getResources().getDisplayMetrics().density*(images.size()-1);
        float factor=Math.min((getWidth()-2*margin-gutter)/sum,(getHeight()-2*margin)/max);
        float x=(getWidth()-(sum*factor+gutter))/2;
        for(int i=0;i<images.size();i++) {
            Bitmap b=images.get(rtl?images.size()-1-i:i);float width=b.getWidth()*factor,height=b.getHeight()*factor;
            destination.set(x,(getHeight()-height)/2,x+width,(getHeight()+height)/2);paint.setAlpha(opacity);canvas.drawBitmap(b,null,destination,paint);
            x+=width+gap*getResources().getDisplayMetrics().density;
        }
    }
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);canvas.save();canvas.translate(panX,panY);canvas.scale(zoom,zoom,getWidth()/2f,getHeight()/2f);
        if(old.isEmpty()||progress>=1)drawSpread(canvas,pages);
        else if(effect.equals("slide")||effect.equals("none")) {
            canvas.save();canvas.translate(-side*getWidth()*progress,0);drawSpread(canvas,old);canvas.restore();
            canvas.save();canvas.translate(side*getWidth()*(1-progress),0);drawSpread(canvas,pages);canvas.restore();
        } else if(effect.equals("cover")) {
            // Keep a slower outgoing layer so the cover motion remains distinct from slide.
            canvas.save();canvas.translate(-side*getWidth()*progress*.7f,0);drawSpread(canvas,old);canvas.restore();
            canvas.save();canvas.translate(side*getWidth()*(1-progress),0);drawSpread(canvas,pages);canvas.restore();
        } else if(effect.equals("fade")) {
            drawSpread(canvas,old);opacity=(int)(255*progress);drawSpread(canvas,pages);opacity=255;
        } else {
            drawBook(canvas);

        }
        canvas.restore();
    }
    private void pageBounds(List<Bitmap> images,RectF result){
        float sum=0,max=1;for(Bitmap b:images){sum+=b.getWidth();max=Math.max(max,b.getHeight());}
        float margin=12*getResources().getDisplayMetrics().density,gutter=gap*getResources().getDisplayMetrics().density*(images.size()-1);
        float scale=Math.min((getWidth()-2*margin-gutter)/sum,(getHeight()-2*margin)/max),w=sum*scale+gutter,h=max*scale;
        result.set((getWidth()-w)/2,(getHeight()-h)/2,(getWidth()+w)/2,(getHeight()+h)/2);
    }
    private void drawSpread(Canvas canvas,List<Bitmap> images){if(images.isEmpty())return;if(effect.equals("book")&&android.os.Build.VERSION.SDK_INT>=29&&canvas.isHardwareAccelerated()){if(hardware==null)hardware=new HardwareSpreads();hardware.draw(canvas,images);return;}pageBounds(images,bounds);paint.setColor(paper);paint.setAlpha(opacity);canvas.drawRect(bounds,paint);drawPages(canvas,images);}
    /** Android 10+: rasterize each spread once on the GPU, then transform its layer.
     * Recording uses the same page layout and opaque gutter as the software path. */
    @android.annotation.TargetApi(29)
    private final class HardwareSpreads {
        final RenderNode[] nodes={new RenderNode("spread-a"),new RenderNode("spread-b")};
        final List<?>[] sources=new List<?>[2];int next,width,height,spacing;boolean reverse;
        void clear(){next=0;for(int i=0;i<2;i++){nodes[i].discardDisplayList();sources[i]=null;}}
        void trim(){for(int i=0;i<2;i++)if(sources[i]!=null)for(Object image:sources[i])if(((Bitmap)image).isRecycled()){nodes[i].discardDisplayList();sources[i]=null;break;}}
        void draw(Canvas canvas,List<Bitmap> images){
            if(width!=getWidth()||height!=getHeight()||spacing!=gap||reverse!=rtl){clear();width=getWidth();height=getHeight();spacing=gap;reverse=rtl;}
            int slot=sources[0]!=null&&sources[0].equals(images)?0:sources[1]!=null&&sources[1].equals(images)?1:-1;
            if(slot<0){slot=next;next=1-next;RenderNode node=nodes[slot];node.discardDisplayList();pageBounds(images,bounds);int l=(int)Math.floor(bounds.left),t=(int)Math.floor(bounds.top),r=(int)Math.ceil(bounds.right),b=(int)Math.ceil(bounds.bottom);node.setPosition(l,t,r,b);node.setUseCompositingLayer(true,null);
                Canvas recording=node.beginRecording(Math.max(1,r-l),Math.max(1,b-t));recording.translate(-l,-t);paint.setColor(paper);paint.setAlpha(255);recording.drawRect(bounds,paint);int alpha=opacity;opacity=255;drawPages(recording,images);opacity=alpha;node.endRecording();sources[slot]=new ArrayList<>(images);
            }
            next=1-slot;nodes[slot].setAlpha(opacity/255f);canvas.drawRenderNode(nodes[slot]);
        }
    }
    private void drawBook(Canvas canvas){
        drawSpread(canvas,pages);pageBounds(old,bounds);float l=bounds.left,top=bounds.top,r=bounds.right,bottom=bounds.bottom,w=bounds.width(),h=bounds.height(),t=progress,sine=(float)Math.sin(Math.PI*t);
        boolean single=old.size()==1;float hinge=single?(side<0?r:l):(l+r)/2;
        source.set(single?l:side<0?l:hinge,top,single?r:side<0?hinge:r,bottom);
        target.set(single?l:side<0?hinge:l,top,single?r:side<0?r:hinge,bottom);
        if(!single){canvas.save();canvas.clipRect(target);drawSpread(canvas,old);canvas.restore();}
        float extent=(single?w:w/2)*(float)Math.cos(Math.PI*t/(single?2:1))*side;
        float lift=sine*Math.min((single?40:52)*getResources().getDisplayMetrics().density,h*(single?.05f:.07f));
        float edge=hinge+extent,left=Math.min(hinge,edge),right=Math.max(hinge,edge),shadow=32*getResources().getDisplayMetrics().density;
        shaderMatrix.setScale(shadow*2,1);shaderMatrix.postTranslate(edge-shadow,0);shadowGradient.setLocalMatrix(shaderMatrix);paint.setAlpha((int)(110*sine));paint.setShader(shadowGradient);canvas.drawRect(edge-shadow,top,edge+shadow,bottom,paint);paint.setShader(null);
        if(Math.abs(extent)<.7f)return;
        quad[0]=left;quad[1]=top-(edge<hinge?lift:0);quad[2]=right;quad[3]=top-(edge>hinge?lift:0);quad[4]=right;quad[5]=bottom+(edge>hinge?lift:0);quad[6]=left;quad[7]=bottom+(edge<hinge?lift:0);
        RectF sample=single||t<.5f?source:target;List<Bitmap> image=single||t<.5f?old:pages;
        corners[0]=sample.left;corners[1]=sample.top;corners[2]=sample.right;corners[3]=sample.top;corners[4]=sample.right;corners[5]=sample.bottom;corners[6]=sample.left;corners[7]=sample.bottom;
        if(projection.setPolyToPoly(corners,0,quad,0,4)){canvas.save();canvas.concat(projection);canvas.clipRect(sample);drawSpread(canvas,image);canvas.restore();}
        leaf.rewind();leaf.moveTo(quad[0],quad[1]);for(int i=2;i<8;i+=2)leaf.lineTo(quad[i],quad[i+1]);leaf.close();
        shaderMatrix.setScale(right-left,1);shaderMatrix.postTranslate(left,0);leafGradient.setLocalMatrix(shaderMatrix);paint.setAlpha((int)(single?t*95:100*sine));paint.setShader(leafGradient);canvas.drawPath(leaf,paint);paint.setShader(null);
    }
    protected void onSizeChanged(int w,int h,int ow,int oh){super.onSizeChanged(w,h,ow,oh);finish();clampPan();}
}
