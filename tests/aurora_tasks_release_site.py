"""Fresh populated sealed47 sources for Tasks adoption and useful Maintenance peer."""
import argparse
from datetime import datetime,timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from aurora_tasks_site import TasksSite,POSTGRES,PROXY,inspect_image,configuration,Catalog,load,write
from foundation_release import FoundationSite
from modular_platform import tasks_adoption as ta


SEED='''
import json
from odoo import api
from odoo.fields import Command
alice=api.Environment(env.cr,FIXTURE['users']['alice']['id'],{},su=False)
bob=api.Environment(env.cr,FIXTURE['users']['bob']['id'],{},su=False)
operator=FIXTURE['users']['operator']['id']
if SITE=='tasks':
    listing=alice['mp.aurora.task.list'].create(dict(name='Original47 shared list',member_ids=[Command.link(bob.uid)]))
    stage=alice['mp.aurora.task.stage'].create(dict(name='Original47 backlog',list_id=listing.id,sequence=7,done=False))
    assigned=alice['mp.aurora.task'].create(dict(name='Original47 assigned task',list_id=listing.id,stage_id=stage.id,
        assignee_id=operator,due_date='2040-01-20 12:00:00',description='Preserve original assignment and long-future due date'))
    closed_list=bob['mp.aurora.task.list'].create(dict(name='Original47 completed list'))
    done=bob['mp.aurora.task.stage'].create(dict(name='Original47 closed',list_id=closed_list.id,sequence=3,done=True))
    completed=bob['mp.aurora.task'].create(dict(name='Original47 completed task',list_id=closed_list.id,stage_id=done.id,
        assignee_id=alice.uid,due_date='2026-01-01 12:00:00'))
    null_list=alice['mp.aurora.task.list'].create(dict(name='Original47 no-stage list'))
    null_task=alice['mp.aurora.task'].create(dict(name='Original47 null-stage task',list_id=null_list.id))
    archived=alice['mp.aurora.task.list'].create(dict(name='Original47 archived list'))
    archived.write(dict(active=False))
    result=dict(list=listing.id,stage=stage.id,task=assigned.id,completed_list=closed_list.id,
        completed_stage=done.id,completed_task=completed.id,null_list=null_list.id,null_task=null_task.id,archived_list=archived.id)
else:
    env['res.users'].browse(alice.uid).write(dict(group_ids=[Command.link(env.ref('maintenance.group_equipment_manager').id)]))
    team=alice['maintenance.team'].create(dict(name='Original47 maintenance team'))
    equipment=alice['maintenance.equipment'].create(dict(name='Original47 foundation pump',maintenance_team_id=team.id))
    request=alice['maintenance.request'].create(dict(name='Original47 pump inspection',equipment_id=equipment.id,
        owner_user_id=alice.uid,user_id=alice.uid,maintenance_team_id=team.id))
    result=dict(team=team.id,equipment=equipment.id,request=request.id,stage=request.stage_id.id)
env.cr.commit()
print('MP_AT_SOURCE='+json.dumps(result))
'''


class ReleaseSite(TasksSite):
    def __init__(self,args):
        if not re.fullmatch(r'at04-[a-z0-9-]{1,50}',args.run) or args.site not in {'tasks','maintenance'}:
            raise ValueError('Explicit bounded release fixture identity required')
        self.args=args
        self.local=ROOT/'.local/aurora-tasks'/args.run/args.site
        self.private=self.local/'operator'

    def prepare(self):
        runtime=inspect_image(ta.SOURCE_IMAGE)
        assert runtime['inventory_digest']==ta.SOURCE_INVENTORY and runtime['platform_version']=='0.1.47'
        artifacts=runtime['inventory']['artifacts']
        assert ta.APP not in artifacts and len(artifacts)==5
        ids=subprocess.run(['docker','network','ls','-q'],check=True,capture_output=True).stdout.decode().split()
        existing=json.loads(subprocess.run(['docker','network','inspect',*ids],check=True,capture_output=True).stdout)
        used=[ipaddress.ip_network(r['Subnet']) for net in existing for r in (net.get('IPAM',{}).get('Config') or []) if r.get('Subnet')]
        subnets=None
        for offset in range(0,224,32):
            pair=[ipaddress.ip_network(f'10.203.159.{offset}/28'),ipaddress.ip_network(f'10.203.159.{offset+16}/28')]
            if not any(a.version==b.version and a.overlaps(b) for a in pair for b in used):
                subnets=dict(zip(['runtime','edge'],map(str,pair)));break
        if subnets is None:raise ValueError('No inspected free source fixture subnets')
        # The new immutable archive was already independently qualified in AT-03.
        # Catalog availability does not put it in the old47 image or install it.
        app=(ROOT/'.local/aurora-tasks/at03-native-03/operator/dev.aurora.tasks-0.2.2.mplug').read_bytes()
        assert 'sha256:'+hashlib.sha256(app).hexdigest()==ta.ARTIFACT
        trust=dict(schema_version=1,mode='curated',generation=1,allow_unsigned_development=False,
                   approved_digests=sorted([r['digest'] for r in artifacts.values()]+[ta.ARTIFACT]))
        self.prepare_resources(dict(images={k:dict(image_id=v) for k,v in {
            'application':ta.SOURCE_IMAGE,'postgres':POSTGRES,'proxy':PROXY}.items()},application_inventory_digest=ta.SOURCE_INVENTORY),
            '9045faa8972458afcc433d80748aeb2f3f52e783',json.dumps(trust).encode(),subnets=subnets)
        catalog=Catalog(self.private/'catalog',configuration(self.private/'trust.json'))
        for plugin,row in sorted(artifacts.items()):
            assert re.fullmatch(r'[a-z0-9._-]+\.mplug',row['file'])
            raw=self.command('source-archive-'+plugin.replace('.','-'),['docker','run','--rm','--network','none',
                '--log-driver','none','--entrypoint','/bin/cat',ta.SOURCE_IMAGE,'/opt/modular/artifacts/'+row['file']])
            assert 'sha256:'+hashlib.sha256(raw).hexdigest()==row['digest']
            path=self.private/row['file'];path.write_bytes(raw);catalog.add(path,expected_digest=row['digest'])
        path=self.private/'dev.aurora.tasks-0.2.2.mplug';path.write_bytes(app);catalog.add(path,expected_digest=ta.ARTIFACT)
        self.phase(self.state(),'source_archives_admitted')

    def initialize(self):
        state=self.state();assert state['phase']=='source_archives_admitted'
        addon=ta.ADDON if self.args.site=='tasks' else 'maintenance'
        self.initialize_core(state,'mp_shell,auth_password_policy,'+addon)
        raw=self.native(state,'legacy-app-seed',[],'FIXTURE='+repr(load(self.local/'fixtures.json'))+'\nSITE='+repr(self.args.site)+'\n'+SEED)
        rows=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_SOURCE=')]
        assert len(rows)==1
        write(self.local/'app-fixtures.json',rows[0])
        self.publish(state,prepare_assets=False)

    def install_references(self):
        assert self.state()['phase']=='core_only_ready'
        FoundationSite.install_selected(self,['org.example.notes','org.example.background'],'source-references')
        self.phase(self.state(),'source_references_installed')

    def observe(self):
        state=self.state();assert state['phase']=='source_references_installed'
        target=load(self.private/'target.json')
        effect=ta.observe_effects(target)
        ta.check_effects(effect,[state['site_id']])
        assert effect[0]['tasks_installed']==(self.args.site=='tasks')
        write(self.local/'source-witnesses.json',effect)
        self.phase(state,'source_qualified')
        print(json.dumps(dict(result='populated_source_ready',site=self.args.site,tables=len(effect[0]['retained_tables']),missing_stages=len(effect[0]['stage_additions']))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('actions',nargs='+',choices=['prepare','initialize','install_references','observe','status'])
    parser.add_argument('--run',required=True)
    parser.add_argument('--site',required=True,choices=['tasks','maintenance'])
    parser.add_argument('--port',required=True,type=int)
    args=parser.parse_args();site=ReleaseSite(args)
    for action in args.actions:getattr(site,action)()
