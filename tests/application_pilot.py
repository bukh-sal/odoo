"""AP-01 owned persistent fictional-data pilot, using the qualified installer."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'packages/platform_sdk')]
from aurora_tasks_site import TasksSite,load,write
from modular_platform.job_operator import JobOperator
from modular_platform.operator_store import OperatorStore
from verify import verify,digest


class Pilot(TasksSite):
    def __init__(self,args):
        if not re.fullmatch(r'ap01-pilot-[0-9]{2}',args.run):raise ValueError('Explicit owned pilot identity required')
        self.args=args
        self.local=ROOT/'.local/application-adoption'/args.run
        self.private=self.local/'operator'

    def command(self,label,args,**kwargs):
        args=list(args)
        # Keep complete private stdout/stderr, but avoid retaining every one-shot
        # native bootstrap/read helper in Docker Desktop. Services remain explicit.
        if args[:2]==['docker','run'] and '--name' in args and '--rm' not in args and '-d' not in args:
            args.insert(2,'--rm')
        return super().command(label,args,**kwargs)

    def prepare(self):
        kit=ROOT/'.local/releases/foundation-r1-core49-tasks'
        manifest=verify(kit)
        assert manifest['stage']=='qualified_local_foundation_tasks_1'
        assert digest(kit/'kit-inventory.json')=='396054faa70542a167ac5cd5e309579270e030cfbe4bb22c155b08c7bd215404'
        selected=load(self.args.candidate)
        assert selected['image_id']==load(kit/'images.json')['images']['application']['image_id']
        super().prepare()
        state=self.state();state.update(purpose='persistent_local_development_pilot',synthetic_data_only=True,
            retention='Keep this explicitly named pilot for daily development; retire disposable siblings separately',
            sealed_kit_manifest_sha256=digest(kit/'kit-inventory.json'))
        write(self.local/'state.json',state)
        write(self.local/'pilot-intent.json',dict(run=self.args.run,project=state['project'],purpose=state['purpose'],
            url=state['url'],owned_resources=state['owned_resources'],synthetic_data_only=True,
            credentials_location=str(self.local/'account-passwords.json'),disposable_recovery_targets=False))

    def start_workers(self):
        assert self.state()['phase']=='native_installed'
        path=self.local/'worker-profile.json';assert not path.exists(),'Inspect previous independent profile intent'
        op=JobOperator(OperatorStore(self.private/'control'),self.private/'target.json')
        review=op.run('profile-review',urgent_lanes=1,bulk_lanes=1,shutdown_seconds=5)
        write(path,dict(phase='reviewed',approval=review['approval']))
        profile=op.run('profile-apply',approval=review['approval']);assert profile['state']=='ready'
        write(path,dict(phase='ready',profile=profile))
        state=self.state();target=load(self.private/'target.json');state.update(image_id=target['image_id'],database=target['sites'][0]['database'])
        self.phase(state,'pilot_ready')
        write(self.local/'pilot-ready.json',dict(result='pilot_ready',utc=datetime.now(timezone.utc).isoformat(),
            project=state['project'],url=state['url'],image_id=target['image_id'],inventory_digest=state['inventory_digest'],
            installed_application='dev.aurora.tasks',application_version='0.2.2',lanes=dict(urgent=1,bulk=1),
            independent_install_operation=load(self.local/'install-bundle.json')['plan']['operation_id'],
            persistent_development_purpose=True,credentials_location=str(self.local/'account-passwords.json')))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('actions',nargs='+',choices=['prepare','initialize','install','verify_install','start_workers','status'])
    p.add_argument('--run',default='ap01-pilot-01');p.add_argument('--port',type=int,default=18172)
    p.add_argument('--candidate',type=Path,default=Path('.local/operator/builds/20261108-at04-core49-02.json'))
    a=p.parse_args();pilot=Pilot(a)
    for action in a.actions:getattr(pilot,action)()
