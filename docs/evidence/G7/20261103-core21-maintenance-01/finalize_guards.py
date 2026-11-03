"""Reconcile real stale refusal; native guard exits1, not a timeout status."""
import importlib.util,json
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('core21_guard_final',OUT/'activate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();name=state['project']+'-core21-stale-image-refusal'
info=json.loads(f.command('core21-stale-terminal-inspection',['docker','inspect','--type','container',name]))[0]
assert info['State']['Status']=='exited' and info['State']['ExitCode']==1 and info['Config']['Labels']['com.modular.disposable']==state['project']
assert info['Image']=='sha256:31a673ebbc53fbdecbc5cbfdb5f0eac30d11367630da306d47b5e14cfce17345'
diagnostic=(m.j.LOCAL/'logs/core21-stale-image-refusal.stderr').read_text()
assert 'Database release inventory differs; controlled maintenance required' in diagnostic
before=json.loads((m.j.LOCAL/'logs/core21-gateway-negative-before.stdout').read_text())
assert m.snapshot(state,'core21-gateway-negative-after')==before
assert m.worker(native,'core21-gateway-negative-worker-after')==f.load(m.PRIVATE/'worker-before.json')
f.save('gateway-startup-guards.json',dict(result='passed_current_gateway_operator_boundaries_and_stale_startup_refusal',configuration_generation=30,image_id=state['image_id'],
 checks=['undeclared sudo404 NOT_FOUND','schema actor injection400 VALIDATION_FAILED without debug/traceback','workspace administrator manager API403','workspace administrator native installation read/create AccessError','actual previous31 image exits1 at pre-import database inventory fence before serving'],
 stale_container=name,stale_exit=1,all37jobs_other16tables_worker_exact=True,
 diagnosed_harness_failure='Expected124/version diagnostic was wrong: actual Python ValueError exits1 at earlier database inventory check. Same terminal helper/log inspected, no startup rerun.',
 limits=['Supported startup/HTTP boundaries only; trusted native code can bypass an entrypoint, no sandbox claim.','Full production TLS/proxy/network/secrets/provenance/failure-recovery qualification remains.']))
print('Actual stale old image exits1 at pre-import inventory gate; gateway/operator denials and all captured data/worker preservation verified')
