"""Closed owned47→49 Tasks adoption; no general legacy-install exception."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from .contracts import validate
from .operator_os import OperatorError
from .plans import data_digest
from .tasks_adoption_native import TASK_COLUMNS,MAINTENANCE_TABLES

RECIPE='owned-native-tasks-adoption-47-49-v1'
SOURCE_IMAGE='sha256:a572f7383c73b5331cc013841db24f371f6d6286e1f353f2c994a554f9162e2a'
SOURCE_INVENTORY='sha256:c69c1015d61b93e6ac79114915a3da82d12f6ca1813032b570c24115684135ad'
APP='dev.aurora.tasks'
ADDON='mp_aurora_tasks'
VERSION='0.2.2'
ARTIFACT='sha256:71c97db1113cba7ba664171962208e429ecff66feb2ef8433e966a1ef20aa52c'
RECIPE_PATH='packages/platform_sdk/modular_platform/tasks_adoption.py'
CHILD_PATH='packages/platform_sdk/modular_platform/tasks_adoption_native.py'


def source_diff(before,after):
    old,new=before['inventory']['files'],after['inventory']['files']
    return [dict(path=n,previous_sha256=old.get(n),target_sha256=new.get(n))
            for n in sorted(old.keys()|new.keys()) if old.get(n)!=new.get(n)]


def _version(value):return value if value.startswith('19.0.') else '19.0.'+value


def check_effects(effects,site_ids):
    if len(effects)!=1 or sorted(site_ids)!=[effects[0]['site_id']]:
        raise OperatorError('Tasks adoption requires one independently configured site')
    effect=effects[0];modules=effect['native_modules']
    if [r['addon'] for r in modules]!=sorted({r['addon'] for r in modules}):
        raise OperatorError('Native module witnesses must be unique and ordered')
    versions={r['addon']:r['version'] for r in modules}
    if (versions.get('mp_core')!='19.0.0.1.47' or effect['tasks_installed']!=(ADDON in versions)
            or ADDON in versions and versions[ADDON]!='19.0.0.1.0'):
        raise OperatorError('Tasks source must be native0.1.0 on sealed47 or absent')
    expected=sorted([*(TASK_COLUMNS if effect['tasks_installed'] else []),
                     *(MAINTENANCE_TABLES if 'maintenance' in versions else [])])
    if [r['table'] for r in effect['retained_tables']]!=expected:
        raise OperatorError('Exact application data witness coverage required')
    gaps=effect['stage_additions']
    pairs=[(r['list_id'],r['done']) for r in gaps]
    if pairs!=sorted(set(pairs)) or gaps and not effect['tasks_installed']:
        raise OperatorError('Stage additions must be unique ordered missing native choices')


def validate_transition(before,after,descriptor,declaration,*,site_ids,effects=None):
    validate('foundation-transition',declaration)
    if declaration['recipe']!=RECIPE:raise OperatorError('Closed Tasks recipe required')
    source,target=declaration['source'],declaration['target']
    if (descriptor['base_image_id']!=SOURCE_IMAGE or source['image_id']!=SOURCE_IMAGE
            or before['inventory_digest']!=SOURCE_INVENTORY or source['inventory_digest']!=SOURCE_INVENTORY
            or descriptor['target_image_id']!=target['image_id'] or target['image_id']==SOURCE_IMAGE
            or target['inventory_digest']!=after['inventory_digest']
            or before['platform_version']!='0.1.47' or after['platform_version']!='0.1.49'):
        raise OperatorError('Tasks transition image/inventory/version pair differs')
    for key in ('python','architecture','markers','python_metadata','python_lock_digest'):
        if before[key]!=after[key]:raise OperatorError('Tasks adoption cannot change the dependency environment')
    old,new=before['inventory'],after['inventory']
    expected_policy=copy.deepcopy(old['policy'])
    if expected_policy.get('application_packages'):raise OperatorError('Source47 already has an application package recipe')
    expected_policy['application_packages']=['plugins/aurora_tasks/application.toml']
    if (new['policy']!=expected_policy or source['policy_digest']!=data_digest(old['policy'])
            or target['policy_digest']!=data_digest(new['policy'])):
        raise OperatorError('Tasks adoption includes an unreviewed policy change')
    previous=old.get('artifacts',{});chosen=new.get('artifacts',{})
    expected_app=dict(addon=ADDON,digest=ARTIFACT,file=APP+'-'+VERSION+'.mplug',plugin_id=APP,version=VERSION)
    if APP in previous or chosen!={**previous,APP:expected_app}:
        raise OperatorError('Only the exact first Tasks archive may be added')
    if set(old['native_addons'])!=set(new['native_addons']):
        raise OperatorError('Tasks adoption cannot add/remove available native addons')
    original,replacement=before['native_manifests'],after['native_manifests']
    if set(original)!=set(old['native_addons']) or set(replacement)!=set(original):
        raise OperatorError('Complete independently read native manifests required')
    for name,manifest in original.items():
        target_manifest=replacement[name]
        if name=='mp_core':
            if (_version(manifest['version']),_version(target_manifest['version']))!=('19.0.0.1.47','19.0.0.1.49'):
                raise OperatorError('Exact native core version pair required')
            if {k:v for k,v in manifest.items() if k!='version'}!={k:v for k,v in target_manifest.items() if k!='version'}:
                raise OperatorError('Tasks support cannot change unrelated core manifest metadata')
        elif name==ADDON:
            if (_version(manifest['version']),_version(target_manifest['version']))!=('19.0.0.1.0','19.0.0.2.2'):
                raise OperatorError('Exact native Tasks source/target version required')
            if target_manifest.get('auto_install') or target_manifest.get('depends')!=['web','mp_core']:
                raise OperatorError('Tasks requires explicit installation and reviewed native dependencies')
        elif manifest!=target_manifest:raise OperatorError('Unrelated native manifest changed: '+name)
    for path,key in [(RECIPE_PATH,'recipe_sha256'),(CHILD_PATH,'child_sha256')]:
        local=Path(__file__).with_name(Path(path).name)
        if new['files'].get(path)!=target[key] or hashlib.sha256(local.read_bytes()).hexdigest()!=target[key]:
            raise OperatorError('Tasks executable recipe/child differs from approved target')
    changes=source_diff(before,after)
    allowed=('packages/platform_sdk/','packages/contracts/','addons/mp_core/','addons/mp_aurora_tasks/')
    artifact_path='artifacts/'+expected_app['file']
    if new['files'].get(artifact_path)!=ARTIFACT[7:]:
        raise OperatorError('Actual Tasks archive inventory pin differs')
    if (not changes or changes!=declaration['source_changes']
            or any(not r['path'].startswith(allowed) and r['path']!=artifact_path for r in changes)):
        raise OperatorError('Tasks adoption has unlisted or unrelated executable changes')
    check_effects(declaration['site_effects'],site_ids)
    for row in declaration['site_effects'][0]['native_modules']:
        if row['addon'] not in original or _version(original[row['addon']].get('version','1.0'))!=row['version']:
            raise OperatorError('Installed source native module differs from sealed47')
    if effects is not None and effects!=declaration['site_effects']:
        raise OperatorError('Application data/modules changed after independent review')
    return changes


def _read_child(configuration,image,phase,effect=None,payloads=None):
    from .deployment import _run
    if len(configuration['sites'])!=1:raise OperatorError('One independent Tasks site required')
    site=configuration['sites'][0]
    data=dict(phase=phase,database=site['database'],site_id=site['site_id'],
              deployment_id=configuration['deployment_id'],effect=effect)
    if payloads is not None:data['payloads']=payloads
    args=['docker','run','--rm','-i','--name',configuration['project']+'-tasks-observe-'+uuid4().hex,
          '--label','com.modular.disposable='+configuration['project'],'--log-driver','none',
          '--network',configuration['project']+'_runtime','--read-only','--user','10001:10001',
          '--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp','--memory','256m','--pids-limit','32',
          '--mount','type=volume,source='+configuration['project']+'_appconfig,target=/run/secrets,readonly',
          '--entrypoint','/venv/bin/python',image,'-c',Path(__file__).with_name('tasks_adoption_native.py').read_text(encoding='utf8')]
    return json.loads(_run(args,input=json.dumps(data).encode('utf8')))


def observe_effects(configuration):
    return [_read_child(configuration,configuration['image_id'],'observe')['effect']]


def declare_transition(configuration,target_image,before,after):
    if (configuration['image_id']!=SOURCE_IMAGE or before['inventory_digest']!=SOURCE_INVENTORY
            or before['platform_version']!='0.1.47' or after['platform_version']!='0.1.49'):
        raise OperatorError('Select the exact owned47-to49 pair before observing application data')
    declaration=dict(schema_version=1,recipe=RECIPE,
        source=dict(image_id=configuration['image_id'],inventory_digest=before['inventory_digest'],
                    policy_digest=data_digest(before['inventory']['policy']),core_version='0.1.47'),
        target=dict(image_id=target_image,inventory_digest=after['inventory_digest'],
                    policy_digest=data_digest(after['inventory']['policy']),core_version='0.1.49',
                    recipe_sha256=after['inventory']['files'].get(RECIPE_PATH),
                    child_sha256=after['inventory']['files'].get(CHILD_PATH),application_version=VERSION,application_digest=ARTIFACT),
        source_changes=source_diff(before,after),site_effects=observe_effects(configuration))
    validate_transition(before,after,dict(base_image_id=configuration['image_id'],target_image_id=target_image),
                        declaration,site_ids=[s['site_id'] for s in configuration['sites']])
    return declaration


def native_changes(sites,declaration):
    check_effects(declaration['site_effects'],[s['site_id'] for s in sites])
    if sorted(sites[0]['native_modules'],key=lambda r:r['addon'])!=declaration['site_effects'][0]['native_modules']:
        raise OperatorError('Installed native modules changed after Tasks adoption review')
    result=[dict(addon='mp_core',previous_version='19.0.0.1.47',target_version='19.0.0.1.49',migrations=[])]
    if declaration['site_effects'][0]['tasks_installed']:
        result.append(dict(addon=ADDON,previous_version='19.0.0.1.0',target_version='19.0.0.2.2',
            migrations=[dict(path='migrations/19.0.0.2.2/post-stages.py',phase='post',digest='sha256:95695e73176594aeee8a1bd3fb43b9eb428cd78d56d6f1606565db63ade8dcc2')]))
    return result


def adoption_target(declaration):
    from .lifecycle_planning import installation_id
    effect=declaration['site_effects'][0]
    if not effect['tasks_installed']:return None
    return dict(installation_id=installation_id(dict(site_id=effect['site_id'],installations=[]),APP),site_id=effect['site_id'],workspace_id=None,
                plugin_id=APP,action='install')


def plan_exception(state,target_release,solution,targets,declaration,operation_type):
    """Trusted staged-planner input, never an application request flag.

    The independent staged reader separately proves image/source/native/data
    facts. This narrower check binds that declaration to the exact solved plan.
    """
    from .native_scope import require_site_manifest
    validate('foundation-transition',declaration)
    if declaration['recipe']!=RECIPE or operation_type!='core_upgrade':
        raise OperatorError('Native adoption requires its explicit staged core recipe')
    check_effects(declaration['site_effects'],state['site_ids'])
    previous=state['release_lock']
    if (previous['platform_version']!='0.1.47' or previous['core_inventory_digest']!=SOURCE_INVENTORY
            or target_release['platform_version']!='0.1.49'
            or target_release['core_inventory_digest']!=declaration['target']['inventory_digest']):
        raise OperatorError('Adoption plan release provenance differs from its declaration')
    old={p['plugin_id']:p for p in previous['plugins']}
    new={p['plugin_id']:p for p in target_release['plugins']}
    if APP in old or set(new)!=set(old)|{APP} or any(new[n]!=p for n,p in old.items()):
        raise OperatorError('Adoption plan may only add the first Tasks archive')
    chosen=new[APP]
    if (chosen['version'],chosen['digest'],chosen['runtime'],chosen['native_addon'])!=(VERSION,ARTIFACT,'native',ADDON):
        raise OperatorError('Adoption plan selected a different native package')
    descriptor=next(p for p in solution['plugins'] if p['manifest']['plugin']['id']==APP)
    require_site_manifest(descriptor['manifest'])
    if any(p['plugin_id']==APP for p in state['installations']):
        raise OperatorError('Legacy native adoption cannot reuse existing package metadata')
    nominated=adoption_target(declaration)
    if [t for t in targets if t['plugin_id']==APP]!=([nominated] if nominated else []):
        raise OperatorError('Adoption must nominate exactly its canonical site-native installation, or stay absent')
    return dict(available_plugin=APP,target=nominated)


def maintenance_flags(bundle):
    lock=bundle['operation_lock'];declaration=lock['foundation_transition']
    validate('foundation-transition',declaration)
    check_effects(declaration['site_effects'],bundle['plan']['site_ids'])
    effect=declaration['site_effects'][0]
    changes=native_changes([dict(site_id=effect['site_id'],native_modules=effect['native_modules'])],declaration)
    nominated=adoption_target(declaration)
    installs=[t for t in lock['targets'] if t['action']=='install']
    app_artifacts=[r for r in bundle['plan'].get('artifacts',[]) if r['plugin_id']==APP]
    expected_artifacts=[dict(plugin_id=APP,version=VERSION,digest=ARTIFACT,runtime='native',
                             action='install',native_addon=ADDON,migration_digests=[])] if nominated else []
    if (bundle['plan']['operation_type']!='core_upgrade' or lock['native_core_changes']!=changes
            or installs!=([nominated] if nominated else []) or app_artifacts!=expected_artifacts
            or any(t['action'] not in {'deploy','install'} for t in lock['targets'])
            or not bundle['plan']['backup']['required'] or not bundle['plan']['destructive']):
        raise OperatorError('Exact Tasks adoption/core/site/checkpoint authority required')
    return ['-u',','.join(r['addon'] for r in changes)]


def retire(executor,bundle,directory):
    from .operator_store import _write_new
    declaration=bundle['operation_lock']['foundation_transition']
    effect=declaration['site_effects'][0]
    value=_read_child(executor.config,executor.config['image_id'],'capture',effect)
    _write_new(directory/'tasks-adoption-baseline.json',value)


def archive_and_verify(executor,bundle,directory,image):
    from .contracts import load_json
    baseline=load_json((directory/'tasks-adoption-baseline.json').read_bytes())
    effect=bundle['operation_lock']['foundation_transition']['site_effects'][0]
    if baseline['effect']!=effect:raise OperatorError('Captured Tasks baseline differs from approved effect')
    result=_read_child(executor.config,image,'verify',effect,baseline['payloads'])
    return dict(recipe=RECIPE,operation_id=bundle['plan']['operation_id'],**result)
