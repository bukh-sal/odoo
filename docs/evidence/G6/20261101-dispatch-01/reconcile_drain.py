"""Reconcile the committed successful drain after a wrong test postcondition.

Do not repeat the actual producer/fence mutation. The only failed test-body
assertion was after the real lock wait, rollback and fence commit completed.
"""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'docs/evidence/G6/20261029-events-01'))
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='dispatch_fence_failed'
failed=f.load(OUT/'drain-concurrency-01.json');helper=ROOT/'packages/platform_sdk/modular_platform/dispatch_lifecycle.py';tests=OUT/'native_tests.py'
assert failed['tests']==1 and len(failed['failures'])==2 and not failed['errors']
assert hashlib.sha256(helper.read_bytes()).hexdigest()==failed['helper_sha256'] and hashlib.sha256(tests.read_bytes()).hexdigest()==failed['test_sha256']
lines=tests.read_text().splitlines();assert "set(original['tables'])-{'mp_dispatch_control'}" in lines[113]
trace=(j.LOCAL/'logs/dispatch-drain-concurrency-01.stderr').read_text()
assert 'line 114, in test_real_native_producer_holds_drain_until_its_transaction_finishes' in trace and 'line 22, in tearDown' in trace
assert trace.count('AssertionError:')==2 and "'rows': 216" in trace
assert f.load(OUT/'fence-01.json')['result']=='passed' and f.load(OUT/'fence-01.json')['helper_sha256']==failed['helper_sha256']
code="import json,sys,types\nenv.cr.rollback()\nm=types.ModuleType('modular_platform.dispatch_lifecycle_probe');m.__package__='modular_platform';sys.modules[m.__name__]=m\nexec(compile("+repr(helper.read_text())+",'dispatch_lifecycle_probe','exec'),m.__dict__)\n"
code+="env.cr.execute(\"SELECT value FROM ir_config_parameter WHERE key='mp.site_id'\");site=env.cr.fetchone()[0]\nenv.cr.execute(\"SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'\");release=env.cr.fetchone()[0]\nobserved=m.observe(env.cr,m.LifecycleScope(site,release));assert observed['control']['state']=='paused' and observed['control']['generation']==14\n"
code+="assert {k:v['rows'] for k,v in observed['tables'].items()}==dict(mp_dispatch_control=1,mp_job=3,mp_outbox=28,mp_event_subscription=31,mp_event_delivery=216,mp_event_consumption=3,mp_event_consumer_state=1)\nenv.cr.execute('SELECT count(*) FROM mp_example_note');assert env.cr.fetchone()[0]==22\nenv.cr.execute(\"SELECT count(*) FROM mp_event_delivery WHERE state='leased'\");assert env.cr.fetchone()[0]==0\nprint('MP_DRAIN_RECONCILED='+json.dumps(observed));env.cr.rollback()"
raw=f.native(state,'dispatch-drain-reconcile-01',[],code)
rows=[json.loads(line.split('MP_DRAIN_RECONCILED=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_DRAIN_RECONCILED=')];assert len(rows)==1
f.save('drain-reconciliation.json',dict(result='passed_by_retained_prefix_and_readonly_reconciliation',retained_failed_record='drain-concurrency-01.json',real_native_wait_and_postrollback_fence_commit_completed_before_failure=True,diagnosis='Test incorrectly expected all delivery metadata unchanged. Fencing deliberately replaces leased receipts; immutable producer/consumer/business history remains retained. Subsequent teardown compared the old control epoch because the wrong assertion prevented baseline update.',mutation_repeated=False,seven_other_cases_passed_same_helper=True,current_observation=rows[0],limits=['Native helper proof only, not integrated executor/upgrade/restore qualification.']))
f.phase(state,'dispatch_fence_verified');f.guard(state);print('Committed native drain reconciled; no producer/fence replay.')
