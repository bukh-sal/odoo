"""Installed native checker accepts only the exact reviewed suspended transition."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from runtime import s,base,f,PRIVATE,IMAGE
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
state,native=s.context();r=f.load(s.path('upgrade'));assert r['state']=='approved'
helper=ReferenceDispatchMaintenance(native,operation=r['operation_id']);snapshot=helper.inspect();helper.require_profile(snapshot);policy=helper.policy_for(snapshot)
assert policy['profile']=='r1-reference-stateless-transition-v1' and policy['worker_transition']['operation_id']==r['operation_id']
assert policy['runtime_image']=='modular-document-stats@'+IMAGE and policy['registrations'][0]['version']=='0.1.2'
assert snapshot['external_installations']==1 and snapshot['job_states']==dict(completed=16,dead_letter=19,cancelled=2)
assert all(x['feature_state']=='suspended' for registration in policy['registrations'] for x in registration['features'])
assert base.snapshot(state,'worker-security-reviewed-transition-after')==f.load(PRIVATE/'upgrade-before.json')
f.save('reviewed-native-transition.json',dict(result='passed_actual_installed_exact_private_transition',snapshot=snapshot,policy=policy,all37terminal_jobs_other17tables_exact=True,no_mutation=True))
print('Installed native checker accepted exact independently reviewed87 transition; all provider scopes suspended',flush=True)
