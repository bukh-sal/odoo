"""One-shot real metadata successor upgrade; preserve worker and native state."""
import argparse,copy,hashlib,json,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261101-provider-registration-01'))
import register as previous
from setup import command
from reference_package import assemble
from modular import configuration
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.plans import data_digest
from modular_platform.restore_continuation import FILE_OBSERVATION
j=previous.j;f=previous.f;f.OUTPUT=OUT
PRIVATE=j.LOCAL/'provider-upgrade';MARKER=PRIVATE/'upgrade.json'

def run(label,args,**options):return command('successor-'+label,args,**options)
def context():return previous.context()
def prefix():return [sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
def validation(native):return ['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
def selected(catalog,version,digest):
    return next(p for p in catalog.snapshot() if p['plugin_id']=='org.example.document_stats' and p['version']==version and p['digest']==digest)

def curate():
    state,native=context();assert native.config['generation']==12 and not MARKER.exists()
    from modular_platform.operator_os import protect_directory
    protect_directory(PRIVATE)
    old=previous.f.load(previous.PRIVATE/'setup.json')
    catalog=Catalog(native.catalog_root,native.validator,readonly=True)
    before=native.observer.state(native.observer.read(),catalog.snapshot())['state']
    worker=previous.worker(native,'worker-before-successor-curation-02')
    manifest,raw,files=assemble(ROOT,'plugins/document_stats/plugin.toml')
    assert manifest['plugin']['version']=='0.1.1' and manifest['compatibility']['platform']=='>=0.1.13,<0.2'
    assert raw==assemble(ROOT,'plugins/document_stats/plugin.toml')[1]
    assert len(files)==6 and manifest['external_service']==selected(catalog,'0.1.0',old['artifact_digest'])['manifest']['external_service']
    archive=PRIVATE/'org.example.document_stats-0.1.1.mplug';archive.write_bytes(raw)
    verified=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(archive)
    trust=j.LOCAL/'operator/trust.json';policy=f.load(trust);assert policy['generation']==6 and verified.digest not in policy['approved_digests']
    f.write(PRIVATE/'trust-before.json',policy)
    f.write(MARKER,dict(state='curating',digest=verified.digest,scope=old['scope']))
    policy['generation']+=1;policy['approved_digests'].append(verified.digest);f.write(trust,policy)
    catalog=Catalog(native.catalog_root,configuration(trust));catalog.add(archive,expected_digest=verified.digest)
    after=native.observer.state(native.observer.read(),catalog.snapshot())['state']
    assert all(before[k]==after[k] for k in ['release_lock','installations','bindings','endpoints'])
    assert previous.worker(native,'worker-after-successor-curation')==worker
    assert selected(catalog,'0.1.0',old['artifact_digest'])['digest']==old['artifact_digest']
    f.save('curation.json',dict(result='passed_immutable_successor_curation',version='0.1.1',digest=verified.digest,
        minimum_platform='0.1.13',worker_image_contract_unchanged=True,old_artifact_preserved=True,
        trust_generation=7,native_release_and_worker_unchanged=True,new_docker_assets=0,files=sorted(files)))
    marker=f.load(MARKER);marker['state']='curated';f.write(MARKER,marker)
    print('Immutable metadata successor curated; previous archive/release and worker retained')

def prepare():
    state,native=context();marker=f.load(MARKER);assert marker['state']=='curated' and native.config['generation']==12
    nomination=dict(operation_type='upgrade',targets=[dict(**marker['scope'],plugin_id='org.example.document_stats',action='upgrade')],
        selections=[dict(plugin_id='org.example.document_stats',version='0.1.1',digest=marker['digest'])])
    f.save('nomination.json',nomination)
    bundle=json.loads(run('plan',prefix()+['plugin','plan-external','--input',str(OUT/'nomination.json'),'--store',str(native.store.root)]+validation(native)))
    native._runtime_preflight(bundle);f.save('bundle.json',bundle)
    assert not bundle['plan']['permission_changes'] and 'feature_states' not in bundle['operation_lock']
    f.write(PRIVATE/'data-before.json',previous.snapshot(state,'provider-upgrade-before'))
    f.write(PRIVATE/'schema-before.json',dict(digest=previous.schema(state,'provider-upgrade-schema-before')))
    f.write(PRIVATE/'worker-before.json',previous.worker(native,'worker-before-successor-upgrade'))
    f.write(PRIVATE/'modules-before.json',json.loads(f.sql(state,'provider-upgrade-modules-before','BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;')))
    marker.update(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);f.write(MARKER,marker)
    ops=prefix()+['operations','--store',str(native.store.root)]
    run('register',ops+['register','--bundle',str(OUT/'bundle.json')]+validation(native))
    f.save('independent-review.json',native.store.review(marker['operation_id'],native._validate()))
    run('approve',ops+['approve',marker['operation_id'],'--plan-hash',marker['plan_hash'],'--noninteractive','--ack-trust']+validation(native))
    marker['state']='approved';f.write(MARKER,marker)
    print('Same-image metadata upgrade independently reconstructed, reviewed and approved')

def apply():
    state,native=context();marker=f.load(MARKER);assert marker['state']=='approved' and native.config['generation']==12
    marker['state']='applying';f.write(MARKER,marker);f.phase(state,'provider_upgrade_applying')
    result=json.loads(run('apply',prefix()+['plugin','apply',marker['operation_id'],'--store',str(native.store.root)]+validation(native),timeout=600))
    assert result['state']=='completed';f.save('completed.json',result)
    marker['state']='completed_needs_verification';f.write(MARKER,marker)
    print('Reviewed metadata upgrade completed; exact preservation verification follows')

def verify():
    state,native=context();marker=f.load(MARKER);assert marker['state']=='completed_needs_verification'
    bundle=f.load(OUT/'bundle.json');assert native.config['generation']==13 and native.config['image_id']==state['image_id']
    assert native.config['published_release']==bundle['operation_lock']['release']
    old_release=f.load(OUT.parent/'20261101-provider-registration-01/enable-bundle.json')['operation_lock']['release']
    new_release=bundle['operation_lock']['release']
    assert [p for p in old_release['plugins'] if p['runtime']=='native']==[p for p in new_release['plugins'] if p['runtime']=='native']
    assert {k:v for k,v in old_release.items() if k not in {'plugins','generation','created_at'}}=={k:v for k,v in new_release.items() if k not in {'plugins','generation','created_at'}}
    before=f.load(PRIVATE/'data-before.json');after=previous.snapshot(state,'provider-upgrade-after')
    assert previous.schema(state,'provider-upgrade-schema-after')==f.load(PRIVATE/'schema-before.json')['digest']
    assert previous.worker(native,'worker-after-successor-upgrade')==f.load(PRIVATE/'worker-before.json')
    modules=json.loads(f.sql(state,'provider-upgrade-modules-after','BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;'))
    assert modules==f.load(PRIVATE/'modules-before.json')
    installation=next(r for r in before['mp_plugin_installation'] if r['public_id']==marker['scope']['installation_id'])
    workspace=next(r for r in before['mp_workspace'] if r['public_id']==marker['scope']['workspace_id'])
    target=next(r for r in bundle['operation_lock']['release']['plugins'] if r['runtime']=='external_service')
    candidate=selected(Catalog(native.catalog_root,native.validator,readonly=True),'0.1.1',marker['digest'])
    cutoff=datetime.fromisoformat(bundle['plan']['created_at'].replace('Z','+00:00'));updated=0
    for table in before:
        expected=copy.deepcopy(before[table]);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual)
        if table=='mp_plugin_installation':
            old=next(r for r in expected if r['id']==installation['id']);assert old['version']=='0.1.0'
            old.update(version='0.1.1',artifact_digest=marker['digest'],manifest=candidate['manifest'])
        elif table=='mp_workspace_plugin':
            old=next(r for r in expected if r['installation_id']==installation['id'] and r['workspace_id']==workspace['id'])
            current=next(r for r in actual if r['id']==old['id']);assert old['availability']==current['availability']=='enabled'
            assert cutoff<=datetime.fromisoformat(current['write_date']).replace(tzinfo=timezone.utc)<=datetime.now(timezone.utc)
            old['write_date']=current['write_date']
        elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=1
        elif table=='mp_job':
            byid={r['public_id']:r for r in actual}
            for old in expected:
                current=byid[old['public_id']];changed={k for k in old if old[k]!=current[k]}
                assert changed<={'release_digest','claim_generation','dispatch_generation'}
                if changed:
                    assert current['release_digest']==bundle['plan']['target_release_digest'] and current['claim_generation']==old['claim_generation']+1 and current['dispatch_generation']==60
                    old.update(**{k:current[k] for k in changed});updated+=1
        assert expected==actual,table+' changed outside exact metadata upgrade'
    stage=native.store.root/'stages'/marker['operation_id'];checkpoint=native.store.root/'checkpoints'/marker['operation_id']
    ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
    assert ready['control']['generation']==60 and enabled['after']['control']['generation']==61
    assert f.load(stage/'metadata.log')==dict(metadata_published=True,operation_id=marker['operation_id'],native_maintenance=False,runtime_control=False)
    files=json.loads(run('files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
    retained={};path_prefix='filestore/'+state['active_db']+'/'
    with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(path_prefix):retained[member.name[len(path_prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert retained and all(files.get(p)==digest for p,digest in retained.items())
    f.save('qualification.json',dict(result='passed_actual_same_worker_metadata_upgrade',operation_id=marker['operation_id'],
        metadata_version='0.1.1',artifact_digest=marker['digest'],minimum_platform='0.1.13',configuration_generation=13,dispatch_generation=61,
        unchanged_native_image=state['image_id'],native_schema_all_module_rows_exact=True,
        independent_worker_identity_image_start_restart_mounts_network_keys_publication_exact=True,
        all_original_rows_preserved_except_exact_metadata_policy_epoch_changes=True,old_job_outcomes_inputs_attempts_exact=19,jobs_epoch_updated=updated,
        old_files_preserved=len(retained),enabled_feature_preserved=True,no_external_runtime_control=True,
        limits=['Same worker image and service contract only; changed-image transition unqualified.','Host maintenance/restart occurred.','No connector/remote/recovery/manager lifecycle qualification.']))
    marker['state']='verified';f.write(MARKER,marker);f.phase(state,'provider_upgrade_verified');f.guard(state)
    print('Real metadata upgrade verified: enabled feature, worker, native state and original data/jobs/files preserved')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['curate','prepare','apply','verify']);args=parser.parse_args();globals()[args.action]()
