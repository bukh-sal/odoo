"""Continue existing current fixture after diagnosed new-site dispatch bootstrap."""
from probe import *

def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json');target=load(LOCAL/'operator/target.json');reader=DockerObserver(target)
    dest=OUTPUT/'HTTP-qualification.json';assert not dest.exists();checks=load(OUTPUT/'HTTP-progress.json')['checks']
    prod=Client('production');dev=Client('development');prod.login(state,fixture,'alice');dev.login(state,fixture,'alice')
    def passed(name,**details):
        checks.append(dict(case=name,result='passed',**details));(OUTPUT/'HTTP-progress02.json').write_text(json.dumps(dict(state='in_progress',checks=checks),indent=2)+'\n')
    # Valid CSRF mutation + exact cleanup on a new synthetic record, never an
    # existing note. IDs are recorded immediately; uncertain outcomes stop.
    marker=LOCAL/'csrf-created-note.json';assert not marker.exists();title='SEC02_owned_'+uuid4().hex
    code,value,_,_=prod.service(fixture,'create',{'title':title,'body':'Owned temporary CSRF acceptance fixture'},key='sec02-create-'+uuid4().hex);assert code==200;created=value['data'];marker.write_text(json.dumps(dict(state='created',note=created),indent=2)+'\n',encoding='utf8')
    code,value,_,_=prod.service(fixture,'delete',{'note_id':created['id'],'expected_revision':created['revision']},key='sec02-delete-'+uuid4().hex);assert code==200 and value['data']['deleted'];marker.write_text(json.dumps(dict(state='deleted_verified',note_id=created['id']),indent=2)+'\n',encoding='utf8');passed('valid_session_CSFR_create_delete_succeeds_only_for_owned_temporary_record')
    # Preserve optional Canvas custom page, without expanding its behavior.
    wid=fixture['workspaces']['A']['public_id'];code,value,_,_=prod.request('/api/v1/context?plugin_id=org.example.canvas',headers={'X-MP-Client-Release':prod.release,'X-MP-Workspace':wid});assert code==200;bindings=value['data']['bindings'];binding=next(b for b in bindings if b['alias']=='boards')
    code,value,_,_=prod.request('/api/v1/services/'+binding['service_id']+'/get',dict(api_version=binding['api_version'],request_id=str(uuid4()),input={}),headers={'Origin':prod.origin,'X-CSRFToken':prod.csrf,'X-MP-Client-Release':prod.release,'X-MP-Workspace':wid,'X-MP-Binding':binding['binding_id']});assert code==200 and len(value['data']['cards'])==1;passed('minimal_Canvas_read_and_custom_page_capability_retained')
    # All database-manager variants are rejected before native handling.
    for path in ['/web/database/manager','/web/database/list','/web/database/selector','/web/database/create','/web/%64atabase/manager','/%77eb/database/manager','/web/database%2flist']:
        code,_,_,_=prod.request(path);assert code==403
    for path in ['/web/tests','/web/tests/legacy','/web/qunit','/web/tour','/web/assets/debug/missing.js','/_tests','/app?debug=assets','/web/login?debug=1','/web/login?debug=tests','/web/login?debug=0']:
        code,_,_,_=prod.request(path);assert code==403
    for path in ['/xmlrpc/2/common','/jsonrpc']:
        code,_,_,_=prod.request(path);assert code==404
    passed('production_database_debug_test_and_excluded_external_RPC_endpoints_unavailable')
    assets=[]
    for client in [dev,prod]:
        code,_,_,raw=client.request('/app/org.example.notes/?workspace='+wid);assert code==200
        paths=sorted(set(re.findall(rb'(?:src|href)=[\"\x27]([^\"\x27]*/web/assets/[^\"\x27]+)',raw)))
        for asset in paths:
            path=asset.decode()
            if not path.startswith('/'):continue
            code,_,headers,data=client.request(path);assert code==200 and data and b'## CSS error message ##' not in data
            assets.append(dict(mode=client.mode,path=path,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
        assert len([a for a in assets if a['mode']==client.mode])>=2
    passed('native_shell_and_regular_JS_CSS_assets_work_through_both_edges',assets=assets)
    # Source configurations and data, not merely status codes, stay coherent.
    assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'setup/business-before.json') and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'setup/schema-before.json')
    assert json.loads(sql(reader,"SELECT jsonb_build_object('fixture_users',(SELECT count(*) FROM res_users WHERE active AND (login='admin' OR login LIKE 'g5_%%')),'active_technical_credentials',(SELECT count(*) FROM mp_service_credential WHERE state='active'),'base_url',(SELECT value FROM ir_config_parameter WHERE key='web.base.url'));"))==dict(fixture_users=0,active_technical_credentials=0,base_url=state['origin'])
    passed('production_fixture_old_logins_disabled_and_exact_business_schema_retained')
    report=dict(result='passed_HTTP_matrix',utc=datetime.now(timezone.utc).isoformat(),checks=checks,application_image=state['image_id'],source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/http_profile.py','deploy/nginx-r0.conf','deploy/compose-production.yaml','tests/test_http_profile.py']},limits=['Local TLS uses a private two-day qualification certificate explicitly trusted only by this client.','TLS protocol-negative/rate/protected-target audits separate. External analysis intentionally unavailable; no SVC/job qualification.','Same-origin/native plugins remain trusted; no sandbox or remote production deployment.'])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed_HTTP_matrix',checks=len(checks),assets=len(assets))))


if __name__=='__main__':main()
