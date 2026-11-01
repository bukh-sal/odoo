"""Read-only installed core preservation, then one normal original-actor job."""
import argparse,hashlib,json,re,sys,tarfile
from pathlib import Path
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT))
from activate import ROOT,j,f,MARKER,context
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION

def preservation():
    state,native=context();record=f.load(MARKER);assert record['state']=='completed_needs_qualification' and native.config['generation']==9
    operation=record['operation_id'];checkpoint=native.store.root/'checkpoints'/operation;stage=native.store.root/'stages'/operation
    fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
    assert fence['after']['control']['generation']==38 and ready['control']['generation']==39 and enabled['after']['control']['generation']==40
    current=DispatchMaintenance(native).inspect();assert current==enabled['after'] and current['job_states']==dict(completed=3,dead_letter=2)
    def parse(raw,table):
        match=re.search(rb'COPY public\.'+table.encode()+rb' \((.*?)\) FROM stdin;\n(.*?)\\\.\n',raw,re.S)
        assert match;return match[1].decode().split(', '),sorted(line.decode().split('\t') for line in match[2].splitlines() if line)
    counts={}
    for table in ['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_outbox','mp_job']:
        old=f.command('core11-backup-'+table,['docker','exec','-i',state['project']+'-db-1','pg_restore','--data-only','--no-owner','--no-privileges','--schema=public','--table='+table,'-f','-'],input=(checkpoint/'database.dump').read_bytes())
        new=f.command('core11-current-'+table,['docker','exec',state['project']+'-db-1','pg_dump','-U','postgres','--data-only','--no-owner','--no-privileges','--table=public.'+table,state['active_db']])
        a,b=parse(old,table),parse(new,table);assert a[0]==b[0];counts[table]=len(a[1])
        if table=='mp_job':
            allowed={'release_digest','claim_generation','dispatch_generation'}
            project=lambda rows:sorted([{key:value for key,value in zip(a[0],row) if key not in allowed} for row in rows],key=lambda r:r['public_id'])
            assert project(a[1])==project(b[1]) and len(a[1])==len(b[1])==5
        else:assert a==b
    assert counts==dict(mp_example_note=27,mp_example_canvas_board=0,mp_example_note_event_summary=3,mp_outbox=44,mp_job=5)
    args,_=native._child(operation,'core11-fixture-files',network=False)
    files=json.loads(f.command('core11-current-files',args+['-c',FILE_OBSERVATION,state['active_db']]))
    expected={};prefix='filestore/'+state['active_db']+'/'
    with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(prefix):expected[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert all(files.get(name)==digest for name,digest in expected.items())
    cfg=j.LOCAL/'operator/worker-target.json';worker=f.load(cfg);assert worker['helper_image']=='sha256:4262dffe7d3cdb316d7434a42c54ad1f918d94c4c07f3df860b17d7fcec4e8af'
    before=hashlib.sha256(cfg.read_bytes()).hexdigest();worker['helper_image']=native.config['image_id'];f.write(cfg,worker)
    f.save('preservation.json',dict(result='passed_installed_core11_upgrade_preservation',image_id=state['image_id'],generation=9,dispatch_generation=40,same_database=True,counts_exact=counts,all_original_job_fields_except_explicit_generations_and_release_exact=True,retained_files=len(expected),plugin_installations_and_bindings_exact=True,worker_configuration_update=dict(previous_sha256=before,current_sha256=hashlib.sha256(cfg.read_bytes()).hexdigest(),only_field='helper_image',reason='Use the normally approved current core image for isolated operator helpers; runtime authority generation2 retained'),limits=['JOB01/02 targeted lease/error/revocation requalification and actual external Notes bridge still required.']))
    record['state']='preservation_verified';f.write(MARKER,record);f.phase(state,'core11_preservation_verified');f.guard(state);print('Installed core1.11 preserves all original Notes/events/jobs/files; normal job helper pin updated to approved image')

def job():
    state,native=context();record=f.load(MARKER);assert record['state']=='preservation_verified'
    private=j.LOCAL/'core11-normal-cli-job.json';assert not private.exists()
    code="""import json
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core import job_dispatch as jobs
native=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['C']['public_id'])
b=FIXTURE['bindings']['C'];frame=CallFrame(FIXTURE['users']['alice']['principal_id'],b['workspace_id'],b['site_id'],b['consumer_installation_id'],'org.example.notes',())
native=native(context={**native.context,'_mp_call_frame':frame});note=native['mp.example.note'].search([],limit=1);assert note
ident=jobs.enqueue_bound(native,'documents','org.example.notes:inspect_revision',dict(note_id=note.public_id,expected_revision=note.revision),uuid4().hex)
value=dict(job_id=ident,note_id=note.public_id,revision=note.revision,actor_id=native.context['_mp_scope'].principal_id)
env.cr.commit();print('MP_CORE11_JOB='+json.dumps(value))
"""
    raw=f.native(state,'core11-normal-job-seed',[],'FIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\n'+code)
    rows=[json.loads(line.split('MP_CORE11_JOB=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CORE11_JOB=')];assert len(rows)==1;f.write(private,rows[0])
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json'),'worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json')]
    result=json.loads(f.command('core11-normal-job-once',prefix+['run-job-once'],timeout=180));assert any(row.get('job_id')==rows[0]['job_id'] and row['state']=='completed' for row in result['results'])
    check="""import json
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import job_dispatch as jobs
native=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['C']['public_id'])
value=jobs.status(native,JOB['job_id']);assert value['state']=='completed' and value['attempts']==1 and value['result']==dict(note_id=JOB['note_id'],revision=JOB['revision'])
env.cr.execute('SELECT actor_id FROM mp_job WHERE public_id=%s',[JOB['job_id']]);assert env.cr.fetchone()[0]==JOB['actor_id']
print('MP_CORE11_COMPLETE='+json.dumps(dict(state=value['state'],attempts=value['attempts'],original_actor=True)))
env.cr.rollback()
"""
    raw=f.native(state,'core11-normal-job-status',[],'FIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\nJOB='+repr(rows[0])+'\n'+check)
    proof=[json.loads(line.split('MP_CORE11_COMPLETE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CORE11_COMPLETE=')];assert len(proof)==1
    f.save('normal-job.json',dict(result='passed_actual_installed_normal_operator_job',**proof[0],job_id=rows[0]['job_id'],runner_source_substitution=False,normal_cli=True,authority_mount_read_only=True,no_business_record_mutation=True,retained_new_read_only_job=True,limits=['This is native inspect_revision, not remote Notes statistics. Lease/kill/error-path requalification and external metadata/connector installation remain required.']))
    record['state']='normal_native_job_verified';f.write(MARKER,record);f.phase(state,'core11_normal_native_job_verified');f.guard(state);print('Actual normal CLI/installed guarded runner completed original-actor read-only job once; no source substitution')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['preservation','job']);args=parser.parse_args();globals()[args.action]()
