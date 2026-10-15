package cn.migi.reader;
import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
public final class FixtureSetup extends Activity {
    public void onCreate(Bundle state){super.onCreate(state);String target=getIntent().getStringExtra("target");
        if(target!=null&&target.startsWith("cn.migi.reader")){
            Uri tree=DocumentsContract.buildTreeDocumentUri(getPackageName()+".documents","root");
            grantUriPermission(target,tree,Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION|Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        }
        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(this::finish,300);
    }
}
