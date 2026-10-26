"""Original tiny HTML pages, never copied third-party manga/site content."""
import json

def packed_manifest():
    meta={'files':['01.webp','02.webp'],'path':'/synthetic/','sl':{'e':123,'m':'test'}}
    # The adapter reads only literal arguments, and must never execute this body.
    payload='Reader('+json.dumps(meta,separators=(',',':'))+').show();'
    return "window['eval'](function(p,a,c,k,e,d){throw new Error('MUST NOT EXECUTE');}("+repr(payload)+",36,0,''.split('|'),0,{}))"

def response(path):
    if path=='/search':return '<a href="/manga/7/snow"><img data-src="/page/1.png"></a><a href="/manga/7/snow">Snow &amp; Day</a><a href="/search?q=snow&amp;page=2">Next</a><a href="https://other.invalid/manga/8/advert">AD</a>'
    if path in ('/list/view_p1.html','/s/snow_p1.html'):return '<a class="bcover" title="雪色 &amp; 日和" href="/comic/7/"><img src="/page/1.png"></a><a href="/list/view_p2.html">下一页</a>'
    if path=='/manga/7/snow':return '<div id="chapters"><a href="/chapters/7-2/snow-2">Chapter 2</a><a href="/chapters/7-1/snow-1">Chapter 1</a></div><a href="/chapters/8-1/other">Other book</a>'
    if path=='/comic/7/':return '<div id="chapter-list-1"><ul><li><a class="status0" href="/comic/7/2.html" title="第 2 话">2</a></li><li><a class="status1" href="/comic/7/3.html">付费章节</a></li><li><a class="status0" href="/comic/7/1.html">第 1 话</a></li></ul></div>'
    if path.startswith('/chapters/7-'):return '<img src="https://ads.invalid/ad.png"><picture><source srcset="ignored"><img data-src="/page/1.png"></picture><picture><img src="/page/2.png"></picture>'
    if path in ('/comic/7/1.html','/comic/7/2.html'):return '<script>'+packed_manifest()+'</script>'
    return None
