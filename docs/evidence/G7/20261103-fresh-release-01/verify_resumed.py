"""Actual resumed native HTTP/authority/attachment checks and original preservation."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from dependency_recovery import ROOT,OUT,LOCAL,PRIVATE,MARKER,f,context,snapshot,OLD
from modular_platform.dispatch_operator import DispatchMaintenance
import r1_probe
state,native=context();r=f.load(MARKER);assert r['recovery']['state']=='resumed_needs_verification' and state['image_id']==OLD
fixture=f.load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL
client=r1_probe.Client(state,fixture,'alice');views={}
for workspace in ('A','B'):
 result=client.native('get_views',workspace=workspace,kwargs=dict(views=[[False,'list'],[False,'form']],options=dict(toolbar=False)));assert {'list','form'}<=set(result['views']);views[workspace]=sorted(result['views'])
seed=f.load(PRIVATE/'seed.json');note=client.call('get',dict(note_id=seed['notes']['A'][0]),workspace='A');assert note['revision']==2 and note['title']=='Recovery A 0'
client.call('get',dict(note_id=seed['notes']['B'][0]),workspace='A',expect=404,code='NOT_FOUND')
bob=r1_probe.Client(state,fixture,'bob');bob.native('search_read',args=[[]],kwargs={'fields':['public_id','title']},workspace='B',deny=True)
code="import base64,hashlib,json;assert env.cr.dbname=="+repr(state['active_db'])+";a=env['ir.attachment'].browse("+str(seed['attachment_id'])+");raw=base64.b64decode(a.datas);assert hashlib.sha256(raw).hexdigest()=="+repr(seed['attachment_sha256'])+";print('MP_G7_ATTACHMENT='+json.dumps(dict(attachment_read=True,sha256=hashlib.sha256(raw).hexdigest(),native_operator_only=True)))"
raw=f.native(state,'g7-recovery-attachment-read',[],code);checks=[json.loads(line.split('MP_G7_ATTACHMENT=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_G7_ATTACHMENT=')];assert len(checks)==1
closed=json.loads((LOCAL/'logs/g7-dependency-restored-closed-data.stdout').read_bytes());after=snapshot(state,'g7-dependency-resumed-data')
assert {k:v for k,v in after.items() if v is not None}==closed
dispatch=DispatchMaintenance(native).inspect();assert dispatch['control']['state']=='enabled' and dispatch['job_states']==dict(completed=1)
status=native.store.status(r['operation_id']);assert status['state']=='revoked' and status['phase']=='restore_traffic_resumed' and status['traffic_resumed']
original=f.load(LOCAL/'original-preservation-query.json');current=json.loads(f.command('g7-dependency-original-after-recovery',['docker','exec','-i',original['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',original['database'],'-v','ON_ERROR_STOP=1'],input=original['query'].encode()));assert current==original['expected'];f.guard(state)
f.save('resumed-http.json',dict(result='passed_actual_dependency_fault_reviewed_fresh_restore_separate_resume',operation_id=r['operation_id'],configuration_generation=native.config['generation'],native_image=state['image_id'],fresh_database=state['active_db'],native_Odoo_views=views,original_Alice_note_revision=2,foreign_workspace404=True,current_BobB_revocation_denied_after_restore=True,attachment=checks[0],no_new_business_or_job_effect=True,original17table_hashes_and_configs_exact=True,dispatch=dispatch,operation_status=status,browser_rendering=False,limits=['Recovered baseline remains old31/core20 intentionally. Target570 full fresh release and normal final qualification remain.','Standalone operator-owned native attachment only; workspace attachments remain unavailable.','No populated pending/in-flight or remote effect recovery claim from this terminal-native-job fixture.']))
r['recovery']['state']='qualified';r['state']='dependency_fault_restore_qualified';f.write(MARKER,r);f.phase(state,'g7_dependency_fault_restore_qualified');print('Actual separate resume/native views/authority/attachment/data checks passed; working original unchanged',flush=True)
