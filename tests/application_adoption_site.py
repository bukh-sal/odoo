"""Owned AP-02/03 disposable native application sites; never the retained pilot."""
import argparse
from pathlib import Path
import re
import subprocess
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'packages/platform_sdk')]
from aurora_tasks_site import TasksSite,POSTGRES,PROXY,load,write
from modular_platform.operator_store import OperatorStore
from modular_platform.job_operator import JobOperator


class AdoptionSite(TasksSite):
    def __init__(self,args):
        if not re.fullmatch(r'ap0[23]-[a-z0-9-]{1,45}',args.run):raise ValueError('Explicit disposable adoption identity required')
        self.args=args;self.local=ROOT/'.local/application-adoption'/args.run;self.private=self.local/'operator'

    def command(self,label,args,**kwargs):
        args=list(args)
        if args[:2]==['docker','run'] and '--name' in args and '--rm' not in args and '-d' not in args:args.insert(2,'--rm')
        return super().command(label,args,**kwargs)

    def retire(self):
        state=self.state();project=state['project'];target=load(self.private/'target.json')
        assert not (self.local/'retired.json').exists()
        assert re.fullmatch(r'mp-r0-r1release[0-9a-f]{12}',project)
        assert not JobOperator(OperatorStore(self.private/'control'),self.private/'target.json')._lanes()
        allowed={POSTGRES,PROXY,state['image_id'],target['image_id']}
        store=OperatorStore(self.private/'control')
        install=load(self.local/'install-bundle.json')['plan']['operation_id'];assert store.status(install)['state']=='completed'
        for label in ('fault','forward'):
            path=self.local/(label+'-operation.json')
            if path.exists():
                record=load(path);assert store.status(record['operation'])['state'] in {'completed','revoked'}
                assert record['phase'] in {'verified','failed_restored_job_authorization'}
                allowed.update([record['base']['image_id'],record['candidate']])
        selected=[n for n in subprocess.check_output(['docker','ps','-a','--format','{{.Names}}']).decode().splitlines() if n.startswith(project+'-')]
        inspected=json.loads(self.command('retirement-container-inventory',['docker','inspect',*selected])) if selected else []
        for row in inspected:
            labels=row['Config']['Labels'] or {}
            assert row['Name'].lstrip('/') in selected and row['Image'] in allowed
            assert (labels.get('com.modular.disposable')==project or labels.get('com.modular.deployment')==target['deployment_id']
                or labels.get('com.docker.compose.project')==project)
            assert all(m['Name'] in state['owned_resources']['volumes'] for m in row['Mounts'] if m['Type']=='volume')
        for kind in ('volumes','networks'):
            for name in state['owned_resources'][kind]:
                singular={'volumes':'volume','networks':'network'}[kind]
                row=json.loads(self.command('retirement-inspect-'+name,['docker',singular,'inspect',name]))[0]
                assert name.startswith(project+'_') and row['Labels']['com.modular.disposable']==project
        self.phase(state,'retiring_owned_site')
        if selected:self.command('retire-containers',['docker','rm','-f',*selected])
        self.command('retire-volumes',['docker','volume','rm',*state['owned_resources']['volumes']])
        self.command('retire-networks',['docker','network','rm',*state['owned_resources']['networks']])
        self.verify_retirement()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('actions',nargs='+',choices=['prepare','initialize','install','verify_install','status','retire','verify_retirement'])
    p.add_argument('--run',required=True);p.add_argument('--port',type=int,required=True)
    p.add_argument('--candidate',type=Path,default=Path('.local/operator/builds/20261108-at04-core49-02.json'))
    a=p.parse_args();site=AdoptionSite(a)
    for phase in a.actions:getattr(site,phase)()
