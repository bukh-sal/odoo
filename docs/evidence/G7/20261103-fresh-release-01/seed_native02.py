"""Bounded real Notes/Canvas/filestore/original-actor terminal-job fixture."""
import base64,hashlib,json
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import job_dispatch as jobs
from odoo.addons.mp_core.dispatch import CallFrame
from modular_platform import durable
env.cr.rollback();assert env.cr.dbname==EXPECTED_DATABASE
env.cr.execute('SELECT (SELECT count(*) FROM mp_example_note),(SELECT count(*) FROM mp_example_canvas_board)');assert env.cr.fetchone()==(0,0)
env.cr.execute('SELECT count(*) FROM mp_job');assert env.cr.fetchone()[0]==0
env.cr.execute('SELECT count(*) FROM mp_outbox');assert env.cr.fetchone()[0]==0
env.cr.execute('SELECT state FROM mp_dispatch_control');controls=env.cr.fetchall();assert controls in ([],[('enabled',)])
if not controls:
 site=env['ir.config_parameter'].sudo().get_param('mp.site_id');release=env['ir.config_parameter'].sudo().get_param('mp.release_digest')
 durable.set_control(env.cr,site,release,'enabled')
notes={}
for workspace,actor in [('A','alice'),('B','bob')]:
 native=scoped_environment(api.Environment(env.cr,FIXTURE['users'][actor]['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
 notes[workspace]=[native['mp.example.note'].create(dict(title='Recovery   '+workspace+'  '+str(i),body='Bounded G7 dependency recovery fixture '+workspace+str(i))) for i in range(2)]
native=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
board=native['mp.example.canvas.board'].create(dict(name='Minimal recovery fixture',cards=[]))
payload=b'G7 actual dependency recovery attachment\n'
attachment=native['ir.attachment'].create(dict(name='g7-recovery-fixture.txt',datas=base64.b64encode(payload),mimetype='text/plain',res_model='mp.example.note',res_id=notes['A'][0].id))
native.flush_all();assert attachment.store_fname
binding=FIXTURE['bindings']['A']
frame=CallFrame(FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces']['A']['public_id'],FIXTURE['site_id'],binding['consumer_installation_id'],'org.example.notes',())
native=native(context={**native.context,'_mp_call_frame':frame})
ident=jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',dict(note_id=notes['A'][0].public_id,expected_revision=1),uuid4().hex,request_id=str(uuid4()))
env.cr.commit();invocation=jobs.prepare_one(env,str(uuid4()));assert invocation.claim.job_id==ident;env.cr.commit()
result=jobs.finish_one(env,invocation,jobs.compute(invocation));assert result['revision']==2;env.cr.commit()
env.cr.execute('SELECT state,attempts,result FROM mp_job WHERE public_id=%s',[ident]);job=env.cr.fetchone();assert job[0]=='completed' and job[1]==1
print('MP_G7_RECOVERY_SEED='+json.dumps(dict(notes={key:[n.public_id for n in rows] for key,rows in notes.items()},board_id=board.public_id,board_revision=1,attachment_id=attachment.id,attachment_store_fname=attachment.store_fname,attachment_sha256=hashlib.sha256(payload).hexdigest(),job_id=ident,job_state=job[0],job_attempts=job[1],original_actor='alice',notes_total=4)))
