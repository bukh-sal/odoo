"""Operator-owned image candidates and exact staged native release plans."""
import copy
from datetime import datetime,timezone
import os
from pathlib import Path
import re

from .contracts import load_json,plan_hash
from .deployment import DockerObserver,inspect_image
from .lifecycle_planning import installation_id
from .operator_os import OperatorError,OperationLocks,protect_directory,verify_private_directory
from .operator_store import _write_new
from .planning_cli import prepare_document
from .plans import check_bundle,data_digest,_display
from .projection import runtime_inputs
from .resolution import binding_matches_scope


def prepare_staged_plan(document,sites,catalog,runtime,descriptor,*,targets,operation_type,operation_id,created_at):
    if operation_type not in ('install','upgrade'):
        raise OperatorError('Staged native planning requires install or upgrade')
    selected,environment,provenance=runtime_inputs(runtime,catalog)
    by_plugin={item['manifest']['plugin']['id']:item for item in selected}
    by_site={site['site_id']:site for site in sites}
    for target in targets:
        site=by_site.get(target['site_id'])
        if (site is None or not any(item['workspace_id']==target['workspace_id'] and item['state']=='active' for item in site['workspaces'])
                or target['plugin_id'] not in by_plugin or target['action'] not in ('install','upgrade')
                or by_plugin[target['plugin_id']]['manifest']['runtime']['kind']!='native'
                or target['installation_id']!=installation_id(site,target['plugin_id'])):
            raise OperatorError('Staged target differs from current site/workspace/installation identity')
    current=document['state']['release_lock']
    old={item['plugin_id']:item for item in current['plugins']}
    requested={plugin:'=='+item['manifest']['plugin']['version'] for plugin,item in by_plugin.items()}
    update=[plugin for plugin,item in by_plugin.items() if plugin not in old or old[plugin]['digest']!=item['digest']]
    old_python={item['name'].lower():item for item in current['python_solution']}
    update.extend('python:'+item['name'] for item in runtime['python_metadata']
        if item['name'].lower() not in old_python or old_python[item['name'].lower()]['digest']!=item['digest'])
    target_document=copy.deepcopy(document)
    target_document.update(environment=environment,provenance=provenance,python_metadata=runtime['python_metadata'])
    target_document['request']={'operation_type':operation_type,'requested':requested,'targets':copy.deepcopy(targets),
        'update':update,'core_python':[item['name']+'=='+item['version'] for item in runtime['python_metadata']],
        'operation_id':operation_id,'created_at':created_at}
    bundle=prepare_document(target_document,catalog)
    for target in targets:
        required=set(by_plugin[target['plugin_id']]['manifest']['dependencies']['plugins'])
        required.update(item['provider'] for item in bundle['operation_lock']['release']['service_selection']
            if item['consumer']==target['plugin_id'] and not item['optional']
            and binding_matches_scope(item,target['site_id'],target['workspace_id']))
        previous=next((item for item in document['state']['installations'] if item['installation_id']==target['installation_id']
            and item['workspace_id']==target['workspace_id']),None)
        needs_enabled=target['action']=='install' or previous and previous['feature_state']=='enabled'
        for plugin in required:
            planned=next((item for item in targets if item['plugin_id']==plugin and item['site_id']==target['site_id']
                and item['workspace_id']==target['workspace_id']),None)
            existing=next((item for item in document['state']['installations'] if item['plugin_id']==plugin
                and item['site_id']==target['site_id'] and item['workspace_id']==target['workspace_id']),None)
            if planned and planned['action']=='install':continue
            if not existing or existing['state']!='installed' or existing['metadata_state']!='installed' or needs_enabled and existing['feature_state']!='enabled':
                raise OperatorError('Staged activation omits an installed/enabled required workspace dependency')
    actual={item['plugin_id']:item['digest'] for item in bundle['operation_lock']['release']['plugins']}
    expected={plugin:item['digest'] for plugin,item in by_plugin.items()}
    if actual!=expected or descriptor['inventory_digest']!=runtime['inventory_digest'] or descriptor['runtime_digest']!=data_digest(runtime):
        raise OperatorError('Solved release differs from the independently staged executable image')
    bundle['operation_lock']['staged_image']=copy.deepcopy(descriptor)
    bundle['operation_lock']['known_unknowns'].append('The staged image includes fully trusted native core/runtime code; image rollback alone does not restore database state.')
    bundle['plan']['dependency_lock_digest']=data_digest(bundle['operation_lock'])
    bundle['plan_hash']=plan_hash(bundle['plan'])
    bundle['display']=_display(bundle['plan'],bundle['operation_lock'])
    check_bundle(bundle,document['state'])
    return bundle


class StageStore:
    def __init__(self,store,configuration,catalog):
        self.store,self.configuration,self.catalog=store,configuration,catalog
        self.root=store.root/'releases'/configuration['deployment_id']

    def stage(self,image_id):
        config=self.configuration
        with OperationLocks(self.store.root/'locks',config['deployment_id'],[site['site_id'] for site in config['sites']]):
            self.store._authorize_plan({'deployment_id':config['deployment_id'],'site_ids':[site['site_id'] for site in config['sites']],
                'policy_version':config['policy_version'],'operator_authorization_generation':config['operator_authorization_generation']})
            DockerObserver(config).read() # Verify the selected current target before stage enrollment.
            runtime=inspect_image(image_id);snapshot=self.catalog.snapshot()
            runtime_inputs(runtime,snapshot) # All packaged artifact identities/trust must exist.
            record={'schema_version':1,'base_configuration':config,'image_id':image_id,'runtime':runtime,
                'staged_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
            descriptor={'stage_digest':data_digest(record),'base_image_id':config['image_id'],'target_image_id':image_id,
                'inventory_digest':runtime['inventory_digest'],'runtime_digest':data_digest(runtime)}
            protect_directory(self.root)
            path=self.root/(descriptor['stage_digest'][7:]+'.json')
            if path.exists():
                self.store._regular(path)
                if load_json(path.read_bytes())!=record:raise OperatorError('Immutable staged release conflict')
            else:_write_new(path,record)
            temporary=self.root/('active-'+descriptor['stage_digest'][7:]+'.tmp')
            _write_new(temporary,descriptor)
            os.replace(temporary,self.root/'active.json')
            return descriptor

    def load(self,descriptor=None,*,recheck=True):
        verify_private_directory(self.root)
        active=self.root/'active.json';self.store._regular(active)
        selected=load_json(active.read_bytes())
        if descriptor is not None and descriptor!=selected:
            raise OperatorError('Independently selected staged release changed; prepare/review again')
        descriptor=selected
        if (set(descriptor)!={'stage_digest','base_image_id','target_image_id','inventory_digest','runtime_digest'}
                or any(not isinstance(value,str) or not re.fullmatch('sha256:[0-9a-f]{64}',value) for value in descriptor.values())):
            raise OperatorError('Exact immutable staged image descriptor required')
        path=self.root/(descriptor['stage_digest'][7:]+'.json');self.store._regular(path);record=load_json(path.read_bytes())
        if (data_digest(record)!=descriptor['stage_digest'] or record['base_configuration']!=self.configuration
                or record['image_id']!=descriptor['target_image_id'] or self.configuration['image_id']!=descriptor['base_image_id']
                or data_digest(record['runtime'])!=descriptor['runtime_digest'] or record['runtime']['inventory_digest']!=descriptor['inventory_digest']):
            raise OperatorError('Staged image/configuration preimage mismatch or stale deployment')
        if recheck and inspect_image(record['image_id'])!=record['runtime']:
            raise OperatorError('Staged image runtime metadata changed since independent observation')
        runtime_inputs(record['runtime'],self.catalog.snapshot())
        return copy.deepcopy(descriptor),copy.deepcopy(record)
