"""Actual current image must refuse metadata mutation before reservation."""
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.operator_store import OperatorStore
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_os import OperatorError
from modular import configuration

def main():
    local=ROOT/'.local/g6-events';marker=local/'metadata-host-preflight-01.json'
    if marker.exists():raise RuntimeError('Inspect original read-only preflight result')
    state=json.loads((local/'state.json').read_text());target=local/'operator/target.json'
    before=hashlib.sha256(target.read_bytes()).hexdigest()
    marker.write_text(json.dumps(dict(state='running'))+'\n')
    native=ReferenceMetadataExecutor(OperatorStore(local/'operator/control'),target,local/'operator/catalog',configuration(local/'operator/trust.json'))
    rejected=False
    try:native._runtime_preflight(dict(operation_lock=dict(release=native.config['published_release'])))
    except OperatorError as error:
        if 'immutable image' not in str(error):raise
        rejected=True
    assert rejected and hashlib.sha256(target.read_bytes()).hexdigest()==before
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in state['protected_configurations'].items())
    report=dict(result='passed_actual_old_image_refusal',utc=datetime.now(timezone.utc).isoformat(),image=state['image_id'],
        metadata_preflight_rejected=True,reservation_attempted=False,mutation_attempted=False,new_docker_assets=0,
        target_and_protected_configs_preserved=True,limit='Private read-only preflight only; coherent new immutable image still required.')
    (OUT/'host-preflight.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    marker.write_text(json.dumps(dict(state='completed',**report),indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=='__main__':main()
