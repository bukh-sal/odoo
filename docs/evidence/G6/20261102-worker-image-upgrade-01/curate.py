"""Independent metadata curation and real unapproved-image manager refusal."""
import copy,json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from runtime import ROOT,OUT,PRIVATE,RUNTIME,context,op,f,j,base
from reference_package import assemble
from modular import configuration
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.profile_channel import publish_profile
import suspend as s
MARKER=PRIVATE/'metadata.json'
state,native=context();runtime=f.load(RUNTIME);assert runtime['state']=='new_worker_attested' and not MARKER.exists()
assert op(native).publisher._document()['generation']==8
build=f.load(OUT/'worker-build.json');old=f.load(PRIVATE/'runtime-data-before.json')
source=ROOT/'plugins/document_stats/plugin.toml';original=source.read_bytes();text=original.decode()
assert '"version" = "0.1.1"' in text and '"platform" = ">=0.1.13,<0.2"' in text
text=text.replace('"version" = "0.1.1"','"version" = "0.1.2"').replace('>=0.1.13,<0.2','>=0.1.17,<0.2')
text=text.replace('modular-document-stats@'+build['base_image_id'],build['expected_image'])
source.write_bytes(text.encode())
manifest,raw,files=assemble(ROOT,'plugins/document_stats/plugin.toml')
assert raw==assemble(ROOT,'plugins/document_stats/plugin.toml')[1]
assert manifest['plugin']['version']=='0.1.2' and manifest['external_service']['expected_image']==build['expected_image']
oldrow=next(r for r in old['mp_plugin_installation'] if r['plugin_id']=='org.example.document_stats')
expected=copy.deepcopy(oldrow['manifest']);expected['plugin']['version']='0.1.2';expected['compatibility']['platform']='>=0.1.17,<0.2';expected['external_service']['expected_image']=build['expected_image']
assert manifest==expected and len(files)==6
archive=PRIVATE/'org.example.document_stats-0.1.2.mplug';archive.write_bytes(raw)
verified=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(archive)
record=dict(state='curating',digest=verified.digest,scope=runtime['scope'],version='0.1.2',image=build['expected_image']);f.write(MARKER,record)
trust=j.LOCAL/'operator/trust.json';policy=f.load(trust);assert policy['generation']==8 and verified.digest not in policy['approved_digests']
f.write(PRIVATE/'metadata-trust-before.json',policy);policy['generation']+=1;policy['approved_digests'].append(verified.digest);f.write(trust,policy)
catalog=Catalog(native.catalog_root,configuration(trust));catalog.add(archive,expected_digest=verified.digest)
snapshot=catalog.snapshot();assert any(r['digest']==oldrow['artifact_digest'] for r in snapshot)
state,native=context();f.save('unapproved-image-planning-profile.json',publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True)))
client=s.client(state);nomination=dict(schema_version=1,operation='prepare',operation_type='upgrade',plugin_id='org.example.document_stats',
    site_id=runtime['scope']['site_id'],workspace_ids=[runtime['scope']['workspace_id']],cascade=False,artifact_version='0.1.2',artifact_digest=verified.digest)
code,response=client.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':client.csrf})
assert code==400 and response['error']['code']=='VALIDATION_FAILED',(code,response)
assert op(native).publisher._document()['generation']==8
assert base.snapshot(state,'image-metadata-curation-data')==old
f.save('unapproved-image-manager-refusal.json',dict(result='passed_actual_manager_new_image_without_current_approval_refused',status=code,response=response,
    native_generation=20,publication_generation=8,provider_all_scopes_suspended=True,old_metadata_preserved=True))
f.save('metadata-curation.json',dict(result='passed_immutable_changed_image_metadata_curation',version='0.1.2',digest=verified.digest,minimum_platform='0.1.17',
    previous_version='0.1.1',previous_digest=oldrow['artifact_digest'],previous_archive_preserved=True,trust_generation=9,files=sorted(files),
    only_manifest_changes=['plugin.version','compatibility.platform','external_service.expected_image'],no_native_or_frontend_code=True,
    worker_image=build['image_id'],source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),all_host_data_exact=True))
record['state']='curated_unapproved_image_refused';f.write(MARKER,record)
print('Metadata0.1.2/min17/newimage curated, oldarchive retained; actual manager refuses unapproved image while publication8 remains revoked',flush=True)
