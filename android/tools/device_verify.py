"""Explicit-device QA runner; never clears or inserts records in the real app."""
from pathlib import Path
import argparse,os,subprocess,time
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--serial',required=True);p.add_argument('--physical',action='store_true');args=p.parse_args()
adb=root/'.tools/sdk/platform-tools/adb.exe';env=os.environ.copy();env['ANDROID_USER_HOME']=str(root/'.tools/android-home')
def call(parts):return subprocess.run([str(adb),'-s',args.serial,*parts],check=True,capture_output=True,env=env,timeout=40)
if not args.physical and call(['shell','getprop','ro.boot.qemu']).stdout.strip()!=b'1':raise SystemExit('Physical target requires --physical.')
for apk in ['Migi-Android-QA.apk','Migi-Android-QA-tests.apk']:print(call(['install','-r',str(root/'dist'/apk)]).stdout.decode(errors='replace'))
call(['shell','am','force-stop','cn.migi.reader.qa']);call(['shell','pm','clear','cn.migi.reader.qa'])
process=subprocess.Popen([str(adb),'-s',args.serial,'shell','am','instrument','-w','cn.migi.reader.qa.tests/cn.migi.reader.NativeChecks'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
lines=[]
for line in process.stdout:
    lines.append(line);print(line,end='',flush=True)
    if 'READY_FIXTURE_GRANT' in line:call(['shell','am','start','-W','-n','cn.migi.reader.qa.tests/cn.migi.reader.FixtureSetup','--es','target','cn.migi.reader.qa'])
    if 'READY_UI' in line:
        time.sleep(1)
        call(['shell','am','start','-W','-f','0x20020000','-n','cn.migi.reader.qa/cn.migi.reader.MainActivity'])
process.wait();output=''.join(lines);(root/'build/device-native-checks.txt').write_text(output,encoding='utf-8')
if 'Native Android checks passed:' not in output:raise SystemExit('Native checks failed; inspect build/device-native-checks.txt')
print('DEVICE VERIFICATION PASSED')
