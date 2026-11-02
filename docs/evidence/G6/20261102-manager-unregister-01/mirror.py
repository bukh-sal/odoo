"""Publish/read the redacted same-operation journal through the normal channel."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import OUT,MARKER,context,f,base,j
import r1_probe
from modular_platform.contracts import validate_operations_view
r1_probe.r1.r0.LOCAL=j.LOCAL
state,native=context();cycle=f.load(MARKER);record=cycle['unregister'];assert record['state']=='preservation_verified'
command=base.prefix()+['operations','--store',str(native.store.root),'mirror-status',record['operation_id']]+base.validation(native)
result=json.loads(f.command('manager-unregister01-unregister-mirror',command));f.save('unregister-mirror-publication.json',result)
client=r1_probe.Client(state,f.load(j.LOCAL/'fixtures.json'),'operator')
status,response=client.request('/api/v1/operations/status/'+record['operation_id']);assert status==200
view=validate_operations_view(response['data']);assert view['state']=='completed' and view['phase']=='completed'
assert view['source']=='operator_journal_mirror' and view['plan_hash']==record['plan_hash']
assert len(view['dimensions'])==1
dimension=view['dimensions'][0];assert dimension['plugin_id']=='org.example.document_stats' and dimension['database_state']=='not_installed' and dimension['feature_state']=='suspended'
f.save('unregister-http-completed-status.json',view)
f.save('unregister-handoff-qualification.json',dict(result='passed_actual_http_manager_to_independent_executor_handoff',operation_id=record['operation_id'],plan_hash=record['plan_hash'],
    app_request_was_not_approval=True,independent_import_review_exact_approval_required=True,same_operation_completed=True,
    actual_http_redacted_status_completed=True,external_metadata_removed_feature_suspended=True,browser_rendering_tested=False))
f.guard(state);print('Same manager HTTP request now observes independently mirrored completed status, removed metadata and suspended feature')
