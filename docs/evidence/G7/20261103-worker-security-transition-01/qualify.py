"""Current worker acceptance binding; no whole security/recovery/G7 claim."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from runtime import s,base,f,j,PRIVATE,OUT,ROOT,IMAGE,REFERENCE,op
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
state,native=s.context();assert native.config['generation']==31
for action in ('suspend','upgrade','enable'):assert f.load(s.path(action))['state']=='verified'
assert f.load(PRIVATE/'remote-job.json')['state']=='verified'
credentials=f.load(OUT/'current-credentials.json');assert len(credentials['cases'])==7
data=base.snapshot(state,'worker-security-qualification-final');assert len(data['mp_job'])==38
assert {k:sum(x['state']==k for x in data['mp_job']) for k in ('completed','dead_letter','cancelled')}==dict(completed=17,dead_letter=19,cancelled=2)
worker=base.worker(native,'worker-security-qualification-worker');assert worker['image']==IMAGE
operator=op(native);document=operator.publisher._document();assert document['generation']==13
helper=ReferenceDispatchMaintenance(native);snapshot=helper.inspect();helper.require_profile(snapshot);policy=helper.policy_for(snapshot)
assert policy['profile']=='r1-reference-stateless-v1' and policy['runtime_image']==REFERENCE
assert policy['registrations'][0]['version']=='0.1.3' and all(x['feature_state']=='enabled' for x in policy['registrations'][0]['features'])
build=f.load(OUT.parent/'20261103-worker-dependencies-image-01/candidate-build.json')
paths={}
for path,digest in build['source_sha256'].items():
 if path.endswith('/Dockerfile'):continue
 destination='/app/'+path
 if path.startswith('services/document_stats/') and path.endswith(('requirements.lock','dependency-provenance.json')):destination='/app/provenance/'+Path(path).name
 if path in ('LICENSE','COPYRIGHT'):destination='/app/provenance/'+path
 paths[destination]=digest
code="import hashlib,importlib.metadata as m,importlib.util,json,pathlib,sys;p=json.load(sys.stdin);v={d.metadata['Name']:d.version for d in m.distributions()};assert importlib.util.find_spec('odoo') is None;assert all(hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest()==h for n,h in p.items());print(json.dumps(dict(packages=v,files=len(p),odoo_absent=True)))"
observed=json.loads(f.command('worker-security-current-source-packages',['docker','exec','-i',worker['container_id'],'/venv/bin/python','-c',code],input=json.dumps(paths).encode()))
assert observed['packages']==build['packages'] and observed['files']==13 and observed['odoo_absent']
runtime=native.observer.read()['runtime'];sources={}
for name in ('worker_transition','reference_dispatch','reference_recovery','external_planning','external_metadata','metadata_executor','dispatch_lifecycle','worker_operator','worker_publication','worker_authority','worker_dispatch','job_runner','tokens','projection','operator_store','plans'):
 path='packages/platform_sdk/modular_platform/'+name+'.py';actual=(ROOT/path).read_bytes();assert actual==subprocess.check_output(['git','show','f37ed42d:'+path])
 digest=hashlib.sha256(actual).hexdigest();assert runtime['inventory']['files'][path]==digest;sources[path]=digest
retired=f.load(OUT/'retirement.json');assert retired['current_runtime_data_exact']
records=['suspend-preservation.json','metadata-curation.json','switch-prestop-diagnosis.json','runtime-change-review.json','runtime-switch.json','runtime-refusals.json','reviewed-native-transition.json','upgrade-preservation.json','enable-preservation.json','current-credentials.json','credential-status-diagnosis.json','remote-job.json','retirement.json']
acceptance={
 'SVC-01':'Actual active immutable87 image: no Odoo import,13 distributions and13 copied source/provenance files exact. Sole RO public config mount/image-default environment; no DB/issuer/operator/socket mounts. Actual original-user job completes once.',
 'SVC-03':'Actual current valid RS256 token plus altered payload workspace/site returns401; independently foreign signed workspace also403. Normal configured scope works and host original actor job is separately checked.',
 'SVC-05':'Actual reviewed revocation12/newendpoint11/publication13; unapproved metadata image400, old/third image and unreviewed default mismatch refused, exact private transition then ordinary metadata0.1.3 upgrade/enable. Current token200, staleendpoint403/wrongaudience401/retiredkey401 and retiredissuer refusal. Strict default profile restored.'}
f.save('qualification.json',dict(result='passed_actual_dependency_worker_transition_and_bounded_acceptance',utc=datetime.now(timezone.utc).isoformat(),acceptance_requalified=acceptance,configuration_generation=31,dispatch_generation=snapshot['control']['generation'],host_image=native.config['image_id'],worker_image=IMAGE,worker_container=worker['container_id'],worker_packages=observed['packages'],worker_copied_files_exact=13,publication_generation=13,endpoint_generation=11,metadata_version='0.1.3',counts={t:len(rows) for t,rows in data.items()},current_strict_default_reference_profile=True,unchanged_current_inventoried_host_source_sha256=sources,records={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in records},limits=['No new API-major/storage/effect behavior or native/same-origin sandbox claim.','Not dependency-changing native post-commit fault/restore, clean full release, final security/advisory/provenance/license/network/secrets/history qualification or runbooks. Historical worker recovery source is retained unchanged, not rerun here.','No browser UI09, target performance or Canvas expansion. Weighted gate points unchanged until the relevant whole slice passes.']))
f.phase(state,'worker_security_transition_backend_qualified');f.guard(state)
print(json.dumps(dict(result='worker_transition_qualified',acceptance=sorted(acceptance),jobs=38,dispatch=snapshot['control']['generation'])))
