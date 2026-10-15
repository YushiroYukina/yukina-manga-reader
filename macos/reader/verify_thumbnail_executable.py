"""Verify a packaged worker through the same redirected pipes used by QProcess."""
import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'tests'))
from test_reader import fixtures,temporary_directory
from PySide6.QtGui import QImage

with temporary_directory() as directory:
    root=Path(directory); source=fixtures(root)[1]; cache=root/'cache'/'covers'; output=cache/'sample.png'
    request={'id':'sample','source':str(source),'kind':'book','output':str(output)}
    process=subprocess.Popen([str(Path(sys.argv[1]).resolve()),'--thumbnail-worker',str(cache)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
    try:
        stdout,stderr=process.communicate(json.dumps(request)+'\n',timeout=15)
    except subprocess.TimeoutExpired:
        process.kill(); process.communicate(); raise
    assert process.returncode==0, (process.returncode,stdout,stderr)
    reply=json.loads(stdout.strip()); assert reply['ok'],reply
    image=QImage(str(output)); assert image.pixelColor(210,300).name()=='#ff0000'
    assert output.drive.casefold()!='c:'
    print('Packaged worker redirected pipes and first-page thumbnail: PASS')
