"""Curate exact metadata0.1.3; unapproved worker image cannot be planned."""
import copy,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import runtime as r
s,f,j,base,PRIVATE,OUT,ROOT=r.s,r.f,r.j,r.base,r.PRIVATE,r.OUT,r.ROOT
from reference_package import assemble
from modular import configuration
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.profile_channel import publish_profile
state,native=s.context();record=f.load(r.MARKER);assert record['state']=='revoked' and not (PRIVATE/'metadata.json').exists()
assert r.op(native).publisher._document()['generation']==12
source=ROOT/'plugins/document_stats/plugin.toml';original=source.read_bytes();text=original.decode()
assert '"version" = "0.1.2"' in text and 'modular-document-stats@sha256:5482020' in text
text=text.replace('"version" = "0.1.2"','"version" = "0.1.3"').replace(r.op(native).config['runtime']['image'],r.REFERENCE)
source.write_bytes(text.encode());manifest,raw,files=assemble(ROOT,'plugins/document_stats/plugin.toml');assert raw==assemble(ROOT,'plugins/document_stats/plugin.toml')[1]
before=f.load(PRIVATE/'runtime-before.json');old=next(x for x in before['mp_plugin_installation'] if x['plugin_id']=='org.example.document_stats')
expected=copy.deepcopy(old['manifest']);expected['plugin']['version']='0.1.3';expected['external_service']['expected_image']=r.REFERENCE
assert manifest==expected and len(files)==6
archive=PRIVATE/'org.example.document_stats-0.1.3.mplug';archive.write_bytes(raw)
verified=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(archive)
metadata=dict(state='curating',version='0.1.3',digest=verified.digest,image=r.REFERENCE,scope=record['scope']);f.write(PRIVATE/'metadata.json',metadata)
trust=j.LOCAL/'operator/trust.json';policy=f.load(trust);assert policy['generation']==12 and verified.digest not in policy['approved_digests']
f.write(PRIVATE/'trust-before.json',policy);policy['generation']+=1;policy['approved_digests'].append(verified.digest);f.write(trust,policy)
catalog=Catalog(native.catalog_root,configuration(trust));catalog.add(archive,expected_digest=verified.digest)
assert any(x['digest']==old['artifact_digest'] for x in catalog.snapshot())
state,native=s.context();f.save('unapproved-image-planning-profile.json',publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True)))
c=s.client(state);scope=record['scope'];nomination=dict(schema_version=1,operation='prepare',operation_type='upgrade',plugin_id='org.example.document_stats',site_id=scope['site_id'],workspace_ids=[scope['workspace_id']],cascade=False,artifact_version='0.1.3',artifact_digest=verified.digest)
code,response=c.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':c.csrf});assert code==400 and response['error']['code']=='VALIDATION_FAILED',(code,response)
assert base.snapshot(state,'worker-security-curation-after')==before
f.save('metadata-curation.json',dict(result='passed_metadata_curation_and_unapproved_image_refusal',version='0.1.3',digest=verified.digest,old_version='0.1.2',old_digest=old['artifact_digest'],old_archive_retained=True,files=sorted(files),only_manifest_changes=['plugin.version','external_service.expected_image'],trust_generation=13,unapproved_image_HTTP_status=code,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),all_host_data_exact=True))
metadata['state']='curated_unapproved_image_refused';f.write(PRIVATE/'metadata.json',metadata)
print('Metadata0.1.3 curated; actual manager refuses candidate image without independent endpoint approval',flush=True)
