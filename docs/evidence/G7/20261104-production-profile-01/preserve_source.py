"""Exact17-table/worker/config preservation on the existing source realm."""
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context,snapshot,worker,LOCAL
f.OUTPUT=OUT;state,native=context('connector');assert native.config['generation']==4
prior=ROOT/'.local/g7-proxy-ingress-04';data=snapshot(state,'production-profile-source-after');identity=worker(native,'production-profile-source-worker-after')
assert data==json.loads((prior/'data-before.json').read_text());assert identity==json.loads((prior/'worker-before.json').read_text());f.guard(state)
record=dict(result='source17tables_worker_and_all_protected_configurations_exact',utc=datetime.now(timezone.utc).isoformat(),source_image=state['image_id'],generation=4,source_project=state['project'],table_count=17,prior_data_sha256=hashlib.sha256((prior/'data-before.json').read_bytes()).hexdigest(),prior_worker_sha256=hashlib.sha256((prior/'worker-before.json').read_bytes()).hexdigest(),limits=['Full listed business/authority/job/event tables and worker/config identity; login/session/asset caches are outside this snapshot.','Copied fixture test records/events are separate; original source/site/control are not changed.'])
(OUT/'source-preservation.json').write_text(json.dumps(record,indent=2)+'\n');print(record['result'])
