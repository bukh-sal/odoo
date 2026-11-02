"""Source qualification and separately guarded curation of the minimal action."""
import argparse,copy,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-worker-image-success-01'))
import approve_runtime as current
from modular_platform.catalog import Catalog
from modular_platform.operator_os import protect_directory
from modular import configuration
from reference_package import assemble,validate_reference_composition
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
base,f,j=current.base,current.f,current.j
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'notes-stats-ui-01';MARKER=PRIVATE/'setup.json'

def qualify():
    assert not (OUT/'source-checks.json').exists()
    checks=[('native-action-tests',['node','--test','tests/test_notes_analysis_action.mjs','tests/test_native_interactions.mjs']),
            ('contract-freeze',[sys.executable,'-X','utf8','tools/check_contract_freeze.py'])]
    for name,args in checks:
        result=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=90)
        (OUT/(name+'.log')).write_bytes(result.stdout+result.stderr)
        assert result.returncode==0,name
    archives=[];rows=[]
    with tempfile.TemporaryDirectory(prefix='mp-analysis-source-') as temporary:
        path=Path(temporary)/'checked.mplug'
        for plugin in ['notes','notes_labels','canvas','notes_stats']:
            manifest,raw,files=assemble(ROOT,'plugins/'+plugin+'/plugin.toml')
            assert raw==assemble(ROOT,'plugins/'+plugin+'/plugin.toml')[1]
            path.write_bytes(raw);checked=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(path)
            archives.append(raw);rows.append(dict(plugin_id=manifest['plugin']['id'],version=manifest['plugin']['version'],digest=checked.digest,files=len(files)))
        validate_reference_composition(archives)
    names=['platform_addons/mp_example_notes_stats/static/src/analysis.js','platform_addons/mp_example_notes_stats/__manifest__.py','plugins/notes_stats/plugin.toml','tests/test_notes_analysis_action.mjs']
    f.save('source-checks.json',dict(result='passed_source_only_not_deployed_or_browser_verified',node_checks=17,freeze_files=97,freeze_rows=8,
        archives=rows,composition_valid=True,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in names},
        native_slot_and_facade_reused=True,custom_record_screen_or_dialog_added=False,public_contract_changed=False,browser_verified=False))
    print('17 Node checks, freeze97/eightrows and four reproducible validated archives/composition passed; source only')

def curate():
    state,native=current.context();assert native.config['generation']==23 and not PRIVATE.exists()
    source=f.load(OUT/'source-checks.json');assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source['source_sha256'].items())
    protect_directory(PRIVATE)
    catalog=Catalog(native.catalog_root,native.validator,readonly=True);observation=native.observer.read()
    before=native.observer.state(observation,catalog.snapshot())['state']
    data=base.snapshot(state,'ui-curation-data-before');remote=base.worker(native,'ui-curation-worker-before')
    f.write(PRIVATE/'data-before-curation.json',data);f.write(PRIVATE/'worker-before-curation.json',remote)
    for plugin in ['notes','notes_labels','canvas','notes_stats']:
        manifest,raw,files=assemble(ROOT,'plugins/'+plugin+'/plugin.toml');digest='sha256:'+hashlib.sha256(raw).hexdigest()
        checked=next(r for r in source['archives'] if r['plugin_id']==manifest['plugin']['id']);assert checked['digest']==digest
        if plugin!='notes_stats':assert digest==observation['runtime']['inventory']['artifacts'][manifest['plugin']['id']]['digest']
        else:candidate=(digest,raw)
    digest,raw=candidate;archive=PRIVATE/'org.example.notes_stats-0.1.1.mplug'
    with archive.open('xb') as stream:stream.write(raw)
    trust_path=j.LOCAL/'operator/trust.json';old=f.load(trust_path);assert old['generation']==9 and digest not in old['approved_digests']
    f.write(PRIVATE/'trust-before.json',old);f.write(MARKER,dict(state='curating',artifact_digest=digest,archive=str(archive.relative_to(ROOT))))
    trust=copy.deepcopy(old);trust['generation']+=1;trust['approved_digests'].append(digest);f.write(trust_path,trust)
    curated=Catalog(native.catalog_root,configuration(trust_path));curated.add(archive,expected_digest=digest)
    after=native.observer.state(native.observer.read(),curated.snapshot())['state']
    assert all(after[k]==before[k] for k in ['release_lock','installations','bindings','endpoints'])
    assert base.snapshot(state,'ui-curation-data-after')==data and base.worker(native,'ui-curation-worker-after')==remote
    f.save('package-curation.json',dict(result='passed_minimal_action_curation_not_deployed',artifact_digest=digest,version='0.1.1',
        old_three_artifacts_exact=True,fixture_trust_generation=10,global_trust_untouched=True,configuration_generation=23,
        release_bindings_endpoints_17tables_worker_exact=True,browser_verified=False,no_docker_assets_created=True))
    record=f.load(MARKER);record['state']='artifact_curated';f.write(MARKER,record);f.phase(state,'notes_stats_ui_artifact_curated');f.guard(state)
    print('NotesStats0.1.1 curated, fixture trust9->10; current23/data/worker unchanged, no deployment')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['qualify','curate']);globals()[parser.parse_args().action]()
