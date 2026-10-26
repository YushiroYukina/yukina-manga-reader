"""Production Java protocol checks on JVM when an Android device is unavailable."""
from pathlib import Path
import hashlib,os,subprocess,sys,urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from PySide6.QtWidgets import QApplication
from fixture_server import Fixture
app=QApplication.instance() or QApplication([])
android=ROOT/'android';tools=Path(os.environ.get('YUKINA_ANDROID_TOOLS',android/'.tools'));jdk=Path((tools/'jdk-path.txt').read_text('utf-8-sig').strip());androidjar=tools/'sdk/platforms/android-34/android.jar'
jar=ROOT/'.tools/testlibs/json-20240303.jar';expected='3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed'
if not jar.exists():
    jar.parent.mkdir(parents=True,exist_ok=True);jar.write_bytes(urllib.request.urlopen('https://repo.maven.apache.org/maven2/org/json/json/20240303/json-20240303.jar',timeout=45).read())
if hashlib.sha256(jar.read_bytes()).hexdigest()!=expected:raise SystemExit('Host JSON test dependency checksum mismatch')
out=android/'build/host-online';out.mkdir(parents=True,exist_ok=True);classes=android/'build/classes'
cp=os.pathsep.join(map(str,[jar,classes,androidjar]));test=android/'tests/java/cn/migi/reader/OnlineProtocolChecks.java'
subprocess.run([str(jdk/'bin/javac.exe'),'-encoding','UTF-8','-cp',cp,'-d',str(out),str(test)],check=True)
fixture=Fixture().start()
try:
    process=subprocess.run([str(jdk/'bin/java.exe'),'-cp',str(out)+os.pathsep+cp,'cn.migi.reader.OnlineProtocolChecks',fixture.url],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (ROOT/'work').mkdir(exist_ok=True);(ROOT/'work/android-protocol-checks.txt').write_text(process.stdout+process.stderr,encoding='utf-8');print(process.stdout);print(process.stderr);raise SystemExit(process.returncode)
finally:fixture.close()
