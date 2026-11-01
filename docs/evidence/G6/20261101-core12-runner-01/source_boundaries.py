"""Bind retained actual death/revocation proof to unchanged current code paths."""
import ast,copy,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
oldproof=json.loads((ROOT/'docs/evidence/G6/20261101-core11-runner-01/checkpoint.json').read_text())
def previous(path):
    raw=subprocess.run(['git','show','2316240a:'+path],cwd=ROOT,capture_output=True,check=True).stdout
    assert hashlib.sha256(raw).hexdigest()==oldproof['source_sha256'][path]
    return raw.decode()
def nodes(source):return {n.name:n for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
def equal(a,b):return ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
path='platform_addons/mp_core/job_dispatch.py';old=nodes(previous(path));new=nodes((ROOT/path).read_text())
assert old.keys()==new.keys()
unchanged=[]
for name in old:
    if name=='_safe_code':continue
    assert equal(old[name],new[name]),name;unchanged.append(name)
runner='packages/platform_sdk/modular_platform/job_runner.py';oldrun=nodes(previous(runner));newrun=nodes((ROOT/runner).read_text())
assert oldrun.keys()==newrun.keys()
for name in oldrun:
    if name!='run_once':assert equal(oldrun[name],newrun[name]),name
candidate=copy.deepcopy(newrun['run_once']);removed=0
test=ast.parse("code=='CANCELLED'").body[0].value
for node in ast.walk(candidate):
    if isinstance(node,ast.ExceptHandler):
        found=[n for n in node.body if isinstance(n,ast.If) and equal(n.test,test)]
        for entry in found:node.body.remove(entry);removed+=1
assert removed==1 and equal(oldrun['run_once'],candidate)
exact=[]
for path in ['packages/platform_sdk/modular_platform/durable.py','platform_addons/mp_example_notes/jobs.py','platform_addons/mp_core/external_job.py']:
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==oldproof['source_sha256'][path];exact.append(path)
result=dict(result='passed_retained_test_boundaries',previous_actual_image=oldproof['image_id'],current_core='19.0.0.1.12',exact_files=exact,exact_native_definitions=unchanged,exact_runner_functions_except_one_cancel_if=True,only_runner_control_flow_addition='Return claim_lost for CANCELLED before opening a failure transaction',native_mapper_delta='Existing PLUGIN_SUSPENDED/NOT_FOUND worker codes preserved; all other guard/prepare/finalization definitions unchanged',retained_proofs=['../20261101-core11-runner-01/lease.json','../20261101-core11-runner-01/revocation.json'],limits=['AST/source boundaries justify retaining the actual death/reclaim and committed actor-demotion cases. Current installed native matrix and actual runner code/error/cancel cases are separate required records.'])
(OUT/'source-boundaries.json').write_text(json.dumps(result,indent=2)+'\n');print('Unchanged claim/authorization/finalization/compute and startup paths proven; current cancel branch isolated')
