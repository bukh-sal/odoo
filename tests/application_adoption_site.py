"""Owned AP-02/03 disposable native application sites; never the retained pilot."""
import argparse
from pathlib import Path
import re
import subprocess
import json
from datetime import datetime,timezone
from uuid import uuid4
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'packages/platform_sdk')]
from aurora_tasks_site import TasksSite,POSTGRES,PROXY,load,write
from modular_platform.operator_store import OperatorStore
from modular_platform.job_operator import JobOperator
from modular_platform.deployment import inspect_image,DockerObserver
from modular_platform.native_executor import NativeExecutor
from modular_platform.lifecycle_planning import prepare_current_image_install
from modular_platform.plans import data_digest
from modular import configuration
from modular_platform.catalog import Catalog
from compose_application_set import expected_policy
from verify import verify,digest


class AdoptionSite(TasksSite):
    def __init__(self,args):
        if not re.fullmatch(r'ap0[23]-[a-z0-9-]{1,45}',args.run):raise ValueError('Explicit disposable adoption identity required')
        self.args=args;self.local=ROOT/'.local/application-adoption'/args.run;self.private=self.local/'operator'

    def command(self,label,args,**kwargs):
        args=list(args)
        if args[:2]==['docker','run'] and '--name' in args and '--rm' not in args and '-d' not in args:args.insert(2,'--rm')
        return super().command(label,args,**kwargs)

    def candidate(self):
        if self.args.run.startswith('ap02-'):return super().candidate()
        record=load(self.args.candidate)
        assert record['state']=='verified' and record['result']=='verified_application_set_on_pinned_foundation'
        kit=ROOT/'.local/releases/foundation-r1-core49-tasks';manifest=verify(kit)
        assert record['foundation']['kit_manifest']=='sha256:396054faa70542a167ac5cd5e309579270e030cfbe4bb22c155b08c7bd215404'
        assert 'sha256:'+digest(kit/'kit-inventory.json')==record['foundation']['kit_manifest']
        images=load(kit/'images.json')
        assert images['images']['application']['image_id']==record['foundation']['image_id'] and images['application_inventory_digest']==record['foundation']['inventory_digest']
        before=inspect_image(record['foundation']['image_id']);runtime=inspect_image(record['image_id'])
        assert before['inventory_digest']==record['foundation']['inventory_digest'] and runtime['inventory_digest']==record['inventory_digest']
        assert runtime['platform_version']==before['platform_version']=='0.1.49'
        names={'dev.aurora.tasks':'mp_aurora_tasks','dev.aurora.projects':'mp_aurora_projects','dev.aurora.projects_tasks':'mp_aurora_projects_tasks'}
        selected=record['applications'];assert all(names.get(row['plugin_id'])==row['addon'] for row in selected)
        assert runtime['inventory']['policy']==expected_policy(before,selected)
        assert all(runtime[k]==before[k] for k in ('python','architecture','markers','python_lock_digest','python_metadata'))
        assert runtime['inventory']['generated_patches']==before['inventory']['generated_patches']
        prefixes=tuple('addons/'+r['addon']+'/' for r in selected);archives=set()
        for row in selected:
            actual=runtime['inventory']['artifacts'][row['plugin_id']]
            assert all(actual[k]==row[k] for k in ('addon','version','digest'))
            archives.add('artifacts/'+actual['file']);old=before['inventory']['artifacts'].get(row['plugin_id'])
            if old:archives.add('artifacts/'+old['file'])
        old=before['inventory']['files'];new=runtime['inventory']['files']
        assert all(old.get(n)==new.get(n) or n.startswith(prefixes) or n in archives for n in old.keys()|new.keys())
        assert not any(runtime[k] for k in ('modified_files','missing_addon_files','unexpected_addon_files'))
        return dict(record=record,runtime=runtime,artifacts=runtime['inventory']['artifacts'],source_commit=manifest['source_commit'])

    def install(self):
        if self.args.run.startswith('ap02-'):return super().install()
        state=self.state();assert state['phase']=='core_only_ready'
        native=NativeExecutor(OperatorStore(self.private/'control'),self.private/'target.json',self.private/'catalog',configuration(self.private/'trust.json'))
        catalog=Catalog(native.catalog_root,native.validator,readonly=True);observed=native.observer.read();snapshot=catalog.snapshot()
        root=self.args.package;app=observed['runtime']['inventory']['artifacts'][root]
        bundle=prepare_current_image_install(native.observer.state(observed,snapshot),observed['sites'],snapshot,
            site_id=state['site_id'],workspace_ids=[],site_native=True,plugin_id=root,version=app['version'],artifact_digest=app['digest'],
            operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        assert not bundle['plan']['permission_changes'];write(self.local/'install-bundle.json',bundle)
        self.phase(state,'registering_native_install');validate=native._validate();native.store.register(bundle,validate)
        review=native.store.review(bundle['plan']['operation_id'],validate)
        native.store.approve(bundle['plan']['operation_id'],exact_hash=bundle['plan_hash'],noninteractive=True,revalidate=validate,
            acknowledgments=dict(destructive=True,trust_expansion=True,permission_expansion=True))
        self.phase(state,'applying_native_install');result=native.apply(bundle['plan']['operation_id'])
        assert result['state']=='completed' and result['traffic_resumed'];write(self.local/'install-result.json',result)
        write(self.local/'install-review.json',dict(review_digest=data_digest(review),plan_hash=bundle['plan_hash'],operation=bundle['plan']['operation_id']))
        self.verify_install()

    def continue_install(self):
        assert self.args.run.startswith('ap03-') and self.state()['phase']=='applying_native_install'
        bundle=load(self.local/'install-bundle.json');assert 'staged_image' not in bundle['operation_lock']
        native=NativeExecutor(OperatorStore(self.private/'control'),self.private/'target.json',self.private/'catalog',configuration(self.private/'trust.json'))
        status=native.store.status(bundle['plan']['operation_id'])
        assert status['state']=='approved' and status['phase']=='prepared' and not status['mutation_started']
        assert status['plan_hash']==bundle['plan_hash'] and not (self.local/'install-result.json').exists()
        result=native.apply(bundle['plan']['operation_id']);assert result['state']=='completed' and result['traffic_resumed']
        write(self.local/'install-result.json',result);self.verify_install()

    def verify_install(self):
        if self.args.run.startswith('ap02-'):return super().verify_install()
        state=self.state();assert state['phase']=='applying_native_install';assert load(self.local/'install-result.json')['state']=='completed'
        target=load(self.private/'target.json');reader=DockerObserver(target)
        catalog=Catalog(self.private/'catalog',configuration(self.private/'trust.json'),readonly=True)
        after=reader.state(reader.read(),catalog.snapshot())['state'];write(self.local/'installed-state.json',after)
        expected={t['plugin_id'] for t in load(self.local/'install-bundle.json')['operation_lock']['targets']}
        assert {r['plugin_id'] for r in after['installations']}==expected
        assert all(r['workspace_id'] is None and r['metadata_state']=='installed' for r in after['installations'])
        state.update(image_id=target['image_id'],database=target['sites'][0]['database'])
        assert self.sql(state,'verify-no-workspace-authority','SELECT (SELECT count(*) FROM mp_workspace),(SELECT count(*) FROM mp_membership),(SELECT count(*) FROM mp_workspace_plugin);').strip()==b'0|0|0'
        self.phase(state,'native_installed')

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
    p.add_argument('actions',nargs='+',choices=['prepare','initialize','install','continue_install','verify_install','status','retire','verify_retirement'])
    p.add_argument('--run',required=True);p.add_argument('--port',type=int,required=True)
    p.add_argument('--candidate',type=Path,default=Path('.local/operator/builds/20261108-at04-core49-02.json'))
    p.add_argument('--package',choices=['dev.aurora.projects','dev.aurora.projects_tasks'],default='dev.aurora.projects')
    a=p.parse_args();site=AdoptionSite(a)
    for phase in a.actions:getattr(site,phase)()
