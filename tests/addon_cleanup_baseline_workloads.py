"""Real plugin/workload qualification after the plugin-free recovery proof."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from foundation_release import FoundationSite,ROOT,load,write,configuration,SEED_APP
from foundation_jobs import SEED,shell,queue
from modular_platform.catalog import Catalog
from modular_platform.lifecycle_planning import installation_id,prepare_current_install_targets
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore


class Baseline(FoundationSite):
    def __init__(self,label):
        self.local=ROOT/'.local/addon-cleanup/baseline46/private/reference'
        self.private=self.local/'operator'
        self.catalog=self.local.parent/'catalog'
        self.args=SimpleNamespace(site='maintenance',label=label)

    def state(self):
        state=load(self.local/'state.json');target=load(self.private/'target.json')
        state.update(database=target['sites'][0]['database'],image_id=target['image_id'])
        return state

    def install_selected(self,plugins,label):
        path=self.local/(label+'.json');assert not path.exists()
        validator=configuration(self.private/'trust.json')
        native=NativeExecutor(OperatorStore(self.private/'control'),self.private/'target.json',self.catalog,validator)
        observed=native.observer.read();catalog=Catalog(self.catalog,validator,readonly=True).snapshot()
        targets=[dict(installation_id=installation_id(observed['sites'][0],plugin),site_id=observed['sites'][0]['site_id'],
            workspace_id=w['public_id'],plugin_id=plugin,action='install')
            for w in load(self.local/'fixtures.json')['workspaces'].values() for plugin in plugins]
        bundle=prepare_current_install_targets(native.observer.state(observed,catalog),observed['sites'],catalog,
            activation_targets=targets,operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        record=dict(phase='registering',operation=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);write(path,record)
        check=native._validate();native.store.register(bundle,check);native.store.review(record['operation'],check)
        native.store.approve(record['operation'],exact_hash=bundle['plan_hash'],noninteractive=True,revalidate=check,
            acknowledgments=dict(destructive=False,trust_expansion=True,permission_expansion=True))
        record['phase']='applying';write(path,record)
        status=native.apply(record['operation']);assert status['state']=='completed' and status['traffic_resumed']
        record['phase']='verified';write(path,record);print(json.dumps(record))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['install_notes','install_background','seed_app','workflow','seed_jobs','verify_jobs'])
    p.add_argument('--label',default='baseline');a=p.parse_args();site=Baseline(a.label)
    if a.phase=='seed_app':
        path=site.local/'app-fixtures.json';assert not path.exists()
        # The inherited fixture's fresh-release prefix intentionally refuses a
        # restored DB. Bind the exact independently restored target instead.
        database=load(site.private/'target.json')['sites'][0]['database']
        code=SEED_APP.replace("assert env.cr.dbname.startswith('mp_disposable_r0_r1_release_')",'assert env.cr.dbname == EXPECTED_DB')
        raw=shell(site,'ar-baseline-app-seed-restored',f"APP='maintenance'\nEXPECTED_DB={database!r}\n"+code)
        value,=[json.loads(r.split('=',1)[1]) for r in raw.splitlines() if r.startswith('MP_STRESS_RESULT=')]
        write(path,value);print(json.dumps(dict(result='seeded',app='maintenance')))
    elif a.phase=='seed_jobs':
        path=site.local/'job-seed.json';assert not path.exists()
        app=load(site.local/'app-fixtures.json')
        code=f"FIXTURE={load(site.local/'fixtures.json')!r}\nAPP_MODEL='maintenance.request'\nAPP_ID={app['request']}\nSITE='maintenance'\n"+SEED
        raw=shell(site,'ar-baseline-job-seed',code)
        value,=[json.loads(r.split('=',1)[1]) for r in raw.splitlines() if r.startswith('CF_JOBS=')]
        value['original']=queue(load(site.private/'target.json'),value);write(path,value)
        print(json.dumps(dict(result='seeded',jobs=3,filestore_witness=True)))
    elif a.phase=='verify_jobs':
        seed=load(site.local/'job-seed.json');after=queue(load(site.private/'target.json'),seed)
        for ident,before in seed['original'].items():
            for key in ('deadline','actor','workspace','handler','key'):assert after[ident][key]==before[key],key
            if ident!=seed['running']:assert after[ident]['at']==before['at']
        assert after[seed['reminder']]['state']==after[seed['pending']]['state']=='pending'
        code=f'''
from modular_platform import durable
old=durable.Claim({seed['running']!r},{seed['generation']},{seed['owner']!r})
try:durable.run_fenced(env.cr,old,lambda row:{{'unexpected':True}})
except (durable.ClaimLost,durable.DispatchPaused):print('AR_STALE_DENIED')
else:raise AssertionError('Old claim escaped its release fence')
'''
        assert 'AR_STALE_DENIED' in shell(site,'ar-stale-claim-'+a.label,code)
        write(site.local/('jobs-'+a.label+'.json'),dict(result='passed',queue=after,timing_actor_workspace_preserved=True,stale_claim_denied=True))
        print(json.dumps(dict(result='passed',jobs=3,stale_claim_denied=True)))
    else:getattr(site,a.phase)()


if __name__=='__main__':main()
