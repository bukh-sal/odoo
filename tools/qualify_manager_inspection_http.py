"""Bounded proxy and actual HTTP inspection checks on the isolated manager site."""
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'.local/g5-manager-upgrade'
OUTPUT=ROOT/'docs/evidence/G5/20261029-manager-inspection-http-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.contracts import validate
from modular_platform.deployment import DockerObserver
from modular import configuration
from qualify_manager_upgrade_operation import snapshot
import r1_probe

def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['proxy','http']);args=parser.parse_args()
    state=json.loads((LOCAL/'state.json').read_text(encoding='utf-8'));config=json.loads((LOCAL/'operator/target.json').read_text(encoding='utf-8'))
    assert state['disposable'] and state['project']==config['project']=='mp-r0-r1mgr84459f617ab0'
    assert state['phase']=='manager_inspection_core_activated' and state['generation']==config['generation']==4
    assert json.loads((LOCAL/'manager-inspection-core.json').read_text(encoding='utf-8'))['state']=='completed_verified'
    def guard():assert hashlib.sha256((ROOT/'.local/operator/targets/g5.json').read_bytes()).hexdigest()==state['main_target_sha256']
    guard();reader=DockerObserver(config)
    def run(argv,*,input=None):
        r=subprocess.run(argv,input=input,capture_output=True,timeout=150)
        if r.returncode:raise RuntimeError('Named fixture command failed; inspect retained evidence before retry')
        return r
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf-8') as stream:stream.write(json.dumps(value,indent=2)+'\n')
    if args.action=='proxy':
        marker=LOCAL/'inspection-proxy.json';assert not marker.exists() and not OUTPUT.exists();OUTPUT.mkdir()
        edge=reader._container('edge');container=json.loads(run(['docker','inspect',edge]).stdout)[0]
        mount=next(m for m in container['Mounts'] if m['Destination']=='/etc/nginx/conf.d')
        assert mount['Type']=='volume' and mount['Name']==state['project']+'_proxyconfig' and not mount['RW']
        before=run(['docker','exec',edge,'cat','/etc/nginx/conf.d/default.conf']).stdout
        expected=subprocess.check_output(['git','show','71a18c53:deploy/nginx-r0.conf']).replace(b'\r\n',b'\n');assert before==expected
        after=(ROOT/'deploy/nginx-r0.conf').read_bytes();assert hashlib.sha256(after).hexdigest()==json.loads((ROOT/'docs/evidence/G5/20261029-manager-inspection-source/proxy-config-check.json').read_text(encoding='utf-8'))['config_sha256']
        with (LOCAL/'proxy-before-inspection.conf').open('xb') as backup:backup.write(before)
        record={'state':'updating','edge_id':edge,'volume':mount['Name'],'old_sha256':digest(before),'new_sha256':digest(after)}
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');write('proxy-decision.json',record)
        code="""import sys,json,hashlib,base64,os
from pathlib import Path
value=json.load(sys.stdin);target=Path('/proxy/default.conf');assert target.is_file() and not target.is_symlink()
assert 'sha256:'+hashlib.sha256(target.read_bytes()).hexdigest()==value['old_sha256']
raw=base64.b64decode(value['new_base64'],validate=True);temporary=Path('/proxy/default.conf.mp-inspection-next')
with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
os.chmod(temporary,0o644);os.replace(temporary,target)
print(json.dumps({'new_sha256':'sha256:'+hashlib.sha256(target.read_bytes()).hexdigest()}))
"""
        cmd=['docker','run','-i','--name',state['project']+'-inspection-proxy-update','--label','com.modular.disposable='+state['project'],'--network','none','--read-only','--user','0:0','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=volume,source='+mount['Name']+',target=/proxy','--entrypoint','/venv/bin/python',config['image_id'],'-c',code]
        updated=json.loads(run(cmd,input=json.dumps({'old_sha256':digest(before),'new_base64':base64.b64encode(after).decode()}).encode()).stdout);assert updated['new_sha256']==digest(after)
        record['state']='written_needs_reload';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        checked=run(['docker','exec',edge,'nginx','-t']);reloaded=run(['docker','exec',edge,'nginx','-s','reload'])
        assert run(['docker','exec',edge,'cat','/etc/nginx/conf.d/default.conf']).stdout==after;guard()
        record.update(state='completed_verified',utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        write('proxy-update.json',record|{'native_check_stderr':checked.stderr.decode(),'reload_stderr':reloaded.stderr.decode(),'main_target_unchanged':True,'scope':'Upload exact location100MiB; other routes10MiB, DB-manager denial and loopback edge unchanged.'});print(json.dumps(record));return
    assert json.loads((LOCAL/'inspection-proxy.json').read_text(encoding='utf-8'))['state']=='completed_verified'
    marker=LOCAL/'inspection-http.json';assert not marker.exists();marker.write_text(json.dumps({'state':'checking'},indent=2)+'\n',encoding='utf-8')
    before=snapshot(reader);assert len(before['notes'])==2
    fixtures=json.loads((LOCAL/'fixtures.json').read_text(encoding='utf-8'));r1_probe.r1.r0.LOCAL=LOCAL
    operator=r1_probe.Client(state,fixtures,'operator');alice=r1_probe.Client(state,fixtures,'alice')
    catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True)
    artifact=next(d for d in catalog.snapshot() if d['plugin_id']=='org.example.notes' and d['version']=='0.2.3');raw=catalog.path(artifact['digest']).read_bytes();checks=[]
    def checked(name):checks.append(name)
    status,value=operator.request('/api/v1/operations/installed');assert status==200;validate('manager-view',value['data']);installed=value['data'];assert len(installed['items'])==1
    item=installed['items'][0];assert item['database_state']=='installed' and item['dependencies']['state']=='satisfied' and item['health']['state']=='unknown';write('installed.json',installed);checked('current installed schema/version/availability/dependencies and honest health')
    status,value=operator.request('/api/v1/operations/details?digest='+artifact['digest']);assert status==200;details=value['data'];validate('manager-view',details);assert details['manifest']==artifact['manifest'];assert not details['provenance']['publisher_identity_verified'];write('details.json',details);checked('exact manifest, permissions/services/data/provenance/trust details')
    for path in ['/api/v1/operations/installed','/api/v1/operations/details?digest='+artifact['digest']]:
        status,value=alice.request(path);assert status==403 and value['error']['code']=='FORBIDDEN'
    checked('workspace actor denied operator metadata')
    def upload(data,client=operator,*,expected=None,csrf=True,release=None):
        headers={'Content-Type':'application/octet-stream','X-MP-Artifact-Digest':expected or digest(data),'X-MP-Client-Release':release or client.release_token}
        if csrf:headers['X-CSRFToken']=client.csrf
        request=urllib.request.Request(client.base+'/api/v1/operations/validate-upload',headers=headers,data=data)
        try:response=client.http.open(request,timeout=120)
        except urllib.error.HTTPError as error:response=error
        with response:return response.status,json.loads(response.read())
    status,value=upload(raw);assert status==200 and value['data']['result']=='verified';validate('manager-view',value['data']);write('valid-upload.json',value['data']);checked('real curated archive upload and extracted-byte validation')
    status,value=upload(b'uncurated reference bytes');assert status==200 and value['data']['result']=='not_curated' and value['data']['validation_scope']=='trust_gate';write('not-curated-upload.json',value['data']);checked('unknown bytes honestly stop at trust gate')
    status,value=upload(raw,expected='sha256:'+'0'*64);assert status==200 and value['data']['error_code']=='DIGEST_MISMATCH';write('mismatched-upload.json',value['data']);checked('actual byte identity mismatch rejected')
    for kwargs,expected_status,code in [({'csrf':False},403,'FORBIDDEN'),({'client':alice},403,'FORBIDDEN'),({'release':'sha256:'+'0'*64},409,'CONFLICT')]:
        status,value=upload(raw,**kwargs);assert status==expected_status and value['error']['code']==code
    checked('actual upload CSRF/operator/stale-release denials')
    maximum=b'x'*(100*1024*1024);status,value=upload(maximum);assert status==200 and value['data']['size']==len(maximum) and value['data']['result']=='not_curated';write('maximum-upload.json',value['data']);del maximum;checked('exact100MiB upload traverses real proxy and bounded native route')
    connection=http.client.HTTPConnection('127.0.0.1',state['port'],timeout=15);connection.putrequest('POST','/api/v1/operations/validate-upload');connection.putheader('Content-Length',str(100*1024*1024+1));connection.endheaders();response=connection.getresponse();assert response.status==413;response.read();connection.close();checked('proxy rejects100MiBplus1 before receiving oversized body')
    leftovers=run(['docker','exec',reader._container('app'),'/venv/bin/python','-c',"from pathlib import Path;import json;print(json.dumps([p.name for p in Path('/tmp').iterdir() if p.name.startswith('mp-upload-')]))"]).stdout
    assert json.loads(leftovers)==[];checked('no retained upload staging directories')
    notes=alice.call('list',{'limit':25})['items'];assert len(notes)==2 and sorted(n['revision'] for n in notes)==[1,2]
    assert snapshot(reader)==before;guard();checked('retained Notes API/business/features/bindings/grants exact and main unchanged')
    record={'state':'completed_verified','utc':datetime.now(timezone.utc).isoformat(),'generation':4,'checks':checks,'main_target_unchanged':True,'browser_qualification_pending':True};marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');write('http-qualification.json',record);print(json.dumps({'result':record['state'],'checks':len(checks),'generation':4}))

if __name__=='__main__':main()
