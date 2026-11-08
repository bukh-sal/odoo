"""AP-I temporary import-trap image and revoked read-only staged install proof."""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from application_adoption_site import load,write
from application_package import assemble_application
from reference_package import toml_value
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import inspect_image
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.release_staging import StageStore,prepare_staged_plan
from modular_platform.lifecycle_planning import installation_id
from modular_platform.plans import data_digest

PLUGIN='dev.aurora.projects_probe'
ADDON='mp_aurora_projects_probe'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['prepare','plan','retire'])
    p.add_argument('--run',default='ap03-slot-probe-01');a=p.parse_args();assert re.fullmatch(r'ap03-slot-probe-[0-9]{2}',a.run)
    local=ROOT/'.local/application-adoption'/a.run;marker=local/'state.json'
    public=ROOT/'docs/evidence/post-r1/application-adoption';receipt=public/(a.run+'-image.json')
    if a.phase=='prepare':
        assert not local.exists();protect_directory(local);write(marker,dict(phase='preparing',purpose='data-only import-trap;never install'))
        source=local/'source';addon=source/'native'/ADDON;addon.mkdir(parents=True)
        template=ROOT/'.local/application-adoption/apps/aurora-tasks'
        manifest=copy.deepcopy(tomllib.loads((template/'plugin.toml').read_text(encoding='utf-8')))
        manifest['plugin'].update(id=PLUGIN,version='0.0.1',name='PROBE - NEVER INSTALL',description='Data-only composition/planning import trap')
        manifest['runtime']['addon_name']=ADDON;manifest['compatibility']['platform']='==0.1.49';manifest['upgrade']['transitions']=[]
        manifest['data']=dict(models=['mp.aurora.project.probe'],extension_targets=[],contributions=[dict(kind='model',id='mp.aurora.project.probe',target='site',delete_policy='owned')])
        (source/'plugin.toml').write_text('\n'.join(k+' = '+toml_value(v) for k,v in manifest.items())+'\n',encoding='utf-8',newline='\n')
        (addon/'__init__.py').write_text('raise RuntimeError("PROBE MUST NEVER BE IMPORTED OR INSTALLED")\n',encoding='utf-8',newline='\n')
        (addon/'models.py').write_text("from odoo import models,fields\nclass Probe(models.Model):\n _name='mp.aurora.project.probe'\n name=fields.Char()\n",encoding='utf-8',newline='\n')
        (addon/'__manifest__.py').write_text(repr(dict(name='PROBE - NEVER INSTALL',version='19.0.0.0.1',depends=['web','mp_core'],data=[],license='LGPL-3'))+'\n',encoding='utf-8',newline='\n')
        shutil.copyfile(template/'LICENSE',source/'LICENSE')
        (source/'application.toml').write_text('schema_version=1\nmanifest="plugin.toml"\naddon="native/'+ADDON+'"\n[resources]\n"notices/LICENSE"="LICENSE"\n',encoding='utf-8',newline='\n')
        _,raw,_=assemble_application(source,'application.toml');artifacts=local/'artifacts';artifacts.mkdir()
        name=PLUGIN+'-0.0.1.mplug';(artifacts/name).write_bytes(raw)
        tasks=ROOT/'.local/application-adoption/artifacts/dev.aurora.tasks-0.2.3.mplug';shutil.copyfile(tasks,artifacts/tasks.name)
        images=load(ROOT/'.local/releases/foundation-r1-core49-tasks/images.json')
        recipe=dict(schema_version=2,foundation=dict(kit_manifest='sha256:396054faa70542a167ac5cd5e309579270e030cfbe4bb22c155b08c7bd215404',
            image_id=images['images']['application']['image_id'],inventory_digest=images['application_inventory_digest']),
            applications=[dict(artifact='artifacts/'+n,digest='sha256:'+hashlib.sha256((artifacts/n).read_bytes()).hexdigest()) for n in [tasks.name,name]])
        (local/'release.toml').write_text('\n'.join(k+' = '+toml_value(v) for k,v in recipe.items())+'\n',encoding='utf-8',newline='\n')
        write(marker,dict(phase='prepared',purpose='data-only import-trap;never install',recipe=str(local/'release.toml')))
    elif a.phase=='plan':
        state=load(marker);assert state['phase']=='prepared';state['phase']='planning';write(marker,state)
        candidate=load(receipt);assert candidate['state']=='verified'
        pilot=ROOT/'.local/application-adoption/ap01-pilot-01/operator';target=load(pilot/'target.json')
        before_target_digest=data_digest(target);private=protect_directory(local/'operator');write(private/'target.json',target)
        store=OperatorStore.initialize(private/'control',{target['deployment_id']:[target['sites'][0]['site_id']]},allow_noninteractive=False)
        assert store.policy['policy_version']==target['policy_version'] and store.policy['authorization_generation']==target['operator_authorization_generation']
        runtime=inspect_image(candidate['image_id']);artifacts=runtime['inventory']['artifacts']
        trust=dict(schema_version=1,mode='curated',generation=3,allow_unsigned_development=False,approved_digests=sorted(r['digest'] for r in artifacts.values()))
        write(private/'trust.json',trust);validator=configuration(private/'trust.json');catalog=Catalog(private/'catalog',validator)
        for plugin,row in sorted(artifacts.items()):
            raw=subprocess.check_output(['docker','run','--rm','--network','none','--entrypoint','/bin/cat',candidate['image_id'],'/opt/modular/artifacts/'+row['file']])
            path=private/row['file'];path.write_bytes(raw);catalog.add(path,expected_digest=row['digest'])
        native=StagedNativeExecutor(store,private/'target.json',private/'catalog',validator)
        before=native.observer.read();snapshot=catalog.snapshot();document=native.observer.state(before,snapshot)
        assert all(i['plugin_id']!=PLUGIN for site in before['sites'] for i in site['installations'])
        descriptor=StageStore(store,target,catalog).stage(candidate['image_id'])
        site,=before['sites'];target_row=dict(plugin_id=PLUGIN,site_id=site['site_id'],workspace_id=None,installation_id=installation_id(site,PLUGIN),action='install')
        bundle=prepare_staged_plan(document,before['sites'],snapshot,runtime,descriptor,targets=[target_row],operation_type='install',operation_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),base_runtime=before['runtime'])
        assert not bundle['plan']['permission_changes'] and not bundle['operation_lock'].get('native_core_changes')
        operation=bundle['plan']['operation_id'];state.update(phase='registering',operation=operation);write(marker,state)
        validate=native._validate();store.register(bundle,validate);review=store.review(operation,validate)
        assert store.status(operation)['mutation_started'] is False
        store.revoke(operation);assert store.status(operation)['state']=='revoked'
        after=native.observer.read();assert before['sites']==after['sites']
        assert data_digest(load(pilot/'target.json'))==before_target_digest
        state.update(phase='planned_revoked',image_id=candidate['image_id'],tag=candidate['tag'],plan_hash=bundle['plan_hash'])
        write(marker,state);write(public/(a.run+'-plan.json'),dict(result='passed_read_only_staged_site_native_install',operation=operation,plan_hash=bundle['plan_hash'],
            target=target_row,review_digest=data_digest(review),source_installations_unchanged=True,actual_registered_new_app=False,application_code_executed=False,
            independent_store_no_approval_and_revoked=True,source_image=target['image_id'],candidate_image=candidate['image_id'],core_or_public_contract_change=False))
    else:
        state=load(marker);assert state['phase']=='planned_revoked'
        assert not subprocess.check_output(['docker','ps','-aq','--filter','ancestor='+state['image_id']]).strip()
        image=json.loads(subprocess.check_output(['docker','image','inspect',state['tag']]))[0];assert image['Id']==state['image_id']
        subprocess.run(['docker','image','rm',state['tag']],check=True,capture_output=True)
        assert subprocess.run(['docker','image','inspect',state['tag']],capture_output=True).returncode!=0
        state['phase']='retired';write(marker,state);write(public/(a.run+'-retired.json'),dict(result='retired_owned_probe_image',image_id=state['image_id'],tag=state['tag'],
            no_deployment_containers_or_volumes_created=True,no_application_installed=True,pilot_and_shared_images_untouched=True))
    print(json.dumps(dict(phase=a.phase,result=load(marker)['phase'])),flush=True)

if __name__=='__main__':main()
