"""Actual fresh-target recovery for the failed different-image metadata upgrade."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from upgrade import context,ROOT,OUT,PRIVATE,MARKER,phase,f,j,base
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.restore_continuation import FILE_OBSERVATION

def recover(action):
    state,native=context();record=f.load(MARKER)
    phases={'prepare-restore':('recovery_required','restore_reviewed'),'restore':('restore_reviewed','restored_closed'),
        'prepare-resume':('restored_verified','resume_reviewed'),'prepare-resume-current':('restored_verified','resume_reviewed'),'resume':('resume_reviewed','resumed')}
    expected,finished=phases[action];assert record['state']==expected
    manifest=f.load(native.store.root/'checkpoints'/record['operation_id']/'manifest.json')
    if 'original_database' not in record:record['original_database']=manifest['configuration']['sites'][0]['database']
    filename='restore-decision.json' if 'restore' in action else 'resume-current-decision.json' if action=='prepare-resume-current' else record.get('resume_decision_file','resume-decision.json');path=PRIVATE/filename
    args=base.prefix()+['plugin','recover','prepare-resume' if action=='prepare-resume-current' else action,record['operation_id']]+base.options(native)
    if not action.startswith('prepare-'):
        seal=f.load(path.with_suffix('.hash.json'));args+=['--decision',str(path),'--decision-hash',seal['decision_hash'],'--noninteractive']
    phase(record,'running_'+action);f.phase(state,'image_recovery_'+action)
    result=json.loads(f.command('image-recovery-'+action,args,timeout=600))
    if action.startswith('prepare-'):
        f.write(path,result['decision']);f.write(path.with_suffix('.hash.json'),dict(decision_hash=result['decision_hash']))
        f.save(action+'.json',dict(result='exact_private_changed_image_recovery_review',decision_hash=result['decision_hash'],review=result['decision']['review'],action=result['decision']['action']))
        if action=='prepare-resume-current':record['resume_decision_file']=filename
    else:
        assert result['state']==('restored_verified' if action=='restore' else 'restored_traffic_resumed');f.save(action+'.json',result)
        target=f.load(native.target_path);state['active_db']=target['sites'][0]['database'];state['databases']=sorted(set(state['databases']+[state['active_db']]))
        fixture=f.load(j.LOCAL/'fixtures.json');fixture['database']=state['active_db'];f.write(j.LOCAL/'fixtures.json',fixture)
    phase(record,finished);f.phase(state,'image_recovery_'+finished);f.guard(state)
    print('Actual changed-image reviewed recovery action complete: '+action,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare-restore','restore','prepare-resume','prepare-resume-current','resume']);a=p.parse_args();recover(a.action)
