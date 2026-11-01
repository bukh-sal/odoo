"""Five real reference archives; metadata has no native/frontend/runtime code."""
import hashlib,json,subprocess,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from reference_package import assemble,materialize_reference,validate_reference_composition
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.contracts import normalize_manifest
from packaging.specifiers import SpecifierSet
old=types.ModuleType('retained_reference_assembler')
exec(compile(subprocess.run(['git','show','2316240a:tools/reference_package.py'],cwd=ROOT,capture_output=True,check=True).stdout,'retained_assembler','exec'),old.__dict__)
rows=[];archives=[];validator=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True))
with tempfile.TemporaryDirectory(prefix='mp-external-metadata-') as temporary:
    path=Path(temporary)/'candidate.mplug'
    for plugin in ['notes','notes_labels','canvas','notes_stats','document_stats']:
        relative='plugins/'+plugin+'/plugin.toml';manifest,raw,files=assemble(ROOT,relative);assert raw==assemble(ROOT,relative)[1]
        path.write_bytes(raw);value=validator.verify(path,expected_digest='sha256:'+hashlib.sha256(raw).hexdigest())
        if plugin in ['notes','notes_labels','canvas']:assert raw==old.assemble(ROOT,relative)[1]
        if plugin=='document_stats':
            assert manifest['runtime']=={'kind':'external_service'} and manifest['upgrade']['strategy']=='metadata_only'
            assert manifest['data']['models']==manifest['data']['extension_targets']==manifest['data']['contributions']==[]
            assert manifest['ui']['mode']=='none' and manifest['services']['provides'][0].get('handler') is None
            assert manifest['external_service']['expected_image']==json.loads((ROOT/'services/document_stats/image.lock.json').read_text())['reference']
            assert set(files)=={'plugin.toml','schemas/stats-v1.json','notices/LICENSE','notices/COPYRIGHT','provenance.json','inventory.json'}
            schema=json.loads(files['schemas/stats-v1.json'])
            for name in ['request','response']:assert schema['$defs'][name]==json.loads((ROOT/'packages/contracts/v1'/('worker-'+name+'.schema.json')).read_text())
            try:materialize_reference(ROOT,relative,Path(temporary)/'no-native-addon')
            except ValueError as error:assert str(error)=='External metadata cannot materialize a native addon'
            else:raise AssertionError('External metadata fabricated a native addon')
            assert not (Path(temporary)/'no-native-addon').exists()
        if plugin in ['document_stats','notes_stats']:
            assert '0.1.12' in SpecifierSet(manifest['compatibility']['platform']) and '0.1.11' not in SpecifierSet(manifest['compatibility']['platform'])
        rows.append(dict(plugin=manifest['plugin']['id'],runtime=manifest['runtime']['kind'],digest=value.digest,files=len(files),reproducible=True));archives.append(raw)
    validate_reference_composition(archives)
result=dict(result='passed_reference_metadata_artifact_prerequisite',archives=rows,old_three_native_archives_byte_identical=True,no_external_native_addon_frontend_or_deployment_descriptors=True,existing_frozen_worker_DTOs_exact=True,no_artifact_retained_or_registered=True,no_runtime_started=True,no_docker_assets_created=True,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/reference_package.py','plugins/document_stats/plugin.toml','plugins/notes_stats/plugin.toml']},limits=['Artifact validation/composition only. Independent metadata registration/unregister/suspension, live endpoints/provider bindings, compatibility and full external recovery remain required; SVC04/05 not claimed.'])
(OUT/'qualification.json').write_text(json.dumps(result,indent=2)+'\n');print('Five deterministic archives validate; oldthree byte-identical; externalmetadata is data-only and cannot create an addon')
