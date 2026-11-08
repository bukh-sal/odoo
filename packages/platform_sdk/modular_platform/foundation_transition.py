"""Dispatch explicit closed owned transitions; never accept package-supplied SQL."""
from pathlib import Path
import hashlib
import json

from .contracts import validate
from .operator_os import OperatorError
from .plans import data_digest

RECIPE = 'owned-addon-extraction-46-47-v1'
SOURCE_IMAGE = 'sha256:72d51d3282c93df591e01cf63c2d0fe66c06633f5d4b569d557da5f3c47d0e82'
SOURCE_INVENTORY = 'sha256:14cc5a2c5ef57ad27c8548e3f4150e402ba13dfb8920618b5e3137f060e54fe1'
RECIPE_PATH = 'packages/platform_sdk/modular_platform/foundation_transition.py'
IAP_TABLES = ('iap_account', 'iap_account_res_company_rel', 'iap_account_res_users_rel', 'iap_service')
RETAINED_TABLES = ('discuss_channel', 'fetchmail_server', 'mail_message', 'maintenance_request',
                   'mp_aurora_task', 'mp_aurora_task_list', 'mp_aurora_task_list_res_users_rel', 'mp_aurora_task_stage')
NATIVE_VERSIONS = {
    'base': ('19.0.1.3', '19.0.1.4'), 'web': ('19.0.1.0', '19.0.1.1'),
    'base_setup': ('19.0.1.0', '19.0.1.1'), 'html_editor': ('19.0.1.0', '19.0.1.1'),
    'mail': ('19.0.1.19', '19.0.1.20'), 'web_tour': ('19.0.1.0', '19.0.1.1'),
    'mp_core': ('19.0.0.1.46', '19.0.0.1.47'),
}
NEW_MODULES = {'mp_discuss': '19.0.1.0', 'mp_mail_gateway': '19.0.1.1'}


def _tasks_recipe(declaration):
    return isinstance(declaration,dict) and declaration.get('recipe')=='owned-native-tasks-adoption-47-49-v1'


def observe_transition_effects(configuration,declaration):
    if _tasks_recipe(declaration):
        from .tasks_adoption import observe_effects as observe_tasks
        return observe_tasks(configuration)
    return observe_effects(configuration)


def _native_version(raw):
    # Owned manifests retain short inherited versions; the database records
    # their engine-series prefix. Compare the same independently observed value.
    return raw if raw.startswith('19.0.') else '19.0.'+raw


OWNERS = {'mp_discuss': ['action_discuss',
                'discuss_call_history_menu',
                'discuss_channel_integrations_menu',
                'discuss_channel_tour',
                'discuss_public_channel_template',
                'discuss_technical',
                'main_menu_discuss',
                'menu_call_settings',
                'menu_canned_responses',
                'menu_channel',
                'menu_configuration',
                'menu_notification_settings',
                'menu_roles',
                'menu_root_discuss'],
 'mp_mail_gateway': ['access_fetchmail_server',
                     'act_server_history',
                     'action_email_server_tree',
                     'field_fetchmail_server__active',
                     'field_fetchmail_server__attach',
                     'field_fetchmail_server__configuration',
                     'field_fetchmail_server__create_date',
                     'field_fetchmail_server__create_uid',
                     'field_fetchmail_server__date',
                     'field_fetchmail_server__display_name',
                     'field_fetchmail_server__error_date',
                     'field_fetchmail_server__error_message',
                     'field_fetchmail_server__id',
                     'field_fetchmail_server__is_ssl',
                     'field_fetchmail_server__message_ids',
                     'field_fetchmail_server__name',
                     'field_fetchmail_server__object_id',
                     'field_fetchmail_server__original',
                     'field_fetchmail_server__password',
                     'field_fetchmail_server__port',
                     'field_fetchmail_server__priority',
                     'field_fetchmail_server__script',
                     'field_fetchmail_server__server',
                     'field_fetchmail_server__server_type',
                     'field_fetchmail_server__server_type_info',
                     'field_fetchmail_server__state',
                     'field_fetchmail_server__user',
                     'field_fetchmail_server__write_date',
                     'field_fetchmail_server__write_uid',
                     'field_mail_mail__fetchmail_server_id',
                     'ir_cron_mail_gateway_action',
                     'menu_action_fetchmail_server_tree',
                     'model_fetchmail_server',
                     'view_email_server_form',
                     'view_email_server_search',
                     'view_email_server_tree']}


def source_diff(before, after):
    old, new = before['inventory']['files'], after['inventory']['files']
    return [{'path': name, 'previous_sha256': old.get(name), 'target_sha256': new.get(name)}
            for name in sorted(old.keys() | new.keys()) if old.get(name) != new.get(name)]


def _check_effects(effects, site_ids):
    if [row['site_id'] for row in effects] != sorted(site_ids):
        raise OperatorError('Foundation transition must bind every actual configured site')
    expected = {name: owner for owner, names in OWNERS.items() for name in names}
    for site in effects:
        tables = site['iap_tables']
        if [row['table'] for row in tables] != list(IAP_TABLES):
            raise OperatorError('Foundation retirement requires exact IAP table identities')
        rows = site['mail_ownership']
        actual = {row['name']: row['owner'] for row in rows}
        wanted = expected if site['mail_installed'] else {}
        if len(rows) != len(actual) or actual != wanted:
            raise OperatorError('Foundation transition requires the complete reviewed mail ownership map')
        if site['legacy_local_pipe_count'] != 0:
            raise OperatorError('Retire or reconfigure unsupported local mail-pipe data before this recipe')
        modules = site['native_modules']
        if len({m['addon'] for m in modules}) != len(modules) or modules != sorted(modules, key=lambda m: m['addon']):
            raise OperatorError('Foundation installed module evidence must be unique and ordered')
        if 'iap' not in {m['addon'] for m in modules}:
            raise OperatorError('This recipe requires the installed owned46 IAP substrate')
        if site['mail_installed'] != any(m['addon']=='mail' for m in modules):
            raise OperatorError('Mail effects must match actual installed module scope')
        tables=[r['table'] for r in site['retained_tables']]
        if tables != sorted(set(tables)):
            raise OperatorError('Retained data witnesses must be unique and ordered')


def validate_transition(before, after, descriptor, declaration, *, site_ids, effects=None):
    """Validate independently observed images plus OS-selected declaration."""
    validate('foundation-transition', declaration)
    if _tasks_recipe(declaration):
        from .tasks_adoption import validate_transition as validate_tasks
        return validate_tasks(before,after,descriptor,declaration,site_ids=site_ids,effects=effects)
    source, target = declaration['source'], declaration['target']
    if (descriptor['base_image_id'] != SOURCE_IMAGE or source['image_id'] != SOURCE_IMAGE
            or before['inventory_digest'] != SOURCE_INVENTORY
            or source['inventory_digest'] != SOURCE_INVENTORY
            or target['image_id'] != descriptor['target_image_id']
            or source['image_id'] == target['image_id']
            or target['inventory_digest'] != after['inventory_digest']
            or source['policy_digest'] != data_digest(before['inventory']['policy'])
            or target['policy_digest'] != data_digest(after['inventory']['policy'])):
        raise OperatorError('Foundation transition source/target/policy identities differ')
    for key in ('python', 'architecture', 'markers', 'python_metadata', 'python_lock_digest'):
        if before[key] != after[key]:
            raise OperatorError('Foundation extraction cannot change the dependency environment')
    old, new = before['inventory'], after['inventory']
    if old.get('artifacts') != new.get('artifacts'):
        raise OperatorError('Foundation extraction must preserve actual plugin archives')
    prior_names, next_names = set(old['native_addons']), set(new['native_addons'])
    if prior_names - next_names != {'iap'} or next_names - prior_names != set(NEW_MODULES):
        raise OperatorError('Foundation recipe permits only IAP retirement and the two extracted apps')
    for key in old['policy'].keys() | new['policy'].keys():
        if key not in ('addons', 'profile') and old['policy'].get(key) != new['policy'].get(key):
            raise OperatorError('Foundation recipe includes an unreviewed distribution policy change')
    if set(old['policy']['addons']) != prior_names or set(new['policy']['addons']) != next_names:
        raise OperatorError('Foundation policy/native inventories disagree')
    manifests, replacements = before['native_manifests'], after['native_manifests']
    if set(manifests) != prior_names or set(replacements) != next_names:
        raise OperatorError('Independent native manifests must cover the exact policy')
    for name in prior_names & next_names:
        if name in NATIVE_VERSIONS:
            if (_native_version(manifests[name]['version']), _native_version(replacements[name]['version'])) != NATIVE_VERSIONS[name]:
                raise OperatorError('Foundation native version pair is outside the reviewed recipe: ' + name)
        elif manifests[name] != replacements[name]:
            raise OperatorError('Foundation extraction changes an unrelated native manifest: ' + name)
    for name, version in NEW_MODULES.items():
        if _native_version(replacements[name]['version']) != version or replacements[name].get('auto_install', False):
            raise OperatorError('Extracted apps require exact versions and explicit installation')
    if new['native_addons']['web_tour'].get('auto_install') or replacements['mail'].get('application'):
        raise OperatorError('Onboarding and full app UI cannot be forced by generic communication')
    if after['inventory']['files'].get(RECIPE_PATH) != target['recipe_sha256']:
        raise OperatorError('Foundation executable recipe differs from the approved target image')
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != target['recipe_sha256']:
        raise OperatorError('Operator recipe source differs from independently inventoried target')
    child=Path(__file__).with_name('foundation_native.py')
    if (after['inventory']['files'].get('packages/platform_sdk/modular_platform/foundation_native.py')!=target['child_sha256']
            or hashlib.sha256(child.read_bytes()).hexdigest()!=target['child_sha256']):
        raise OperatorError('Foundation child differs from reviewed target/operator source')
    diff = source_diff(before, after)
    allowed = ('odoo/', 'packages/platform_sdk/', 'packages/contracts/',
               *(f'addons/{name}/' for name in prior_names | next_names))
    if (not diff or declaration['source_changes'] != diff
            or any(not row['path'].startswith(allowed) for row in diff)):
        raise OperatorError('Foundation transition has unlisted or unsupported executable changes')
    _check_effects(declaration['site_effects'], site_ids)
    for site in declaration['site_effects']:
        for module in site['native_modules']:
            if module['addon'] not in manifests or _native_version(manifests[module['addon']].get('version','1.0')) != module['version']:
                raise OperatorError('Installed database module is unavailable or differs from sealed46')
    if effects is not None and effects != declaration['site_effects']:
        raise OperatorError('Foundation retirement data/ownership changed since operator review')
    return diff


def _psql(configuration, query):
    from .deployment import _run
    if len(configuration['sites']) != 1:
        raise OperatorError('This foundation recipe requires one independently configured site')
    return _run(['docker', 'exec', '-i', configuration['project'] + '-db-1', 'psql',
        '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d',
        configuration['sites'][0]['database']], input=query.encode('utf8')).decode('utf8').strip()


def table_payload(configuration, table):
    if table not in (*IAP_TABLES, *RETAINED_TABLES):
        raise OperatorError('Unreviewed retirement table')
    # Fixed reviewed identifiers; JSON text preserves numeric values losslessly.
    return _psql(configuration, 'SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\'::jsonb)::text FROM "' + table + '" t;')


def observe_effects(configuration):
    tables = []
    for name in IAP_TABLES:
        payload = table_payload(configuration, name)
        rows = json.loads(payload)
        tables.append(dict(table=name, rows=len(rows), sha256=hashlib.sha256(payload.encode('utf8')).hexdigest()))
    mail = _psql(configuration, "SELECT count(*) FROM ir_module_module WHERE name='mail' AND state='installed';") == '1'
    modules=json.loads(_psql(configuration,"SELECT json_agg(json_build_object('addon',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module WHERE state='installed';"))
    retained=[]
    for name in RETAINED_TABLES:
        if _psql(configuration,"SELECT to_regclass('public."+name+"') IS NOT NULL;")=='t':
            payload=table_payload(configuration,name)
            retained.append(dict(table=name,rows=len(json.loads(payload)),sha256=hashlib.sha256(payload.encode('utf8')).hexdigest()))
    moves = []
    local = 0
    if mail:
        local = int(_psql(configuration, "SELECT count(*) FROM fetchmail_server WHERE server_type='local';"))
        expected={name:owner for owner,names in OWNERS.items() for name in names}
        names=','.join("'"+n+"'" for n in expected)
        rows=json.loads(_psql(configuration,"SELECT json_agg(json_build_object('name',name,'model',model,'res_id',res_id) ORDER BY name) FROM ir_model_data WHERE module='mail' AND name IN ("+names+");") or '[]')
        for row in rows:moves.append(dict(owner=expected[row['name']],**row))
    if local:
        raise OperatorError('Unsupported local mail-pipe configuration requires an explicit data disposition')
    return [dict(site_id=configuration['sites'][0]['site_id'], mail_installed=mail,
                 legacy_local_pipe_count=local, iap_tables=tables,
                 native_modules=modules,retained_tables=retained,
                 mail_ownership=sorted(moves, key=lambda row: row['name']))]


def native_changes(sites,declaration):
    if _tasks_recipe(declaration):
        from .tasks_adoption import native_changes as tasks_changes
        return tasks_changes(sites,declaration)
    if len(sites)!=1 or len(declaration['site_effects'])!=1:
        raise OperatorError('Foundation recipe requires one site')
    effect=declaration['site_effects'][0]
    actual=sorted(sites[0]['native_modules'],key=lambda m:m['addon'])
    if actual!=effect['native_modules']:
        raise OperatorError('Installed native modules changed since foundation review')
    return [dict(addon=m['addon'],previous_version=m['version'],target_version=NATIVE_VERSIONS[m['addon']][1],migrations=[])
            for m in actual if m['addon'] in NATIVE_VERSIONS]


def maintenance_flags(bundle):
    lock=bundle['operation_lock'];declaration=lock['foundation_transition']
    if _tasks_recipe(declaration):
        from .tasks_adoption import maintenance_flags as tasks_flags
        return tasks_flags(bundle)
    validate('foundation-transition',declaration)
    _check_effects(declaration['site_effects'],bundle['plan']['site_ids'])
    effect=declaration['site_effects'][0]
    expected=[dict(addon=m['addon'],previous_version=m['version'],target_version=NATIVE_VERSIONS[m['addon']][1],migrations=[])
              for m in effect['native_modules'] if m['addon'] in NATIVE_VERSIONS]
    if (bundle['plan']['operation_type']!='core_upgrade' or lock['native_core_changes']!=expected
            or not bundle['plan']['backup']['required'] or not bundle['plan']['destructive']
            or any(t['action']!='deploy' for t in lock['targets'])):
        raise OperatorError('Foundation maintenance requires exact native/site scope and checkpoint')
    installs=sorted(NEW_MODULES) if effect['mail_installed'] else []
    return (['-i',','.join(installs)] if installs else [])+['-u',','.join(m['addon'] for m in expected)]


def declare_transition(configuration, target_image, before, after, *, recipe=RECIPE):
    if recipe=='owned-native-tasks-adoption-47-49-v1':
        from .tasks_adoption import declare_transition as declare_tasks
        return declare_tasks(configuration,target_image,before,after)
    if recipe!=RECIPE:raise OperatorError('Unknown owned foundation recipe')
    declaration = dict(schema_version=1, recipe=RECIPE,
        source=dict(image_id=configuration['image_id'], inventory_digest=before['inventory_digest'],
                    policy_digest=data_digest(before['inventory']['policy']), core_version='0.1.46'),
        target=dict(image_id=target_image, inventory_digest=after['inventory_digest'],
                    policy_digest=data_digest(after['inventory']['policy']), core_version='0.1.47',
                    recipe_sha256=after['inventory']['files'].get(RECIPE_PATH),
                    child_sha256=after['inventory']['files'].get('packages/platform_sdk/modular_platform/foundation_native.py')),
        source_changes=source_diff(before, after), site_effects=observe_effects(configuration))
    descriptor=dict(base_image_id=configuration['image_id'], target_image_id=target_image)
    validate_transition(before, after, descriptor, declaration,
                        site_ids=[row['site_id'] for row in configuration['sites']])
    return declaration


def retire(executor,bundle,directory):
    """After checkpoint+mutation journal, export privately then use old API."""
    from .operator_store import _write_new
    declaration=bundle['operation_lock']['foundation_transition']
    if _tasks_recipe(declaration):
        from .tasks_adoption import retire as capture_tasks
        return capture_tasks(executor,bundle,directory)
    effects=observe_effects(executor.config)
    if effects!=declaration['site_effects']:
        raise OperatorError('Drained foundation data differs from the approved retirement')
    payloads={table:table_payload(executor.config,table) for table in IAP_TABLES}
    _write_new(directory/'retirement-payloads.json',payloads)
    _run_child(executor,bundle,directory,'retire',executor.config['image_id'])


def _run_child(executor,bundle,directory,phase,image,payloads=None):
    operation=bundle['plan']['operation_id']
    arguments,_=executor._child(operation,'foundation-'+phase,writable=True,image_id=image)
    arguments.insert(2,'-i')
    data=dict(phase=phase,operation_id=operation,database=executor.config['sites'][0]['database'],
        deployment_id=executor.config['deployment_id'],declaration=bundle['operation_lock']['foundation_transition'])
    if payloads is not None:data['payloads']=payloads
    executor._private_command(arguments+['-c',Path(__file__).with_name('foundation_native.py').read_text(encoding='utf8')],
        directory/('foundation-'+phase+'.log'),input=json.dumps(data).encode('utf8'))


def archive_and_verify(executor,bundle,directory,image):
    if _tasks_recipe(bundle['operation_lock']['foundation_transition']):
        from .tasks_adoption import archive_and_verify as verify_tasks
        return verify_tasks(executor,bundle,directory,image)
    from .contracts import load_json
    payloads=load_json((directory/'retirement-payloads.json').read_bytes())
    _run_child(executor,bundle,directory,'archive',image,payloads)
    effect=bundle['operation_lock']['foundation_transition']['site_effects'][0]
    actual=json.loads(_psql(executor.config,"SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed';"))
    expected={r['addon']:NATIVE_VERSIONS.get(r['addon'],(None,r['version']))[1]
              for r in effect['native_modules'] if r['addon']!='iap'}
    if effect['mail_installed']:expected.update(NEW_MODULES)
    if actual!=expected:raise OperatorError('Transition installed module set/versions differ from review')
    for witness in effect['retained_tables']:
        value=table_payload(executor.config,witness['table'])
        if hashlib.sha256(value.encode('utf8')).hexdigest()!=witness['sha256']:
            raise OperatorError('Retained application data differs after foundation migration')
    for witness in effect['iap_tables']:
        # Public receipts expose only digests/counts. Raw content remains private.
        result=json.loads(_psql(executor.config,"SELECT json_build_object('payload',payload,'rows',row_count,'sha256',sha256) FROM mp_retirement_archive WHERE operation_id='"+bundle['plan']['operation_id']+"' AND table_name='"+witness['table']+"';") or 'null')
        if (not result or result['payload']!=payloads[witness['table']] or result['rows']!=witness['rows'] or result['sha256']!=witness['sha256']):
            raise OperatorError('Lossless retirement archive verification failed')
    return dict(recipe=RECIPE,operation_id=bundle['plan']['operation_id'],iap_tables=effect['iap_tables'],
        retained_tables=effect['retained_tables'],native_modules=actual,adopted_ids=len(effect['mail_ownership']),
        lossless_archive_verified=True)
