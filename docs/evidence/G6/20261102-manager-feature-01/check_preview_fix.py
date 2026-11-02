"""Real-profile source reproduction after the shared validator fix; no mutation."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import ROOT,OUT,PRIVATE,MARKER,context,f,base
from modular_platform.metadata_sql import METADATA_SELECT
from modular_platform.projection import project_deployment
from modular_platform.manager_planning import prepare_manager_external
from modular_platform.operation_views import prepared_view
state,native=context();cycle=f.load(MARKER);assert cycle['state']=='runtime_preview_fix_required'
profile=json.loads(f.sql(state,'manager-preview-fix-profile','BEGIN READ ONLY; SELECT payload FROM mp_operation_profile; ROLLBACK;'))
metadata=json.loads(f.sql(state,'manager-preview-fix-metadata','BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; '+METADATA_SELECT+'; ROLLBACK;'))
document=project_deployment(profile['configuration'],dict(runtime=profile['runtime'],image_id=profile['configuration']['image_id'],sites=[metadata],external_state=profile['external_state']),profile['catalog'])
nomination=dict(schema_version=1,operation='prepare',operation_type='suspend',plugin_id='org.example.document_stats',site_id=cycle['scope']['site_id'],workspace_ids=[cycle['scope']['workspace_id']],cascade=False)
bundle=prepare_manager_external(document,[metadata],profile['catalog'],profile['external_state'],nomination,
    operation_id='fd57ec5e-7397-4cce-9e24-cea865ef4116',created_at=cycle['baseline_at'].split('.')[0]+'Z')
view=prepared_view(bundle,observed_at=profile['observed_at']);assert view['restart_required'] and not view['native_trusted_code']
assert base.snapshot(state,'manager-preview-fix-data-after')==f.load(PRIVATE/'suspend-data-before.json')
f.save('prepare-source-fix.json',dict(result='passed_real_profile_source_preview_fix',same_actual_profile_metadata_path=True,
    restart_required=True,native_trusted_code=False,app_operation_created=False,all17tables_exact=True,
    source_digests={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['packages/platform_sdk/modular_platform/contracts.py','packages/platform_sdk/modular_platform/plans.py']},
    limits=['Host source correction only; installed core14 remains unchanged/broken until coherent core15 activation.']))
print('Real-profile corrected source round-trips through public preview; no request or mutation created; installed runtime still needs upgrade')
