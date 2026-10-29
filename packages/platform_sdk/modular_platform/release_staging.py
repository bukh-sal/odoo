"""Operator-owned image candidates and exact staged native release plans."""
import copy
from datetime import datetime,timezone
import os
from pathlib import Path
import re
from packaging.version import Version

from .contracts import load_json,plan_hash
from .deployment import DockerObserver,inspect_image
from .lifecycle_planning import installation_id, install_scope_spec, install_activation_targets
from .operator_os import OperatorError,OperationLocks,protect_directory,verify_private_directory
from .operator_store import _write_new
from .planning_cli import prepare_document
from .plans import check_bundle,data_digest,_display
from .projection import runtime_inputs
from .resolution import binding_matches_scope, resolve_release
from .native_versions import PARSER_PATH,reviewed_transition


def validate_platform_deploy(base,runtime,descriptor):
    if base is None or descriptor['base_image_id']==descriptor['target_image_id']:
        raise OperatorError('Platform deploy requires independently observed base and distinct image')
    before,after=base['inventory'],runtime['inventory']
    if (before.get('artifacts')!=after.get('artifacts') or base['python_metadata']!=runtime['python_metadata']
            or base['python_lock_digest']!=runtime['python_lock_digest'] or before['native_addons']!=after['native_addons']
            or before['policy']!=after['policy'] or before.get('generated_patches',[])!=after.get('generated_patches',[])):
        raise OperatorError('Platform deploy cannot change package/Python/native inventory policy')
    manifests=base.get('native_manifests');new_manifests=runtime.get('native_manifests')
    if not manifests or not new_manifests or manifests.keys()!=new_manifests.keys():
        raise OperatorError('Platform deploy requires independently read native manifests')
    if any({key:value for key,value in manifest.items() if key!='assets'}!=
            {key:value for key,value in new_manifests[name].items() if key!='assets'} for name,manifest in manifests.items()):
        raise OperatorError('Platform deploy cannot change native manifest metadata beyond assets')
    old,new=before['files'],after['files']
    changed=sorted(name for name in old.keys()|new.keys() if old.get(name)!=new.get(name))
    if not changed:raise OperatorError('Platform deploy requires a concrete inventoried source change')
    packaged={item['addon'] for item in before.get('artifacts',{}).values()}
    platform={name for name in before['native_addons'] if name.startswith('mp_') and name not in packaged}
    allowed_prefixes=('packages/platform_sdk/','packages/contracts/',*(f'addons/{name}/static/' for name in platform))
    allowed_manifests={f'addons/{name}/__manifest__.py' for name in platform}
    if any(not name.startswith(allowed_prefixes) and name not in allowed_manifests for name in changed):
        raise OperatorError('Platform deploy includes native/upstream files requiring controlled migrations')
    return [{'path':name,'previous_sha256':old.get(name),'target_sha256':new.get(name)} for name in changed]


CORE_ADDONS=frozenset({'mp_compat','mp_identity','mp_core','mp_shell'})
CORE_VERSION=r'19\.0\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)'


def validate_core_upgrade(base,runtime,descriptor):
    """Versioned platform maintenance, deliberately distinct from static deploy."""
    if base is None or descriptor['base_image_id']==descriptor['target_image_id']:
        raise OperatorError('Core upgrade requires independently observed base and distinct image')
    before,after=base['inventory'],runtime['inventory']
    if (before.get('artifacts')!=after.get('artifacts') or base['python_metadata']!=runtime['python_metadata']
            or base['python_lock_digest']!=runtime['python_lock_digest'] or before['native_addons']!=after['native_addons']
            or before['policy']!=after['policy']):
        raise OperatorError('Core upgrade must preserve package/Python/native dependency policy')
    manifests,new_manifests=base.get('native_manifests'),runtime.get('native_manifests')
    if not manifests or not new_manifests or manifests.keys()!=new_manifests.keys():
        raise OperatorError('Core upgrade requires independently read native manifests')
    old,new=before['files'],after['files']
    changed=sorted(name for name in old.keys()|new.keys() if old.get(name)!=new.get(name))
    packaged={item['addon'] for item in before.get('artifacts',{}).values()}
    allowed=(CORE_ADDONS & manifests.keys()) - packaged
    prefixes=('packages/platform_sdk/','packages/contracts/',*(f'addons/{name}/' for name in allowed))
    parser_changed=PARSER_PATH in changed
    if parser_changed and (not reviewed_transition(before,after) or 'mp_compat' not in allowed
            or 'addons/mp_compat/__manifest__.py' not in changed):
        raise OperatorError('Native numeric correction requires exact reviewed bytes/provenance and versioned compatibility maintenance')
    if not parser_changed and before.get('generated_patches',[])!=after.get('generated_patches',[]):
        raise OperatorError('Core upgrade cannot alter generated patch attestations')
    if any(not name.startswith(prefixes) and not (parser_changed and name==PARSER_PATH) for name in changed):
        raise OperatorError('Core upgrade includes packaged/upstream/unsupported native changes')
    touched={name for name in allowed if any(path.startswith(f'addons/{name}/') for path in changed)}
    if not touched or any(manifests[name]!=new_manifests[name] for name in manifests.keys()-touched):
        raise OperatorError('Core upgrade needs a concrete versioned core source change')
    upgrades=[]
    for name in sorted(touched):
        prior,version=manifests[name].get('version'),new_manifests[name].get('version')
        if (not isinstance(prior,str) or not isinstance(version,str) or not re.fullmatch(CORE_VERSION,prior)
                or not re.fullmatch(CORE_VERSION,version) or Version(version)<=Version(prior)
                or f'addons/{name}/__manifest__.py' not in changed):
            raise OperatorError('Every changed core addon requires a strictly increasing canonical native version')
        migrations=[]
        for path in sorted(old.keys()|new.keys()):
            prefix=f'addons/{name}/migrations/'
            if not path.startswith(prefix):continue
            directory=path[len(prefix):].split('/')[0]
            if not re.fullmatch(CORE_VERSION,directory):
                raise OperatorError('Core migration requires a canonical native version directory')
            if Version(directory)<=Version(prior) and old.get(path)!=new.get(path):
                raise OperatorError('Core upgrade cannot rewrite previously applicable migrations')
            if Version(prior)<Version(directory)<=Version(version) and path in new:
                migrations.append({'path':path,'sha256':new[path]})
        upgrades.append({'addon':name,'previous_version':prior,'target_version':version,'migrations':migrations})
    return ([{'path':name,'previous_sha256':old.get(name),'target_sha256':new.get(name)} for name in changed],upgrades)


def validate_plugin_core_stability(base,runtime):
    if base is None:raise OperatorError('Native plugin plan requires independently observed base runtime')
    packaged={item['addon'] for image in (base,runtime) for item in image['inventory'].get('artifacts',{}).values()}
    prefixes=('artifacts/','packages/platform_sdk/','packages/contracts/',*(f'addons/{name}/' for name in packaged))
    old,new=base['inventory']['files'],runtime['inventory']['files']
    if any(old.get(path)!=new.get(path) and not path.startswith(prefixes) for path in old.keys()|new.keys()):
        raise OperatorError('Plugin operation cannot carry native core/upstream changes; use explicit core maintenance')


def prepare_staged_plan(document,sites,catalog,runtime,descriptor,*,targets,operation_type,operation_id,created_at,base_runtime=None,feature_states=()):
    if runtime.get('published_release_protocol')!=1:
        raise OperatorError('Staged native operations require an image with the published-release profile reader')
    if operation_type=='remove':
        if feature_states:raise OperatorError('Source removal cannot change feature availability')
        from .artifact_removal import prepare_staged_removal
        return prepare_staged_removal(document,sites,catalog,runtime,descriptor,targets=targets,
            operation_id=operation_id,created_at=created_at,base_runtime=base_runtime)
    if operation_type not in ('install','upgrade','deploy','core_upgrade'):
        raise OperatorError('Staged native planning requires install, upgrade, platform deploy or core upgrade')
    if operation_type in ('install','upgrade'):validate_plugin_core_stability(base_runtime,runtime)
    platform_diff=validate_platform_deploy(base_runtime,runtime,descriptor) if operation_type=='deploy' else None
    core_changes=None
    if operation_type=='core_upgrade':
        platform_diff,core_changes=validate_core_upgrade(base_runtime,runtime,descriptor)
        for site in sites:
            native={item['addon']:item for item in site['native_modules']}
            if any(change['addon'] not in native or native[change['addon']]['state']!='installed'
                    or native[change['addon']]['version']!=change['previous_version'] for change in core_changes):
                raise OperatorError('Core upgrade base database versions must match independently observed source')
    selected,environment,provenance=runtime_inputs(runtime,catalog)
    by_plugin={item['manifest']['plugin']['id']:item for item in selected}
    by_site={site['site_id']:site for site in sites}
    reinstall=operation_type=='install' and any(i['metadata_state']=='removed' and any(
        t['site_id']==site['site_id'] and t['plugin_id']==i['plugin_id'] for t in targets) for site in sites for i in site['installations'])
    reinstall_spec=None
    if reinstall:
        if any(t['action']!='install' for t in targets):raise OperatorError('Reinstall requires initial-install targets; upgrade existing changed dependencies separately first')
        activation=install_activation_targets({'operation_lock':{'targets':targets,'feature_states':list(feature_states)}}) if feature_states else targets
        ids={i['installation_id']:i['plugin_id'] for i in document['state']['installations']}
        choices={(ids[b['consumer_installation_id']],b['alias'],b['site_id'],b['workspace_id']):b['provider_plugin_id'] for b in document['state'].get('bindings',[])}
        solution=resolve_release(selected,runtime['python_metadata'],environment,
            {p['plugin_id']:'=='+p['version'] for p in selected},scoped_provider_choices=choices,
            core_python=[p['name']+'=='+p['version'] for p in runtime['python_metadata']])
        entries={p['plugin_id']:dict(runtime=p['manifest']['runtime']['kind'],native_addon=p['manifest']['runtime'].get('addon_name'),
                 hard_dependencies=p['manifest']['dependencies']['plugins'],permissions=p['manifest']['permissions']) for p in selected}
        reinstall_spec=install_scope_spec(document,sites,activation_targets=activation,entries=entries,service_selection=solution['bindings'])
        targets=reinstall_spec['targets'];feature_states=reinstall_spec['feature_states']
    elif feature_states:
        raise OperatorError('Post-feature states require a validated retained-scope reinstall')
    feature_map={(r['installation_id'],r['workspace_id']):r['availability'] for r in feature_states}
    for target in targets:
        site=by_site.get(target['site_id'])
        if (site is None or not any(item['workspace_id']==target['workspace_id'] and (item['state']=='active' or feature_map.get((target['installation_id'],target['workspace_id']))=='suspended') for item in site['workspaces'])
                or target['plugin_id'] not in by_plugin or target['action'] not in (('deploy',) if operation_type in ('deploy','core_upgrade') else ('install','upgrade'))
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
    grants={(site['site_id'],item['workspace_id'],item['installation_id'],item['capability']):item for site in sites for item in site.get('grants',[])}
    changes=[]
    for target in targets:
        prior={item['capability'] for item in old.get(target['plugin_id'],{}).get('permissions',{}).get('requests',[])}
        for requested_capability in by_plugin[target['plugin_id']]['manifest']['permissions']['requests']:
            capability=requested_capability['capability']
            existing=grants.get((target['site_id'],target['workspace_id'],target['installation_id'],capability))
            if (not existing and target['action']=='install') or target['action']=='upgrade' and capability not in prior:
                changes.append({'plugin_id':target['plugin_id'],'workspace_id':target['workspace_id'],'capability':capability,'action':'grant'})
    target_document['request']['permission_changes']=changes
    if reinstall_spec is not None:
        target_document['request']['permission_changes']=reinstall_spec['permission_changes']
        target_document['request']['feature_states']=list(feature_states)
    bundle=prepare_document(target_document,catalog)
    if operation_type in ('deploy','core_upgrade'):
        if (bundle['operation_lock']['bindings']!=document['state'].get('bindings',[])
                or bundle['operation_lock']['endpoints']!=document['state'].get('endpoints',[]) or bundle['plan']['permission_changes']):
            raise OperatorError('Platform deploy must preserve bindings/endpoints/grants')
        bundle['operation_lock']['platform_source_diff']=platform_diff
        if core_changes is not None:bundle['operation_lock']['native_core_changes']=core_changes
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
