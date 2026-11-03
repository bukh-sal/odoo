"""Installed identity proof on two distinct guarded native HTTP workers.

Only owned Note fixtures and Alice's A membership are changed. The private
preimage is durable before changes; originals and stopped helpers are retained.
"""
import argparse,hashlib,json,socket,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
import activate as current
j,f=current.j,current.f
f.OUTPUT=OUT
def context():
    state,native=current.context();return state,f.load(current.MARKER),native
from modular_platform.operator_os import protect_directory
import r1_probe
MARKER=j.LOCAL/'core21-HTTP-01.json'
def inspect(name):return json.loads(subprocess.check_output(['docker','inspect',name]))[0]
def snapshot(state,label):
    return json.loads(f.sql(state,label,"SELECT jsonb_build_object('notes',(SELECT jsonb_agg(to_jsonb(n) ORDER BY id) FROM mp_example_note n),'boards',(SELECT COALESCE(jsonb_agg(to_jsonb(b) ORDER BY id),'[]') FROM mp_example_canvas_board b),'projections',(SELECT jsonb_agg(to_jsonb(p) ORDER BY id) FROM mp_example_note_event_summary p),'memberships',(SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM mp_membership m),'groups',(SELECT jsonb_agg(to_jsonb(g) ORDER BY uid,gid) FROM res_groups_users_rel g),'events',(SELECT jsonb_agg(to_jsonb(o) ORDER BY id) FROM mp_outbox o));"))
def setup():
    state,record,native=context();assert state['phase']=='core21_remote_interop_verified' and native.config['generation']==30 and not MARKER.exists()
    with socket.socket() as check:check.bind(('127.0.0.1',18090))
    fixture=f.load(j.LOCAL/'fixtures.json');baseline=snapshot(state,'core21-HTTP-before-01');f.write(j.LOCAL/'core21-HTTP-baseline-01.json',baseline)
    secondary=state['project']+'-core21-http-worker-01';edge=state['project']+'-core21-http-edge-01'
    for name in [secondary,edge]:assert subprocess.run(['docker','inspect',name],capture_output=True).returncode!=0
    private=dict(state='starting_owned_secondary',secondary=secondary,edge=edge,port=18090,owned_notes=[],membership_change_started=False,primary=native.config['worker_id'],image_id=state['image_id']);f.write(MARKER,private)
    config=protect_directory(j.LOCAL/'core21-http-proxy');conf=config/'default.conf';assert not conf.exists()
    conf.write_text('server {listen 8069; server_name _; location ^~ /web/database {return 403;} location / {proxy_set_header Host $http_host; proxy_set_header X-Forwarded-Proto $scheme; proxy_pass http://'+secondary+':8069;}}\n')
    f.command('core21-HTTP-worker-start-01',['docker','run','-d','--name',secondary,'--log-driver','none','--label','com.modular.disposable='+state['project'],'--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',state['project']+'_runtime','--memory','1g','--pids-limit','256','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular','--env','MP_EXPECTED_DATABASE='+state['active_db'],'--env','MP_EXPECTED_INVENTORY_DIGEST='+state['inventory_digest'],state['image_id']])
    edge_image=inspect(state['project']+'-edge-1')['Image']
    f.command('core21-HTTP-edge-create-01',['docker','create','--name',edge,'--log-driver','none','--label','com.modular.disposable='+state['project'],'--read-only','--user','101:101','--cap-drop','ALL','--security-opt','no-new-privileges','--network',state['project']+'_edge','--publish','127.0.0.1:18090:8069','--tmpfs','/var/cache/nginx:rw,uid=101,gid=101,mode=0755','--tmpfs','/var/run:rw,uid=101,gid=101,mode=0755','--mount','type=bind,source='+str(config)+',target=/etc/nginx/conf.d,readonly','--entrypoint','nginx',edge_image,'-g','daemon off;'])
    f.command('core21-HTTP-edge-network-01',['docker','network','connect',state['project']+'_runtime',edge]);f.command('core21-HTTP-edge-start-01',['docker','start',edge])
    r1_probe.r1.r0.LOCAL=j.LOCAL;deadline=time.monotonic()+45
    while True:
        try:r1_probe.Client({**state,'port':18090},fixture);break
        except (OSError,AssertionError):
            assert inspect(secondary)['State']['Running'] and inspect(edge)['State']['Running']
            if time.monotonic()>deadline:raise
            time.sleep(.5)
    a,b=inspect(native.config['worker_id']),inspect(secondary);assert a['Id']!=b['Id'] and a['Image']==b['Image']==state['image_id']
    assert b['Config']['User']=='10001:10001' and b['HostConfig']['ReadonlyRootfs'] and not b['HostConfig'].get('Privileged')
    assert {m['Destination'] for m in b['Mounts']}=={'/run/secrets','/var/lib/modular'}
    private['state']='ready';f.write(MARKER,private);f.save('two-worker-topology.json',dict(result='ready_two_distinct_guarded_HTTP_workers',workers=[a['Id'],b['Id']],same_image=state['image_id'],database=state['active_db'],secondary_loopback_port=18090,operator_or_Docker_mounts=False,new_runtime_or_database_initialized=False));f.phase(state,'core21_HTTP_ready');f.guard(state)
    print('Second exact guarded native HTTP worker and loopback edge ready; no setup/migration or operator mounts.')
def verify():
    state,record,native=context();private=f.load(MARKER);assert state['phase']=='core21_HTTP_ready' and private['state']=='ready'
    fixture=f.load(j.LOCAL/'fixtures.json');baseline=f.load(j.LOCAL/'core21-HTTP-baseline-01.json');r1_probe.r1.r0.LOCAL=j.LOCAL
    operator=r1_probe.Client(state,fixture,'operator');alice=r1_probe.Client(state,fixture);other=r1_probe.Client({**state,'port':private['port']},fixture);bob=r1_probe.Client(state,fixture,'bob');worker=r1_probe.Client(state,fixture,'worker')
    role=json.loads(f.sql(state,'core21-HTTP-original-role-01',"SELECT jsonb_build_object('id',m.id,'role',m.role,'state',m.state) FROM mp_membership m JOIN mp_principal p ON p.id=m.principal_id WHERE p.public_id='"+fixture['users']['alice']['principal_id']+"' AND m.workspace_id="+str(fixture['workspaces']['A']['id'])+';'))
    assert role['role']=='editor' and role['state']=='active';private.update(state='verifying',original_A_membership=role);f.write(MARKER,private)
    def member(role=None,remove=False):
        body=dict(operation='remove' if remove else 'add',principal_id=fixture['users']['alice']['principal_id'])
        if not remove:body['role']=role
        status,value=operator.request('/api/v1/workspace/members',body,'A',{'X-CSRFToken':operator.csrf});assert status==200 and value['data']['changed'],('member',status,value.get('error',{}).get('code'))
    checks=[];error=None
    try:
        nonce=uuid4().hex
        for owner,workspace in [(alice,'A'),(bob,'B')]:
            entry=dict(owner='alice' if workspace=='A' else 'bob',workspace=workspace,key=uuid4().hex,delete_key=uuid4().hex,title='Owned core21 '+workspace+' '+nonce)
            private['owned_notes'].append(entry);f.write(MARKER,private)
            created=owner.call('create',dict(title=entry['title'],body='Temporary native authorization fixture'),workspace=workspace,key=entry['key']);entry.update(public_id=created['id'],revision=1);f.write(MARKER,private)
        a,b=private['owned_notes']
        rows=alice.native('search_read',[[['public_id','=',a['public_id']]]],dict(fields=['id','public_id','title']),workspace='A');assert len(rows)==1;a['native_id']=rows[0]['id'];f.write(MARKER,private)
        assert alice.native('write',[[a['native_id']],{'title':a['title']+' updated'}],dict(context={'expected_revision':1}),workspace='A') is True;a['revision']=2;f.write(MARKER,private)
        bob.call('update',dict(note_id=b['public_id'],expected_revision=1,title=b['title']+' updated'),workspace='B',key=uuid4().hex);b['revision']=2;f.write(MARKER,private)
        for client in [alice,other]:
            assert client.call('get',dict(note_id=a['public_id']),workspace='A')['revision']==2
            visible=client.native('search_read',[[]],dict(fields=['workspace_id','public_id']),workspace='B');assert all(row['workspace_id'][0]==fixture['workspaces']['B']['id'] for row in visible)
            client.call('create',dict(title='Denied viewer',body=''),workspace='B',expect=403,code='FORBIDDEN')
        bob.call('get',dict(note_id=a['public_id']),workspace='B',expect=404,code='NOT_FOUND');bob.native('read',[[a['native_id']],['title']],workspace='B',deny=True)
        alice.native('read',[[a['native_id']],['title']],workspace='B',deny=True)
        checks.append('positive native/REST CRUD, asymmetric roles and two-session workspace isolation')
        for forged_context in [{'uid':1,'su':True,'allowed_company_ids':[1],'force_company':1,'db':'mp_disposable_unselected'},{'mp_workspace_id':fixture['workspaces']['A']['id']},{'_mp_scope':{'role':'administrator'}},{'_mp_call_frame':{'principal_id':'administrator'}}]:
            alice.native('write',[[a['native_id']],{'title':'Denied forged context'}],dict(context=forged_context),workspace='B',deny=True)
        for workspace in [None,str(uuid4()),fixture['workspaces']['A']['public_id'].upper()]:alice.native('search_read',[[]],dict(fields=['title']),workspace=workspace,deny=True)
        alice.call('create',dict(title='Denied attribution',body='',workspace_id=fixture['workspaces']['B']['id']),workspace='A',expect=400,code='VALIDATION_FAILED')
        checks.append('forged actor/database/company/private context/workspace rejected')
        worker.call('list',dict(limit=10),workspace='A',expect=403,code='FORBIDDEN');worker.native('search_read',[[]],dict(fields=['title']),workspace='A',deny=True)
        status,value=operator.request('/api/v1/workspace/members',dict(operation='add',principal_id=fixture['users']['worker']['principal_id'],role='administrator'),'A',{'X-CSRFToken':operator.csrf});assert status==400 and value['error']['code']=='VALIDATION_FAILED'
        checks.append('service cookie has no credential-derived or administrator authority')
        for client in [alice,other]:client.native('read',[[a['native_id']],['title']],workspace='A')
        private['membership_change_started']=True;f.write(MARKER,private);member('viewer')
        for client in [alice,other]:
            client.native('write',[[a['native_id']],{'title':'Denied warmed viewer'}],dict(context={'expected_revision':2}),workspace='A',deny=True)
            client.call('create',dict(title='Denied warmed viewer',body=''),workspace='A',expect=403,code='FORBIDDEN')
        member(remove=True)
        for client in [alice,other,r1_probe.Client(state,fixture),r1_probe.Client({**state,'port':private['port']},fixture)]:
            client.native('read',[[a['native_id']],['title']],workspace='A',deny=True);client.call('get',dict(note_id=a['public_id']),workspace='A',expect=403,code='FORBIDDEN')
        member(role['role']);private['membership_change_started']=False;f.write(MARKER,private)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda c:c.call('get',dict(note_id=a['public_id']),workspace='A'),[alice,other]));assert all(r['revision']==2 for r in results)
        checks.append('committed demotion/revocation/restoration effective on first warmed/new request across two distinct guarded workers')
        for client,workspace in [(alice,'A'),(other,'B'),(bob,'B')]:
            views=client.native('get_views',workspace=workspace,kwargs=dict(views=[[False,'list'],[False,'form']],options=dict(toolbar=False)));assert {'list','form'}<=set(views['views'])
        checks.append('standard native Odoo list/form retained')
    except Exception as failure:
        error=type(failure).__name__;private['failure_type']=error;f.write(MARKER,private);raise
    finally:
        if private['membership_change_started']:
            member(role['role']);private['membership_change_started']=False;f.write(MARKER,private)
        for entry in private['owned_notes']:
            if entry.get('deleted') or not entry.get('public_id'):continue
            owner=alice if entry['owner']=='alice' else bob
            current=owner.call('get',dict(note_id=entry['public_id']),workspace=entry['workspace']);assert current['title'].startswith(entry['title'])
            owner.call('delete',dict(note_id=entry['public_id'],expected_revision=current['revision']),workspace=entry['workspace'],key=entry['delete_key']);entry['deleted']=True;f.write(MARKER,private)
    assert error is None
    after=snapshot(state,'core21-HTTP-after-01')
    for key in ['notes','boards','projections','groups']:assert after[key]==baseline[key],key
    # Membership endpoints legitimately advance audit fields and generation;
    # authority and row identities are the exact original ones.
    keep=lambda rows:[{k:v for k,v in row.items() if k not in {'write_date','write_uid'}} for row in rows]
    assert keep(after['memberships'])==keep(baseline['memberships'])
    by_id={event['id']:event for event in after['events']};assert all(by_id[e['id']]==e for e in baseline['events'])
    assert len(after['events'])==len(baseline['events'])+6
    private.update(state='HTTP_qualified_needs_stop',checks=checks);f.write(MARKER,private)
    f.save('HTTP-qualified.json',dict(result='passed_installed_core21_two_worker_HTTP',image_id=state['image_id'],inventory_digest=state['inventory_digest'],generation=30,checks=checks,worker_ids=f.load(OUT/'two-worker-topology.json')['workers'],original_business_projection_groups_and_membership_authority_exact=True,only_two_owned_notes_created_updated_deleted=True,original_producer_history_exact=True,new_owned_events_retained=6,native_Odoo_list_form_default=True,no_new_core_route_or_UI=True,limits=['Existing frontend transport/cache/typed-Scope/SQL logic retained; earlier real two-tab browser evidence reused, final browser/event/accessibility qualification still required.','Helper worker/edge must be stopped before later lifecycle mutations.']))
    f.phase(state,'core21_HTTP_qualified_needs_stop');f.guard(state);print('Installed identity1.2 native/API/asymmetric/forged/service/two-worker warm-revocation checks pass; original data/authority restored.')
def stop():
    state,record,native=context();private=f.load(MARKER);assert private['state']=='HTTP_qualified_needs_stop' and state['phase']=='core21_HTTP_qualified_needs_stop'
    for key in ['edge','secondary']:
        info=inspect(private[key]);assert info['State']['Running'] and info['Config']['Labels']['com.modular.disposable']==state['project']
        f.command('core21-HTTP-stop-'+key+'-01',['docker','stop','--time','30',info['Id']]);after=inspect(info['Id']);assert not after['State']['Running'] and after['State']['ExitCode']==0
    private['state']='completed';f.write(MARKER,private);f.phase(state,'core21_HTTP_qualified');f.guard(state);f.save('helpers-stopped.json',dict(result='passed',owned_secondary_and_edge_stopped_exit0=True,primary_worker_unchanged=native.config['worker_id'],no_database_reset_or_container_deletion=True));print('Owned secondary HTTP helpers stopped cleanly; primary fixture remains live.')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['setup','verify','stop']);args=parser.parse_args();globals()[args.action]()
