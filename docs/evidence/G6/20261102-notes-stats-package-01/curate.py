"""Curate the minimal native connector; no runtime install or worker controls."""
import copy,hashlib,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-core15-upgrade-01'))
import activate as base
from modular_platform.catalog import Catalog
from modular_platform.operator_os import protect_directory
from modular import configuration
from reference_package import assemble,validate_reference_composition
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
j=base.j;f=base.f;f.OUTPUT=OUT;PRIVATE=j.LOCAL/'notes-stats-install-01';MARKER=PRIVATE/'setup.json'

state,native=base.context();assert native.config['generation']==17 and not PRIVATE.exists();protect_directory(PRIVATE)
catalog=Catalog(native.catalog_root,native.validator,readonly=True);observation=native.observer.read()
before=native.observer.state(observation,catalog.snapshot())['state']
provider=next(r for r in before['installations'] if r['plugin_id']=='org.example.document_stats')
assert provider['state']=='installed' and provider['feature_state']=='enabled'
data=base.snapshot(state,'notes-stats-curation-data-before');remote=base.worker(native,'notes-stats-curation-worker-before')
f.write(PRIVATE/'data-before-curation.json',data);f.write(PRIVATE/'worker-before-curation.json',remote)
archives=[];rows=[];candidate=None
with tempfile.TemporaryDirectory(prefix='mp-notes-stats-package-') as temporary:
    path=Path(temporary)/'checked.mplug'
    for plugin in ['notes','notes_labels','canvas','notes_stats']:
        manifest,raw,files=assemble(ROOT,'plugins/'+plugin+'/plugin.toml');assert raw==assemble(ROOT,'plugins/'+plugin+'/plugin.toml')[1]
        path.write_bytes(raw);checked=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(path)
        if plugin!='notes_stats':assert checked.digest==observation['runtime']['inventory']['artifacts'][manifest['plugin']['id']]['digest']
        else:
            assert manifest['runtime']['addon_name']=='mp_example_notes_stats' and manifest['plugin']['version']=='0.1.0'
            assert manifest['compatibility']['platform']=='>=0.1.13,<0.2'
            assert manifest['data']['models']==[] and manifest['data']['extension_targets']==[] and manifest['ui']['pages']==[]
            assert manifest['runtime']['python_dependencies']==[]
            candidate=(checked.digest,raw,files)
        archives.append(raw);rows.append(dict(plugin_id=manifest['plugin']['id'],digest=checked.digest,reproducible=True,old_image_artifact_exact=plugin!='notes_stats'))
    validate_reference_composition(archives)
digest,raw,files=candidate;archive=PRIVATE/'org.example.notes_stats-0.1.0.mplug'
with archive.open('xb') as stream:stream.write(raw)
trust_path=j.LOCAL/'operator/trust.json';old= f.load(trust_path);assert old['generation']==7 and digest not in old['approved_digests']
f.write(PRIVATE/'trust-before.json',old);f.write(MARKER,dict(state='curating',artifact_digest=digest,archive=str(archive.relative_to(ROOT))))
trust=copy.deepcopy(old);trust['generation']+=1;trust['approved_digests'].append(digest);f.write(trust_path,trust)
curated=Catalog(native.catalog_root,configuration(trust_path));curated.add(archive,expected_digest=digest)
after=native.observer.state(native.observer.read(),curated.snapshot())['state']
assert all(after[k]==before[k] for k in ['release_lock','installations','bindings','endpoints'])
assert base.snapshot(state,'notes-stats-curation-data-after')==data and base.worker(native,'notes-stats-curation-worker-after')==remote
f.save('package-curation.json',dict(result='passed_exact_minimal_native_connector_curation',artifact_digest=digest,archives=rows,
    composition_valid=True,files=sorted(files),old_three_native_image_artifacts_exact=True,no_models_fields_pages_or_python_dependencies_added=True,
    previous_fixture_trust_generation=7,current_fixture_trust_generation=8,global_catalog_and_trust_untouched=True,
    live_configuration_generation=17,dispatch_generation=85,release_metadata_bindings_endpoints_and17tables_worker_exact=True,
    native_addon_not_installed=True,no_docker_assets_created=True))
record=f.load(MARKER);record['state']='artifact_curated';f.write(MARKER,record);f.phase(state,'notes_stats_artifact_curated');f.guard(state)
print('NotesStats0.1.0 archive validated/reproduced/curated; old3 exact, live data/worker unchanged, no install')
