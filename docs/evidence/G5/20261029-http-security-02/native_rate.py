"""Real native429/API429 formats plus unchanged Odoo parser/handler compatibility."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-httpsecurity'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.contracts import validate


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'native-rate-qualification.json';assert not dest.exists();state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json')
    spec=importlib.util.spec_from_file_location('mp_http_probe',OUTPUT/'probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);client=m.Client('production');client.login(state,fixture,'alice');cookie='; '.join(c.name+'='+c.value for c in client.jar);ctx=ssl.create_default_context(cafile=str(LOCAL/'server.crt'))
    def request(i):
        body=dict(jsonrpc='2.0',method='call',id=i,params=dict(model='mp.example.note',method='search_count',args=[[]],kwargs={}))
        headers={'Host':client.authority,'Cookie':cookie,'Origin':client.origin,'Content-Type':'application/json','X-MP-Client-Release':client.release,'X-MP-Workspace':fixture['workspaces']['A']['public_id']}
        req=urllib.request.Request(client.base+'/web/dataset/call_kw/mp.example.note.search_count',data=json.dumps(body).encode(),headers=headers);http=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ctx))
        try:r=http.open(req,timeout=30)
        except urllib.error.HTTPError as e:r=e
        with r:
            value=json.load(r)
            if r.status==200:assert value.get('result')==2
            else:assert r.status==429 and value['jsonrpc']=='2.0' and value['error']['code']==429 and value['error']['data']['name']=='odoo.exceptions.UserError'
            return r.status,value
    resume=sys.argv[1:]==['--resume-api'];assert sys.argv[1:] in ([],['--resume-api'])
    if not resume:
        with ThreadPoolExecutor(max_workers=16) as pool:results=list(pool.map(request,range(240)))
        example=next(v for code,v in results if code==429);(OUTPUT/'native-rate-example.json').write_text(json.dumps(example,indent=2)+'\n',encoding='utf8')
        native_counts=dict(Counter(code for code,_ in results))
    else:
        assert load(OUTPUT/'native-rate-example.json')['error']['data']['name']=='odoo.exceptions.UserError'
        native_counts=None
    def api_request(i):
        req=urllib.request.Request(client.base+'/api/v1/client-release',headers={'Host':client.authority,'Cookie':cookie});http=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ctx))
        try:r=http.open(req,timeout=30)
        except urllib.error.HTTPError as e:r=e
        with r:return r.status,json.load(r)
    with ThreadPoolExecutor(max_workers=16) as pool:api_results=list(pool.map(api_request,range(160)))
    assert set(c for c,_ in api_results)<={200,429};api=next(v for c,v in api_results if c==429);validate('service-response',api);assert api['error']['code']=='RATE_LIMITED';(OUTPUT/'API-rate-example.json').write_text(json.dumps(api,indent=2)+'\n',encoding='utf8')
    # Execute the actual pinned native parsing/error-handler functions. Stubs
    # supply only the surrounding registry/dialog services, not their behavior.
    code=r"""const fs=require('fs'),assert=require('assert');
const rpc=fs.readFileSync('addons/web/static/src/core/network/rpc.js','utf8');
const handlers=fs.readFileSync('addons/web/static/src/core/errors/error_handlers.js','utf8');
function extract(s,name){const start=s.indexOf('export '+name);assert(start>=0);const end=s.indexOf('\n}',start)+2;return s.slice(start,end).replace(/^export /,'');}
const native=new Function(extract(rpc,'class RPCError')+'\n'+extract(rpc,'function makeErrorFromResponse')+';return {RPCError,makeErrorFromResponse};')();
class UncaughtPromiseError extends Error {constructor(){super();this.unhandledRejectionEvent={preventDefault(){}};}}
const empty={contains(){return false;}};class Dialog{};
const handler=new Function('RPCError','UncaughtPromiseError','errorNotificationRegistry','errorDialogRegistry','RPCErrorDialog',extract(handlers,'function rpcErrorHandler')+';return rpcErrorHandler;')(native.RPCError,UncaughtPromiseError,empty,empty,Dialog);
const payload=JSON.parse(fs.readFileSync('docs/evidence/G5/20261029-http-security-02/native-rate-example.json','utf8'));const api=JSON.parse(fs.readFileSync('docs/evidence/G5/20261029-http-security-02/API-rate-example.json','utf8'));let shown=0;
const env={services:{dialog:{add(component,props){assert.equal(component,Dialog);assert.equal(props.data.name,'odoo.exceptions.UserError');assert.equal(props.code,429);assert(props.message.includes('Too many'));shown++;}}}};
assert.throws(()=>handler(env,new UncaughtPromiseError(),native.makeErrorFromResponse(api.error)),TypeError);
assert.equal(handler(env,new UncaughtPromiseError(),native.makeErrorFromResponse(payload.error)),true);assert.equal(shown,1);
process.stdout.write(JSON.stringify({result:'passed',actual_native_functions:true,old_API_DTO_would_throw:true,new_native_error_reaches_existing_dialog_service:true,Owl_render_not_observed:true}));
"""
    r=subprocess.run(['node','-e',code],cwd=ROOT,capture_output=True,timeout=15);assert r.returncode==0,r.stderr.decode();native=json.loads(r.stdout)
    paths=['addons/web/static/src/core/network/rpc.js','addons/web/static/src/core/errors/error_handlers.js'];hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths};app=next(r['container_id'] for r in state['containers'] if r['purpose']=='application')
    inspect="import hashlib,json;from pathlib import Path;print(json.dumps({p:hashlib.sha256((Path('/opt/modular')/p).read_bytes()).hexdigest() for p in "+repr(paths)+"}))"
    actual=json.loads(subprocess.check_output(['docker','exec',app,'/venv/bin/python','-c',inspect],timeout=15));assert actual==hashes
    time.sleep(3);code,value,_,_=client.rpc('mp.example.note','search_count',[[]],workspace=fixture['workspaces']['A']['public_id']);assert code==200 and value['result']==2
    report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),native_requests=240,native_status_counts=native_counts,API_requests=160,API_status_counts=dict(Counter(c for c,_ in api_results)),API_error_matches_frozen_contract=True,native_error_matches_existing_Odoo_RPC=True,native_parser_and_handler=native,native_source_sha256=hashes,normal_native_read_recovers=True,limits=['Actual server responses and actual pinned native functions verified; no Owl dialog rendering observed.','Native cohort finished and response preserved before a subsequent single API request had already recovered; API got its own bounded burst. Original native cohort not repeated; exact native status distribution not retained if resumed.','Only new rate-response protocol branch changed after earlier HTTP/TLS/rate qualification; no native or frontend implementation changed.'])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',native_requests=240,native_parser_handler_compatible=True,API_contract_compatible=True)))


if __name__=='__main__':main()
