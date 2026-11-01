"""Actual same-DB new-image upgrade preservation before the recovered effect."""
import hashlib,json,re,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from activate import context,j,f,MARKER
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
import r1_probe
state,record,native=context();assert state['phase']=='core10_completed_needs_verification' and record['state']=='completed_needs_verification'
assert native.config['generation']==6 and native.config['image_id']==record['image_id']
operation=record['operation_id'];stage=native.store.root/'stages'/operation;checkpoint=native.store.root/'checkpoints'/operation
manifest=f.load(checkpoint/'manifest.json');fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
assert manifest['dispatch_profile']==fence['after'] and fence['after']['control']['generation']==29 and ready['control']['generation']==30
assert enabled['before']==ready and enabled['after']['control']['state']=='enabled' and enabled['after']['control']['generation']==31
current=DispatchMaintenance(native).inspect();assert current==enabled['after'] and current['job_states']==dict(completed=2,dead_letter=2,pending=1)
for table in ['mp_outbox','mp_event_consumption','mp_event_consumer_state']:
    assert current['tables'][table]==manifest['dispatch_profile']['tables'][table]

def copy(raw,table):
    found=re.search(rb'^COPY public\.'+table.encode()+rb' \(([^\n]+)\) FROM stdin;\n(.*?)^\\\.$',raw,re.M|re.S);assert found
    return found[1],sorted(l for l in found[2].splitlines() if l)

def pair(table):
    a=f.command('core10-backup-'+table,['docker','exec','-i',state['project']+'-db-1','pg_restore','--data-only','--no-owner','--no-privileges','--schema=public','--table='+table,'-f','-'],input=(checkpoint/'database.dump').read_bytes())
    b=f.command('core10-current-'+table,['docker','exec',state['project']+'-db-1','pg_dump','-U','postgres','--data-only','--no-owner','--no-privileges','--table=public.'+table,state['active_db']])
    return copy(a,table),copy(b,table)

business=[]
for table in ['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary']:
    a,b=pair(table);assert a==b
    business.append(dict(table=table,rows=len(a[1]),sha256=hashlib.sha256(a[0]+b'\n'+b'\n'.join(a[1])).hexdigest(),checkpoint_COPY_exact=True))
a,b=pair('mp_job');assert a[0]==b[0];columns=[c.strip() for c in a[0].decode().split(',')]
def rows(values):return {p[columns.index('public_id')]:dict(zip(columns,p)) for p in [line.decode().split('\t') for line in values]}
before,after=rows(a[1]),rows(b[1]);seed=f.load(j.LOCAL/'core10-seed-01.json');assert before.keys()==after.keys() and len(before)==5
for ident,old in before.items():
    new=after[ident]
    for key in ['actor_id','workspace_id','installation_id','handler','handler_version','effect_mode','idempotency_key','payload','input_digest','result','attempts','max_attempts','deadline_at']:
        assert old[key]==new[key],(ident,key)
    if ident==seed['job_id']:assert old['state']=='held' and new['state']=='pending' and int(new['claim_generation'])>int(old['claim_generation'])
    else:assert old['state']==new['state'] and old['finished_at']==new['finished_at'] and old['error_code']==new['error_code']
args,_=native._child(operation,'fixture-filestore-check',network=False)
files=json.loads(f.command('core10-current-filestore-01',args+['-c',FILE_OBSERVATION,state['active_db']]))
expected={};prefix='filestore/'+state['active_db']+'/'
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
    for member in archive:
        if member.isfile() and member.name.startswith(prefix):expected[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert all(files.get(name)==digest for name,digest in expected.items()) and len(expected)==42
assets=f.load(stage/'assets.json');assert assets['generation']==6 and assets['inventory_digest']==record['inventory_digest']
old_assets=f.load(native.store.root/'recoveries/8090a1a8-13ee-42e2-9980-9369a79bd78a/assets.json')
assert next(a['sha256'] for a in assets['assets'] if a['mimetype']=='application/javascript')!=next(a['sha256'] for a in old_assets['assets'] if a['mimetype']=='application/javascript')
r1_probe.r1.r0.LOCAL=j.LOCAL;fixture=f.load(j.LOCAL/'fixtures.json');client=r1_probe.Client(state,fixture)
for workspace in ['A','B','C']:
    views=client.native('get_views',workspace=workspace,kwargs=dict(views=[[False,'list'],[False,'form']],options=dict(toolbar=False)));assert {'list','form'}<=set(views['views'])
assert client.call('get',dict(note_id=seed['note_id']),workspace='C')['revision']==1
client.call('get',dict(note_id=seed['note_id']),workspace='A',expect=404,code='NOT_FOUND')
verified=[]
for origin,items in [('retained',old_assets['assets']),('new',assets['assets'])]:
    for item in items:
        url=client.base+item['url']
        with client.http.open(url,timeout=30) as response:
            assert response.status==200 and response.geturl()==url;raw=response.read()
        assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'];verified.append(dict(kind=origin,**item))
status=native.store.status(operation);assert status['state']=='completed' and status['traffic_resumed']
proof=dict(result='passed_real_populated_core_upgrade_before_job_effect',operation_id=operation,generation=6,image_id=record['image_id'],inventory_digest=record['inventory_digest'],same_database=True,all_plugin_artifacts_versions_installations_bindings_exact=True,business_COPY_exact=business,all_five_job_ID_actor_input_key_first_trace_budget_and_saved_results_preserved=True,claimed_job_requeued_within_original_policy=True,dispatch_generations=[28,29,30,31],original_producer_and_consumer_history_exact=True,retained_filestore_files=len(expected),new_asset_bytes_differ=True,old_and_new_asset_URLs_nonredirect_exact=verified,native_Odoo_list_form=['A','B','C'],pending_note_scoped_HTTP_and_foreign_denial=True,limits=['Native recovered job/new-image completed semantic retry/history probes are next, not covered by this checkpoint.','Notes0.2.6 remains exact; versioned Notes0.2.7 batch fix and full event/browser/external qualification remain.'])
f.save('upgrade-preservation.json',proof);record['state']='upgrade_preserved_needs_job_history';f.write(MARKER,record);f.phase(state,'core10_upgrade_preserved');f.guard(state)
print('Real populated core upgrade preserved business/job/history/files; new and retained assets/native views pass.')
