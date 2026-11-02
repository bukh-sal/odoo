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
raw=f.sql(state,'manager-suspend-diagnostic-profile','BEGIN READ ONLY; SELECT payload FROM mp_operation_profile; ROLLBACK;')
profile=json.loads(raw)
raw=f.sql(state,'manager-suspend-diagnostic-metadata','BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; '+METADATA_SELECT+'; ROLLBACK;')
metadata=json.loads(raw);phase='projection'
nomination=dict(schema_version=1,operation='prepare',operation_type='suspend',plugin_id='org.example.document_stats',site_id=cycle['scope']['site_id'],workspace_ids=[cycle['scope']['workspace_id']],cascade=False)
try:
    observation=dict(runtime=profile['runtime'],image_id=profile['configuration']['image_id'],sites=[metadata])
    if 'external_state' in profile:observation['external_state']=profile['external_state']
    document=project_deployment(profile['configuration'],observation,profile['catalog'])
    phase='metadata_planner'
    bundle=prepare_manager_external(document,[metadata],profile['catalog'],profile.get('external_state'),nomination,
        operation_id='fd57ec5e-7397-4cce-9e24-cea865ef4116',created_at=cycle['baseline_at'].split('.')[0]+'Z')
    phase='prepared_view';prepared_view(bundle,observed_at=profile['observed_at'],stale=False)
    report=dict(result='planning_and_view_pass',next='Inspect installed ORM constraints and HTTP body; do not create another nomination yet.')
except Exception as error:
    report=dict(result='reproduced',phase=phase,exception=type(error).__name__,message=str(error)[:240],
        frames=[dict(file=Path(fr.filename).name,line=fr.lineno,function=fr.name) for fr in traceback.extract_tb(error.__traceback__)])
f.save('prepare-diagnostic.json',report)
assert base.snapshot(state,'manager-suspend-data-after-diagnostic')==f.load(PRIVATE/'suspend-data-before.json')
print(json.dumps(report))
