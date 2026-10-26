package cn.migi.reader;
import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
public final class FixtureSetup extends Activity {
    public void onCreate(Bundle state){super.onCreate(state);String target=getIntent().getStringExtra("target");
        if("cn.yukina.online.qa".equals(target)){
            for(String suffix:new String[]{".documents",".onlinefiles"}){
                Uri tree=DocumentsContract.buildTreeDocumentUri(getPackageName()+suffix,"root");
                grantUriPermission(target,tree,Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION|Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
            }
        }
        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(this::finish,300);
    }
}
