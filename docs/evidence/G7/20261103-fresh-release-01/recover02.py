"""Normal separately reviewed CLI fresh restore and explicit resume, once each."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from dependency_recovery import LOCAL,PRIVATE,MARKER,f,context,prefix,options
def run(action):
 state,native=context();r=f.load(MARKER);assert r['state']=='recovery_required'
 assert f.load(PRIVATE/'authority-revocation.json')['state']=='verified'
 current=r.get('recovery',{}).get('state')
 expected={'prepare-restore':None,'restore':'restore_reviewed','prepare-resume':'restored_closed_verified','resume':'resume_reviewed'}[action]
 assert current==expected,(current,expected)
 args=prefix()+['plugin','recover',action,r['operation_id']]+options(native)
 kind='restore' if action in ('prepare-restore','restore') else 'resume';decision_path=PRIVATE/(kind+'-decision.json');hash_path=PRIVATE/(kind+'-decision-hash.json')
 if not action.startswith('prepare-'):
  sealed=f.load(hash_path);args+=['--decision',str(decision_path),'--decision-hash',sealed['decision_hash'],'--noninteractive']
 r['recovery']=dict(state='running_'+action);f.write(MARKER,r);f.phase(state,'g7_dependency_recovery_'+action)
 result=json.loads(f.command('g7-dependency-recovery-'+action,args,timeout=600))
 if action.startswith('prepare-'):
  decision=result['decision'];assert decision['operation_id']==r['operation_id'];assert decision.get('keep_traffic_closed') if action=='prepare-restore' else decision['action']=='resume_verified_restore'
  f.write(decision_path,decision);f.write(hash_path,dict(decision_hash=result['decision_hash']))
  f.save(action+'.json',dict(result='independent_exact_current_recovery_review_prepared',operation_id=r['operation_id'],decision_hash=result['decision_hash'],action=decision['action'],keep_traffic_closed=True))
  r['recovery']['state']=kind+'_reviewed'
 else:
  expected_state='restored_verified' if action=='restore' else 'restored_traffic_resumed';assert result['state']==expected_state
  f.save(action+'.json',result);config=f.load(native.target_path)
  state.update(active_db=config['sites'][0]['database'],image_id=config['image_id'],inventory_digest=config['published_release']['core_inventory_digest'])
  state['databases']=sorted(set(state['databases']+[state['active_db']]));fixture=f.load(LOCAL/'fixtures.json');fixture['database']=state['active_db'];f.write(LOCAL/'fixtures.json',fixture)
  r['recovery']['state']='restored_closed' if action=='restore' else 'resumed_needs_verification'
 f.write(MARKER,r);f.phase(state,'g7_dependency_'+r['recovery']['state']);f.guard(state)
 print('Ordinary separately reviewed recovery step completed: '+action,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare-restore','restore','prepare-resume','resume']);a=p.parse_args();run(a.action)
