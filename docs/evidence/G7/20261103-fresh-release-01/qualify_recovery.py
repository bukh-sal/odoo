"""Bind actual dependency fault/restore coverage without a full release claim."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from dependency_recovery import ROOT,OUT,LOCAL,PRIVATE,PUBLIC,MARKER,f,OLD,NEW
r=f.load(MARKER);assert r['state']=='dependency_fault_restore_qualified' and r['recovery']['state']=='qualified'
fault=f.load(PUBLIC/'fault.json');commit=f.load(PUBLIC/'postcommit-proof.json');closed=f.load(PUBLIC/'closed-preservation.json');resumed=f.load(PUBLIC/'resumed-http.json');retired=f.load(PUBLIC/'retirement.json')
assert fault['native_child_exit0'] and commit['actual_child_image']==NEW and commit['native_core_version']=='19.0.0.1.21'
assert closed['current_image']==OLD and closed['configuration_generation']==4 and closed['old_approval_revoked'] and closed['filestore_files_retained']==38
assert closed['ingress_closed'] and closed['dispatch_paused'] and resumed['operation_status']['traffic_resumed'] and resumed['dispatch']['control']['state']=='enabled'
assert resumed['current_BobB_revocation_denied_after_restore'] and resumed['original17table_hashes_and_configs_exact'] and resumed['no_new_business_or_job_effect']
assert len(retired['containers'])==39 and retired['images_removed']==retired['volumes_removed']==retired['networks_removed']==0
baseline=f.load(OUT/'site/baseline-and-target.json');assert baseline['python_metadata_changed'] and baseline['baseline_python_lock']!=baseline['target_python_lock']
assert closed['python_lock_digest']==baseline['baseline_python_lock']
bundle=f.load(PUBLIC/'bundle.json');admission=f.load(ROOT/'docs/evidence/G7/20261103-core21-dependencies-image-01/candidate-admission.json')
assert bundle['operation_lock']['python_dependency_changes']==admission['python_dependency_changes'] and len(bundle['plan']['targets'])==6
sources={}
for name in ('native_executor','restore_executor','restore_continuation','native_auth_recovery','dispatch_operator','dispatch_lifecycle','recovery_reviews','release_staging','plans','operator_store'):
 path='packages/platform_sdk/modular_platform/'+name+'.py';data=(ROOT/path).read_bytes();assert data==subprocess.check_output(['git','show','4fbf8004:'+path]);sources[path]=hashlib.sha256(data).hexdigest()
records=['baseline-summary.json','seed.json','staged-image.json','bundle.json','independent-review.json','fault.json','postcommit-proof.json','current-authority-revocation.json','prepare-restore.json','restore.json','closed-preservation.json','prepare-resume.json','resume.json','resumed-http.json','retirement.json']
acceptance={
 'MIG-02':'Actual exact old31→new570/core20→21/19distribution dependency maintenance: target immutable native child exit0 and actual SQL core21 commit, host-only injected failure before metadata/traffic. Durable recovery_required/mutation_started true, no false rollback, paused checkpoint/dispatch and closed ingress.',
 'MIG-06':'Ordinary independently reviewed fresh DB restore plus separate reviewed resume: actual old31/core20/previous Python lock/inventory/native modules/schema/38files and fourNotes/minimalCanvas/completed original-actor job preserved. Current BobB revocation/native credentials overlaid exactly; old approval revoked; actual native views/attachment read and original working site17table/config hashes unchanged.'}
f.save('qualification.json',dict(result='passed_actual_dependency_changing_postcommit_fault_fresh_restore_and_separate_resume',utc=datetime.now(timezone.utc).isoformat(),operation_id=r['operation_id'],plan_hash=r['plan_hash'],baseline_image=OLD,failed_target_image=NEW,baseline_python_lock=baseline['baseline_python_lock'],target_python_lock=baseline['target_python_lock'],restored_configuration_generation=4,fresh_database=closed['fresh_database'],failed_database_retained=closed['failed_database_retained'],tables_present=16,absent_summary_table_preserved=True,notes=4,canvas=1,completed_job=1,files=38,retired_containers=39,original_working_deployment_unchanged=True,acceptance_requalified=acceptance,gate_weight_credit=0.5,unchanged_host_lifecycle_source_sha256=sources,records={name:hashlib.sha256((PUBLIC/name).read_bytes()).hexdigest() for name in records},limits=['Qualified native-only terminal-job fault/recovery fixture. No pending/in-flight/unknown remote effect reconciliation claim; MIG09 remains for full profile requalification.','Restored qualification app intentionally runs previous31/core20 dependencies. This is not a fresh target570 release or final release candidate.','Full fresh target bootstrap/reference worker registration/current acceptance, security/licenses/advisories/network/secrets/provenance, runbooks/performance/accessibility/final handoff remain.','No frontend product or Canvas expansion; standard record screens use native Odoo views.']))
print(json.dumps(dict(result='dependency_fault_recovery_qualified',acceptance=sorted(acceptance),gate_credit=0.5,remaining_fullfresh=True)))
