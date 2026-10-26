"""Local, synthetic comic/API server. Contains no third-party comic pages."""
import io,json,threading
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,parse_qs
from PySide6.QtGui import QImage,QColor,QPainter,QFont
from PySide6.QtCore import QBuffer,QByteArray,QIODevice,Qt
from html_fixtures import response as html_response

def image(number):
    im=QImage(800,1100,QImage.Format.Format_RGB32);im.fill(QColor(['#d6e9df','#bcd3e6','#ead6c0','#dfcdeb'][(number-1)%4]))
    painter=QPainter(im);painter.setPen(QColor('#263c3c'));painter.setFont(QFont('Arial',45));painter.drawText(im.rect(),Qt.AlignmentFlag.AlignCenter,f'YUKINA ONLINE\nSYNTHETIC PAGE {number}')
    painter.drawRect(50,50,700,1000);painter.drawLine(50,550,750,550);painter.end();buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly);im.save(buffer,'PNG');return bytes(buffer.data())

class Fixture:
    def __init__(self,host='127.0.0.1',port=0):
        fixture=self;self.requests=[];self.fail_pages=False;self.redirect='';self.at_home_prefix='';self.expired_prefix='';self.md_original=False;self.images={i:image(i) for i in range(1,5)}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                p=urlsplit(self.path);path=p.path;q=parse_qs(p.query);fixture.requests.append((self.path,dict(self.headers)))
                base=f'http://{self.headers.get("Host")}'
                body=None;content='application/json';status=200
                if path=='/redirect':self.send_response(302);self.send_header('Location',fixture.redirect);self.end_headers();return
                if html_response(path) is not None:body=('<a href="javascript:void(0)">menu</a>'+html_response(path)).encode('utf-8');content='text/html; charset=utf-8'
                elif path=='/headers':body=dict(self.headers)
                elif path.startswith('/unicode/'):body=fixture.images[1];content='image/png'
                elif path=='/set-md-v1':fixture.at_home_prefix='/token-v1';fixture.expired_prefix='';body={'ok':True}
                elif path=='/md-original-on':fixture.md_original=True;body={'ok':True}
                elif path=='/md-original-off':fixture.md_original=False;body={'ok':True}
                elif path=='/rotate-md':fixture.at_home_prefix='/token-v2';fixture.expired_prefix='/token-v1/';body={'ok':True}
                elif path=='/catalog.json':body={'version':1,'books':[{'id':'demo','title':'雪色日和 · 在线测试','cover':'','chapters':[{'id':'chapter-1','title':'第 1 话 · 出发','pages':[f'/page/{i}.png' for i in range(1,5)]},{'id':'chapter-2','title':'第 2 话 · 归来','pages':['/page/4.png','/page/3.png']}]}]}
                elif path.startswith('/page/') or '/data-saver/' in path or '/data/' in path or '/pages/' in path or '/page/' in path:
                    if fixture.expired_prefix and path.startswith(fixture.expired_prefix):status=403;body={'error':'token expired'}
                    elif fixture.fail_pages:status=503;body={'error':'paused'}
                    else:
                        last=path.rsplit('/',1)[-1].split('.')[0]
                        index=int(last)+1 if '/page/' in path and path.startswith('/api/v1/manga') else int(last)
                        body=fixture.images.get(index,fixture.images[1]);content='image/png'
                elif path=='/manga':body={'data':[{'id':'demo','attributes':{'title':{'ja':'雪色日和'}},'relationships':[]}],'offset':0,'total':1}
                elif path=='/manga/demo/feed':body={'data':[{'id':'chapter-1','attributes':{'volume':'1','chapter':'1','title':'出发','pages':4,'externalUrl':None,'translatedLanguage':'zh'}}],'total':1}
                elif path=='/at-home/server/chapter-1':body={'baseUrl':base+fixture.at_home_prefix,'chapter':{'hash':'test-hash','dataSaver':[f'{i}.png' for i in range(1,5)],'data':[f'{i}.png' for i in range(1,5)] if fixture.md_original else []}}
                elif path=='/api/v1/series':body={'content':[{'id':'demo','name':'雪色日和','metadata':{'title':'雪色日和'}}],'last':True}
                elif path=='/api/v1/series/demo/books':body={'content':[{'id':'chapter-1','metadata':{'title':'第 1 卷'}}],'last':True}
                elif path=='/api/v1/books/chapter-1/pages':body=[{'number':i,'mediaType':'image/png'} for i in range(1,5)]
                elif path=='/api/v1/source/list':body=[{'id':'1234567890123456789','name':'Synthetic Catalog','lang':'zh'}]
                elif path.startswith('/api/v1/source/') and ('/popular/' in path or '/search' in path):body={'mangaList':[{'id':'demo','title':'雪色日和'}],'hasNextPage':False}
                elif path=='/api/v1/manga/demo/chapters':body=[{'id':1001,'index':0,'name':'第 1 话','chapterNumber':1}]
                elif path=='/api/v1/manga/demo/chapter/0':body={'pageCount':4}
                elif path.endswith('/thumbnail'):body=fixture.images[1];content='image/png'
                else:status=404;body={'error':'not found','path':path}
                data=body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode('utf-8');self.send_response(status);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        self.server=ThreadingHTTPServer((host,port),Handler);self.port=self.server.server_address[1];self.url=f'http://127.0.0.1:{self.port}';self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
    def start(self):self.thread.start();return self
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

if __name__=='__main__':
    import argparse
    from PySide6.QtGui import QGuiApplication
    a=QGuiApplication([]);p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=18951);args=p.parse_args();f=Fixture('0.0.0.0',args.port).start();print(f'Fixture on port {f.port}',flush=True)
    try:f.thread.join()
    except KeyboardInterrupt:f.close()
