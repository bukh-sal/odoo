"""Continue only the verified empty proxy seed; no DB/secrets recreation."""
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-httpsecurity';SOURCE=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from http_profile import render


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');source=load(SOURCE/'operator/target.json');assert state['phase']=='restoring_owned_copy' and not state['containers'] and state['project']=='mp-r0-r1http9669f0969d1d' and source['generation']==18
    assert b"Permission denied: '/proxy/default.conf'" in (LOCAL/'setup.stderr').read_bytes()
    project=state['project'];database=state['active_db'];site=state['site_id'];origin=state['origin'];production=(LOCAL/'production.conf').read_text(encoding='utf8');assert production==render('production',origin)
    reader=DockerObserver(source);business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA));own=DockerObserver(dict(source,project=project,sites=[dict(database=database,site_id=site)]))
    expected=json.loads(json.dumps(business).replace(source['sites'][0]['site_id'],site));assert json.loads(sql(own,BUSINESS_SQL))==expected and json.loads(sql(own,SCHEMA))==schema
    deployment=json.loads(sql(own,"SELECT to_jsonb(value) FROM ir_config_parameter WHERE key='mp.deployment_id';"));assert str(UUID(deployment))==deployment
    assert json.loads(sql(own,"SELECT to_jsonb(count(*)) FROM res_users WHERE active AND login LIKE 'g5_%%';"))==4
    for name in ['app','edge-development','edge-production']:assert subprocess.run(['docker','inspect',project+'-'+name],capture_output=True).returncode!=0
    def phase(value):state.update(phase=value,utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    def command(args,*,input=None,timeout=180):
        r=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
        if r.returncode:
            (LOCAL/'resume-setup.stderr').write_bytes(r.stderr);raise RuntimeError('Reconcile current owned setup before further action')
        return r.stdout
    verifying_tls=sys.argv[1:]==['--verify-existing-tls'];continuing_tls=sys.argv[1:] in (['--existing-tls'],['--verify-existing-tls']);assert sys.argv[1:] in ([],['--existing-tls'],['--verify-existing-tls'])
    check="from pathlib import Path;assert len([p for p in Path('/files/filestore').rglob('*') if p.is_file()])>=54;print('Copied filestore present')"
    command(['docker','run','--rm','--read-only','--network','none','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+project+'_prodproxy,target=/proxy,readonly','--mount','type=volume,source='+project+'_tls,target=/tls,readonly','--mount','type=volume,source='+project+'_filestore,target=/files,readonly','--entrypoint','/venv/bin/python',state['image_id'],'-c',check])
    fixture=load(SOURCE/'fixtures.json');accounts={};token=project.removeprefix('mp-r0-r1http')
    for actor in ['alice','bob','operator']:
        login='sec_'+actor+'_'+token;accounts[actor]=dict(id=fixture['users'][actor]['id'],login=login,password=(LOCAL/('password-'+actor)).read_text(encoding='utf8').strip());fixture['users'][actor]['login']=login
    if continuing_tls:
        if verifying_tls:
            assert b"Permission denied: '/tls/server.key'" in (LOCAL/'resume-setup.stderr').read_bytes()
            verify="""import hashlib,json,pathlib
from cryptography import x509
from cryptography.hazmat.primitives import serialization
root=pathlib.Path('/tls');key=root/'server.key';cert=root/'server.crt';assert key.stat().st_uid==101 and key.stat().st_mode&0o777==0o400 and cert.stat().st_uid==101 and cert.stat().st_mode&0o777==0o444
k=serialization.load_pem_private_key(key.read_bytes(),password=None);c=x509.load_pem_x509_certificate(cert.read_bytes());assert k.public_key().public_numbers()==c.public_key().public_numbers();print(json.dumps({'result':'existing_TLS_valid_and_readable_by_actual_UID101','certificate_sha256':hashlib.sha256(cert.read_bytes()).hexdigest()}))
"""
            report=json.loads(command(['docker','run','--rm','--network','none','--read-only','--user','101:101','--cap-drop','ALL','--mount','type=volume,source='+project+'_tls,target=/tls,readonly','--entrypoint','/venv/bin/python',state['image_id'],'-c',verify]))
            report.update(diagnosis='Previous chmod/chown succeeded; UID0 without DAC capability correctly cannot reread UID101 mode0400 key. Verify as actual edge UID101; no more permission mutation.',TLS_regenerated=False,database_recreated=False)
            (OUTPUT/'setup/tls-permission-reconciliation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
            stored=command(['docker','run','--rm','--network','none','--read-only','--mount','type=volume,source='+project+'_prodproxy,target=/proxy,readonly','--entrypoint','/venv/bin/python',state['image_id'],'-c',"from pathlib import Path;print(Path('/proxy/default.conf').read_text(),end='')"]).decode();assert stored==production
            spec=importlib.util.spec_from_file_location('mp_http_setup',OUTPUT/'setup.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            module.finish_setup(state,source,production,project,database,accounts,origin,fixture,site,deployment,reader,business,schema,phase,command,seeded=True,tls_ready=True)
            return
        assert b"Operation not permitted: '/tls/server.crt'" in (LOCAL/'resume-setup.stderr').read_bytes()
        repair="""import hashlib,json,os,pathlib
from cryptography import x509
from cryptography.hazmat.primitives import serialization
root=pathlib.Path('/tls');key=(root/'server.key').read_bytes();cert=(root/'server.crt').read_bytes();k=serialization.load_pem_private_key(key,password=None);c=x509.load_pem_x509_certificate(cert);assert k.public_key().public_numbers()==c.public_key().public_numbers()
for p in root.iterdir():p.chmod(0o400 if p.suffix=='.key' else 0o444);os.chown(p,101,101)
assert (root/'server.key').read_bytes()==key and (root/'server.crt').read_bytes()==cert
print(json.dumps({'result':'existing_key_certificate_preserved_permissions_repaired','certificate_sha256':hashlib.sha256(cert).hexdigest()}))
"""
        report=json.loads(command(['docker','run','--rm','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--cap-add','FOWNER','--mount','type=volume,source='+project+'_tls,target=/tls','--entrypoint','/venv/bin/python',state['image_id'],'-c',repair]))
        report.update(diagnosis='chmod after chown needs FOWNER; future seed changes mode before transferring owner',TLS_regenerated=False,database_recreated=False)
        (OUTPUT/'setup/tls-permission-reconciliation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        stored=command(['docker','run','--rm','--network','none','--read-only','--mount','type=volume,source='+project+'_prodproxy,target=/proxy,readonly','--entrypoint','/venv/bin/python',state['image_id'],'-c',"from pathlib import Path;print(Path('/proxy/default.conf').read_text(),end='')"]).decode();assert stored==production
    else:
        (OUTPUT/'setup/volume-seed-reconciliation.json').write_text(json.dumps(dict(result='exact_existing_copy_continuation',failure='Immutable image default UID10001 cannot seed root-owned new proxy volume',diagnosis='Proxy config/TLS absent, copied DB/business/schema/54files present, source unchanged, no account provisioning or worker started',correction='Explicit owner UID0 with dropped capabilities seeds only the new empty config volume; retain all existing DB/files/secrets',database_recreated=False,credentials_regenerated=False),indent=2)+'\n',encoding='utf8')
    spec=importlib.util.spec_from_file_location('mp_http_setup',OUTPUT/'setup.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.finish_setup(state,source,production,project,database,accounts,origin,fixture,site,deployment,reader,business,schema,phase,command,seeded=continuing_tls,tls_ready=continuing_tls)


if __name__=='__main__':main()
