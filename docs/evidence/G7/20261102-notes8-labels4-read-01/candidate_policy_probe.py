"""Candidate-only pending-policy discriminator, existing rows, rollback only."""
import hashlib,importlib.util,json
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('notes8_policy_base',OUT.parent/'20261102-read-window-02/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==28
build=f.load(OUT.parent/'20261102-notes8-labels4-candidate-01/candidate-build.json');image=build['image_id']
before=m.snapshot(state,'notes8-policy-before');worker=m.worker(native,'notes8-policy-worker-before')
code="""import json
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
results=[]
for kind in ['feature','installation']:
 env.cr.rollback();env.invalidate_all()
 actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
 note=actor['mp.example.note'].search([],limit=1);assert note
 with note._mp_read_window() as record:
  assert record._labels_available(read_window=True)
  if kind=='feature':
   env['mp.workspace.plugin'].search([('workspace_id','=',actor.context['_mp_scope'].workspace_id),('plugin_id','=','org.example.notes_labels')]).write({'availability':'suspended'})
  else:env['mp.plugin.installation'].search([('plugin_id','=','org.example.notes_labels')]).write({'state':'suspended'})
  dirty=bool(env._field_dirty)
  actual=record._labels_available(read_window=True)
  results.append(dict(kind=kind,pending_ORM_state=dirty,expected=False,actual=actual,passed=actual is False))
 env.cr.rollback();env.invalidate_all()
print('MP_LABELS_POLICY='+json.dumps(dict(checks=results,all_fixtures_rolled_back=True)))
""".replace('FIXTURE',repr(f.load(m.j.LOCAL/'fixtures.json')))
label='g7-notes8-policy-candidate-01'
argv=['docker','run','-i','--name',state['project']+'-'+label,'--log-driver','none','--label','com.modular.disposable='+state['project'],'--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp','--memory','1536m','--pids-limit','128',
 '--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular,readonly','--mount','type=volume,source='+state['project']+'_bootstrap,target=/run/mp-bootstrap,readonly','--entrypoint','/venv/bin/python',image,'odoo-bin','shell','-c','/run/secrets/odoo_config','-d',state['active_db'],'--no-http','--workers=0','--max-cron-threads=0']
raw=f.command(label,argv,input=code.encode(),timeout=300)
rows=[json.loads(line.split('MP_LABELS_POLICY=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_LABELS_POLICY=')];assert len(rows)==1
assert m.snapshot(state,'notes8-policy-after')==before and m.worker(native,'notes8-policy-worker-after')==worker
f.save('candidate-policy-probe.json',dict(result='passed' if all(c['passed'] for c in rows[0]['checks']) else 'counterexample_confirmed',**rows[0],image=image,installed=False,all17tables_worker_exact=True,source_sha256=build['source_sha256']['platform_addons/mp_example_notes_labels/models.py']))
print(json.dumps(rows[0]))
