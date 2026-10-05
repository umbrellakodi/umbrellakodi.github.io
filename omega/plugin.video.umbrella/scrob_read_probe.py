import json
import xml.etree.ElementTree as E
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
s={n.get('id'):n.text or '' for n in E.parse('D:/kodi212/portable_data/userdata/addon_data/plugin.video.umbrella/settings.xml').getroot().findall('setting')}
base=s['scrob.baseurl'].rstrip('/').removesuffix('/api/proxy')+'/api/proxy'
opener=build_opener(NoRedirect)
for mode in ('key','bearer','both'):
    for path in ('/history?type=episode&page=1&page_size=1','/history/next-up','/history/continue-watching','/lists'):
        url=base+path
        headers={}
        if mode in ('key','both'): url+=('&' if '?' in url else '?')+urlencode({'api_key':s['scrob.apikey']})
        if mode in ('bearer','both'): headers['Authorization']='Bearer '+s['scrob.accesstoken']
        try:
            try: r=opener.open(Request(url,headers=headers),timeout=20)
            except HTTPError as e: r=e
            body=r.read()
            out={'mode':mode,'path':path,'status':r.code,'type':r.headers.get('Content-Type'),'redirect_path':urlsplit(r.headers.get('Location','')).path}
            try:
                d=json.loads(body)
                out['shape']=list(d) if isinstance(d,dict) else type(d).__name__
                if isinstance(d,dict):
                    out['counts']={k:len(v) for k,v in d.items() if isinstance(v,list)}
                    out['totals']={k:v for k,v in d.items() if k in ('total_results','total_pages')}
                    for k,v in d.items():
                        if isinstance(v,list) and v and isinstance(v[0],dict):
                            out[k+'_item_keys']=list(v[0])
                            if isinstance(v[0].get('media'),dict): out[k+'_media_keys']=list(v[0]['media']); out[k+'_media_type']=v[0]['media'].get('type')
            except ValueError: pass
            print(json.dumps(out))
        except Exception as e: print(json.dumps({'mode':mode,'path':path,'error_type':type(e).__name__}))

url=base+'/lists?'+urlencode({'api_key':s['scrob.apikey']})
lists=json.load(opener.open(Request(url),timeout=20))['lists']
for lst in lists:
    d=json.load(opener.open(Request(base+'/lists/'+str(lst['id'])+'?'+urlencode({'api_key':s['scrob.apikey']})),timeout=20))
    items=d.get('items',[])
    print(json.dumps({'list_detail_keys':list(d),'items':len(items),'item_keys':list(items[0]) if items else [],'media_types':sorted({str((i.get('media') or {}).get('type')) for i in items})}))
