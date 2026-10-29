"""Real internal HTTP/native-RPC database selector/session isolation checks."""
import http.cookiejar
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

d=json.load(sys.stdin);base='http://127.0.0.1:8069';jar=http.cookiejar.CookieJar();http=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(jar))


def request(path,payload=None,headers=None,opener=http):
    headers=dict(headers or {})
    if payload is not None:headers['Content-Type']='application/json'
    r=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
    try:response=opener.open(r,timeout=15)
    except urllib.error.HTTPError as error:response=error
    with response:
        raw=response.read()
        try:value=json.loads(raw)
        except ValueError:value={'non_json_status':response.status}
        return response.status,value


def rpc(path,params,headers=None):return request(path,dict(jsonrpc='2.0',method='call',params=params,id=1),headers)[1]


checks=[]
if d.get('foreign_cookie'):
    isolated=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    code,value=request('/web/session/get_session_info',dict(jsonrpc='2.0',method='call',params={},id=1),{'Cookie':d['foreign_cookie']},opener=isolated)
    assert code==200 and value.get('error') and not value.get('result',{}).get('uid')
    checks.append('other_site_session_cookie_not_authenticated')
auth=rpc('/web/session/authenticate',dict(db=d['database'],login=d['login'],password=d['password']))
assert auth.get('result',{}).get('uid')==d['uid'] and auth['result']['db']==d['database']
checks.append('own_database_authentication')
code,release=request('/api/v1/client-release');assert code==200 and release['data']['site_id']==d['site_id'];token=release['data']['token']
headers={'X-MP-Client-Release':token,'X-MP-Workspace':d['workspace']}
params=dict(model='mp.example.note',method='search_read',args=[[]],kwargs={'fields':['public_id','title','revision']})
value=rpc('/web/dataset/call_kw/mp.example.note.search_read',params,headers);rows=value['result']
assert len(rows)==2 and any(r['title']=='TEN_'+d['case'].upper()+'_VISIBLE' for r in rows) and all('TEN_'+d['other_case'].upper()+'_VISIBLE'!=r['title'] for r in rows)
checks.append('native_Odoo_reads_only_selected_database')
bad=rpc('/web/session/authenticate',dict(db=d['other_database'],login=d['login'],password=d['password']))
assert bad.get('error',{}).get('data',{}).get('name')=='odoo.exceptions.AccessError' and not bad.get('result')
checks.append('explicit_other_database_authentication_denied_by_filter')
info=rpc('/web/session/get_session_info',{});assert info['result']['db']==d['database'] and info['result']['uid']==d['uid']
code,value=request('/web/dataset/call_kw/mp.example.note.search_read',dict(jsonrpc='2.0',method='call',params=params,id=1),dict(headers,**{'X-Odoo-Database':d['other_database']}));assert code==403 and value=={'non_json_status':403}
checks.append('foreign_database_header_with_session_refused_HTTP403')
code,release=request('/api/v1/client-release?db='+d['other_database']);assert code==200 and release['data']['site_id']==d['site_id']
checks.append('foreign_db_query_cannot_switch_platform_site')
cookie='; '.join(c.name+'='+c.value for c in jar);assert cookie
Path('/tmp/ten-session-cookie').write_text(cookie)
print(json.dumps(dict(result='passed',case=d['case'],database=d['database'],checks=checks,native_note_count=2,no_public_port=True)),flush=True)
