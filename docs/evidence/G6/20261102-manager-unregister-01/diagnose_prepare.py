"""Reproduce actual controller planning from its real DB snapshot, read-only."""
import json,sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import ROOT,OUT,PRIVATE,MARKER,context,f,base
from modular_platform.metadata_sql import METADATA_SELECT
from modular_platform.projection import project_deployment
from modular_platform.manager_planning import prepare_manager_external
from modular_platform.operation_views import prepared_view
state,native=context();cycle=f.load(MARKER)
raw=f.sql(state,'manager-unregister01-corrected-diagnostic-profile','BEGIN READ ONLY; SELECT payload FROM mp_operation_profile; ROLLBACK;')
profile=json.loads(raw)
raw=f.sql(state,'manager-unregister01-corrected-diagnostic-metadata','BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; '+METADATA_SELECT+'; ROLLBACK;')
metadata=json.loads(raw);phase='projection'
nomination=dict(schema_version=1,operation='prepare',operation_type='unregister',plugin_id='org.example.document_stats',site_id=cycle['scope']['site_id'],workspace_ids=[],cascade=False)
try:
    observation=dict(runtime=profile['runtime'],image_id=profile['configuration']['image_id'],sites=[metadata])
    if 'external_state' in profile:observation['external_state']=profile['external_state']
    document=project_deployment(profile['configuration'],observation,profile['catalog'])
    phase='metadata_planner'
    bundle=prepare_manager_external(document,[metadata],profile['catalog'],profile.get('external_state'),nomination,
        operation_id='0809d8a2-f707-4da7-8ca8-0ff86f58913b',created_at=cycle['baseline_at'].split('.')[0]+'Z')
    phase='prepared_view';prepared_view(bundle,observed_at=profile['observed_at'],stale=False)
    report=dict(result='planning_and_view_pass',next='Inspect installed ORM constraints and HTTP body; do not create another nomination yet.')
except Exception as error:
    report=dict(result='reproduced',phase=phase,exception=type(error).__name__,message=str(error)[:240],
        frames=[dict(file=Path(fr.filename).name,line=fr.lineno,function=fr.name) for fr in traceback.extract_tb(error.__traceback__)])
f.save('prepare-corrected-diagnostic.json',report)
assert base.snapshot(state,'manager-unregister01-data-after-corrected-diagnostic')==f.load(PRIVATE/'unregister-data-before.json')
print(json.dumps(report))
