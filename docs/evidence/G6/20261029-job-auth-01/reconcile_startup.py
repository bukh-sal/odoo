"""Reconcile failed runner before preserving its exact unclaimed work."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import g6_job_process_probe as p
f=p.f;state=f.load(p.LOCAL/'state.json');f.guard(state)
assert state['phase']=='process-enqueue-normal'
child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-job-runner-normal']))[0]
assert not child['State']['Running'] and child['State']['ExitCode']==1
stderr=(p.LOCAL/'logs/job-runner-normal.stderr').read_text()
assert "AttributeError: module 'odoo' has no attribute 'tools'" in stderr
job=f.load(p.LOCAL/'process-enqueue-normal.json');record=p.snapshot(state,'reconcile-startup-failure',job)
assert record['state']=='pending' and record['attempts']==0 and record['generation']==0
assert (record['title'],record['revision'])==(job['title'],1)
code="""import json
from modular_platform import durable
env.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'");site=env.cr.fetchone()[0]
env.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");release=env.cr.fetchone()[0]
durable.set_control(env.cr,site,release,'paused');env.cr.commit();print('MP_PROCESS='+json.dumps(dict(paused=True)))
"""
assert p.native(state,'startup-failure-pause',code)==dict(paused=True)
f.phase(state,'job_authorization_verified_runner_startup_failed')
f.write(p.LOCAL/'process.json',dict(phase='terminal_startup_failed_before_claim',job_id=job['job_id'],attempts=0,dispatch='paused',failure='namespace bootstrap',corrected_source_not_deployed=True))
path=p.OUTPUT/'runner-startup-failure.json';assert not path.exists()
f.write(path,dict(result='confirmed_startup_defect_before_claim',image_id=state['image_id'],inventory_digest=state['inventory_digest'],project=state['project'],job_id=job['job_id'],attempts=0,native_business_revision=1,children_terminal=True,dispatch='paused',diagnosis='Pinned Odoo19 namespace package requires its official core initialization. Bare import odoo provides neither tools nor modules.',fix='Import Registry from odoo.modules.registry and config from odoo.tools after immutable guards. No upstream edit.',next_experiment='Build corrected candidate03. Its package/core/dispatch code remains exact; qualify actual runner startup and OS kill/reclaim on one distinct fresh owned site. Preserve both prior G6 sites/queues; populated queue-aware lifecycle remains F-01e.'))
print(json.dumps(dict(result='reconciled',job_attempts=0,dispatch='paused',native_effects=0)))
