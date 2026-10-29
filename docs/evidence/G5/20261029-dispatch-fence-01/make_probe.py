"""Derive the existing scoped recovery probe for this independent fixture."""
from pathlib import Path

root=Path(__file__).resolve().parents[4]
source=root/'docs/evidence/G5/20261029-executor-crash-01/probe.py'
text=source.read_text(encoding='utf8')
text=text.replace("LOCAL=ROOT/'.local/g5-lifecycle'", "LOCAL=ROOT/'.local/g5-dispatch'")
text=text.replace("attempt=OUTPUT/'attempt02'", "attempt=OUTPUT/'recovery'")
text=text.replace("'executor_crash_restored_resumed'", "'dispatch_restored_resumed'")
text=text.replace("['executor-crash.json','executor-crash02.json']", "['dispatch-fault.json']")
text=text.replace("config['generation']==15", "config['generation']==20")
text=text.replace("generation=13", "generation=18")
text=text.replace("['generation']==15", "['generation']==20")
text=text.replace("restored_generation=15", "restored_generation=20")
text=text.replace("'executor-crash02.json'", "'dispatch-fault.json'")
start=text.index("    manifests=[store.root/'stages/")
end=text.index('    for manifest in manifests:',start)
text=text[:start]+"    prior=ROOT/'.local/g5-lifecycle/operator/control/stages'/load(ROOT/'.local/g5-lifecycle/worker-fence-deploy.json')['operation_id']/'assets.json'\n    manifests=[prior,store.root/'recoveries'/load(LOCAL/'dispatch-fault.json')['operation_id']/'assets.json']\n"+text[end:]
text=text.replace('127.0.0.1:18080','127.0.0.1:18081')
destination=Path(__file__).with_name('probe.py')
assert not destination.exists()
destination.write_text(text,encoding='utf8')
