"""Read-only checkpoint comparison after the separate populated plugin upgrade."""
import hashlib,json,re,sys,tarfile
from pathlib import Path
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT))
from activate import context,j,f,ROOT
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
state,record,native=context();assert state['phase']=='notes7_native_batch_verified' and native.config['generation']==8
checkpoint=native.store.root/'checkpoints'/record['operation_id'];stage=native.store.root/'stages'/record['operation_id']
manifest=f.load(checkpoint/'manifest.json');fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
assert manifest['dispatch_profile']==fence['after'] and fence['after']['control']['generation']==35 and ready['control']['generation']==36 and enabled['after']['control']['generation']==37
current=DispatchMaintenance(native).inspect();assert current['control']==enabled['after']['control'] and current['job_states']==dict(completed=3,dead_letter=2)
for name in ['mp_job','mp_event_consumption','mp_event_consumer_state','mp_event_delivery','mp_event_subscription','mp_outbox']:assert current['tables'][name]==enabled['after']['tables'][name]

def parse(raw,table):
    match=re.search(rb'^COPY public\.'+table.encode()+rb' \(([^\n]+)\) FROM stdin;\n(.*?)^\\\.$',raw,re.M|re.S);assert match
    return match[1].decode().split(', '),sorted(line.decode().split('\t') for line in match[2].splitlines() if line)
def pair(table):
    old=f.command('notes7-backup-'+table,['docker','exec','-i',state['project']+'-db-1','pg_restore','--data-only','--no-owner','--no-privileges','--schema=public','--table='+table,'-f','-'],input=(checkpoint/'database.dump').read_bytes())
    new=f.command('notes7-current-'+table,['docker','exec',state['project']+'-db-1','pg_dump','-U','postgres','--data-only','--no-owner','--no-privileges','--table=public.'+table,state['active_db']])
    a,b=parse(old,table),parse(new,table);assert a[0]==b[0];return a,b
rows={}
for table in ['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_outbox']:
    a,b=pair(table);assert a==b;rows[table]=len(a[1])
assert rows==dict(mp_example_note=25,mp_example_canvas_board=0,mp_example_note_event_summary=3,mp_outbox=42)
a,b=pair('mp_job');cols=a[0];allowed={'release_digest','claim_generation','dispatch_generation'}
project=lambda row:{key:value for key,value in zip(cols,row) if key not in allowed}
assert len(a[1])==len(b[1])==5 and sorted((project(row) for row in a[1]),key=lambda row:row['public_id'])==sorted((project(row) for row in b[1]),key=lambda row:row['public_id'])
args,_=native._child(record['operation_id'],'notes7-fixture-files',network=False)
files=json.loads(f.command('notes7-files-after-01',args+['-c',FILE_OBSERVATION,state['active_db']]))
prefix='filestore/'+state['active_db']+'/';expected={}
with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
    for item in archive:
        if item.isfile() and item.name.startswith(prefix):expected[item.name[len(prefix):]]=hashlib.sha256(archive.extractfile(item).read()).hexdigest()
assert len(expected)>=44 and all(files.get(name)==digest for name,digest in expected.items())
before=f.load(OUT/'state-before.json');after=f.load(OUT/'state-after.json');assert before['bindings']==after['bindings']
for old in before['installations']:
    new=next(i for i in after['installations'] if (i['installation_id'],i['workspace_id'])==(old['installation_id'],old['workspace_id']))
    if old['plugin_id']!='org.example.notes':assert new==old
    else:
        for key in ['installation_id','site_id','workspace_id','plugin_id','state','feature_state','metadata_state']:assert old[key]==new[key]
# Native list/form remain the default, not a new record UI.
fixture=f.load(j.LOCAL/'fixtures.json')
code='import json\nfrom odoo import api\nfrom odoo.addons.mp_identity.scopes import scoped_environment\nFIXTURE='+repr(fixture)+'\n'
code+="env.cr.rollback()\nresults=[]\nfor workspace in ['A','B','C']:\n native=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])\n model=native['mp.example.note']\n for kind in ['list','form']:\n  view=model.get_view(view_type=kind)\n  assert view['type']==kind and '<'+kind in view['arch']\n results.append(workspace)\nprint('MP_NOTES_VIEWS='+json.dumps(dict(workspaces=results,native_Odoo_list_form_default=True)))\nenv.cr.rollback()"
raw=f.native(state,'notes7-native-views-01',[],code);views=[json.loads(l.split('MP_NOTES_VIEWS=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_NOTES_VIEWS=')];assert len(views)==1
f.save('preservation.json',dict(result='passed_separate_populated_notes7_upgrade',image_id=state['image_id'],inventory_digest=state['inventory_digest'],generation=8,operation_id=record['operation_id'],dispatch_generations=[34,35,36,37],same_database=True,exact_checkpoint_rows=rows,all_five_job_columns_exact_except_explicit_release_claim_dispatch_generations=True,all_old_files_retained=len(expected),other_installations_and_all_bindings_exact=True,notes_workspace_authority_preserved=True,native_views=views[0],native_batch_cases=10,all_batch_writes_rolled_back=True,source_substitution=False,limits=['Actual deployed event host/bus/browser still required; external worker/effects/credential and G7 remain. No full ID-03/EVT gate credit from this bounded prerequisite.']))
record['state']='plugin_upgrade_native_qualified_needs_host';f.write(j.LOCAL/'notes7-upgrade-01.json',record);f.phase(state,'notes7_native_qualified_needs_host');f.guard(state)
print('Actual Notes-only plugin upgrade preserves25Notes/42producer rows/5jobs/oldfiles/bindings/authority; native batch and Odoo views pass.')
