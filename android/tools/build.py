"""Portable Android build using the official SDK; never contacts a device."""
from pathlib import Path
import os,subprocess,zipfile,shutil,sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'.tools'
JDK=Path((TOOLS/'jdk-path.txt').read_text(encoding='utf-8').strip())
SDK=TOOLS/'sdk'; BT=SDK/'build-tools/34.0.0'; ANDROID=SDK/'platforms/android-34/android.jar'
BUILD=ROOT/'build'; BUILD.mkdir(exist_ok=True)
env=os.environ.copy(); env['JAVA_HOME']=str(JDK);env['ANDROID_HOME']=str(SDK)
env['PATH']=str(JDK/'bin')+os.pathsep+env.get('PATH','')
temp=BUILD/'temp';temp.mkdir(exist_ok=True);env['TEMP']=env['TMP']=str(temp)
def run(args):
    print('Running',Path(str(args[0])).name,flush=True)
    command=[str(args[0])]
    for arg in args[1:]:
        if isinstance(arg,Path):
            try:arg=arg.relative_to(ROOT)
            except ValueError:pass
        command.append(str(arg))
    subprocess.run(command,env=env,cwd=ROOT,check=True)
def java(tool):return JDK/'bin'/f'{tool}.exe'
def compile_java(sources,classes,classpath):
    classes.mkdir(parents=True,exist_ok=True)
    argfile=BUILD/'javac-args.txt'
    argfile.write_text('\n'.join('"'+str(a).replace('\\','/')+'"' for a in sources),encoding='utf-8')
    run([java('javac'),'-encoding','UTF-8','-source','8','-target','8','-Xlint:-options','-g','-parameters','-cp',classpath,'-d',classes,'@'+str(argfile)])
def package(name,manifest,res,classes,dex,out):
    dex.mkdir(parents=True,exist_ok=True)
    if res:
        compiled=BUILD/(name+'-res.zip');run([BT/'aapt2.exe','compile','--dir',res,'-o',compiled])
        run([BT/'aapt2.exe','link','-o',BUILD/(name+'-resources.apk'),'-I',ANDROID,'--manifest',manifest,'--auto-add-overlay',compiled])
    else:run([BT/'aapt2.exe','link','-o',BUILD/(name+'-resources.apk'),'-I',ANDROID,'--manifest',manifest])
    run([java('java'),'-cp',BT/'lib/d8.jar','com.android.tools.r8.D8','--min-api','26','--lib',ANDROID,'--output',dex,*classes.rglob('*.class')])
    unsigned=BUILD/(name+'-unsigned.apk');shutil.copy2(BUILD/(name+'-resources.apk'),unsigned)
    with zipfile.ZipFile(unsigned,'a',compression=zipfile.ZIP_DEFLATED) as z:
        for p in dex.glob('*.dex'):z.write(p,p.name)
        assets=ROOT/('tests/assets' if name=='tests' else 'app/src/main/assets')
        if assets.exists():
            for p in assets.rglob('*'):
                if p.is_file():z.write(p,'assets/'+p.relative_to(assets).as_posix())
    aligned=BUILD/(name+'-aligned.apk');run([BT/'zipalign.exe','-f','4',unsigned,aligned])
    key=TOOLS/'development.keystore'
    if not key.exists():run([java('keytool'),'-genkeypair','-keystore',key,'-storepass','android','-keypass','android','-alias','migi-dev','-keyalg','RSA','-keysize','2048','-validity','3650','-dname','CN=MIGI Development'])
    out.parent.mkdir(parents=True,exist_ok=True)
    run([java('java'),'-jar',BT/'lib/apksigner.jar','sign','--ks',key,'--ks-key-alias','migi-dev','--ks-pass','pass:android','--key-pass','pass:android','--out',out,aligned])
    run([java('java'),'-jar',BT/'lib/apksigner.jar','verify','--verbose',out])

classes=BUILD/'classes'
compile_java(list((ROOT/'app/src/main/java').rglob('*.java')),classes,str(ANDROID))
qa='--qa' in sys.argv
manifest=ROOT/'app/src/main/AndroidManifest.xml'
if qa:
    ET.register_namespace('android','http://schemas.android.com/apk/res/android')
    tree=ET.parse(manifest); tree.getroot().set('package','cn.migi.reader.qa')
    app=tree.getroot().find('application'); app.set('{http://schemas.android.com/apk/res/android}label','右页 · MIGI 验收')
    app.find('activity').set('{http://schemas.android.com/apk/res/android}name','cn.migi.reader.MainActivity')
    manifest=BUILD/'qa-manifest.xml';tree.write(manifest,encoding='utf-8',xml_declaration=True)
package('app',manifest,ROOT/'app/src/main/res',classes,BUILD/'dex',ROOT/('dist/Migi-Android-QA.apk' if qa else 'dist/Migi-Android-0.1.0-alpha.apk'))
tests=list((ROOT/'tests/java').rglob('*.java'))
if tests:
    testclasses=BUILD/'host-tests';compile_java(tests,testclasses,str(classes))
    run([java('java'),'-ea','-cp',str(classes)+os.pathsep+str(testclasses),'cn.migi.reader.CoreTests'])
if '--instrumentation' in sys.argv:
    tc=BUILD/'android-tests';compile_java(list((ROOT/'tests/android').rglob('*.java')),tc,str(ANDROID)+os.pathsep+str(classes))
    manifest=ROOT/'tests/AndroidManifest.xml'
    if qa:
        tree=ET.parse(manifest);tree.getroot().set('package','cn.migi.reader.qa.tests')
        tree.getroot().find('instrumentation').set('{http://schemas.android.com/apk/res/android}targetPackage','cn.migi.reader.qa')
        tree.getroot().find('application/provider').set('{http://schemas.android.com/apk/res/android}authorities','cn.migi.reader.qa.tests.documents')
        manifest=BUILD/'qa-tests-manifest.xml';tree.write(manifest,encoding='utf-8',xml_declaration=True)
    package('tests',manifest,None,tc,BUILD/'test-dex',ROOT/('dist/Migi-Android-QA-tests.apk' if qa else 'dist/Migi-Android-tests.apk'))
print('BUILD PASSED',flush=True)
