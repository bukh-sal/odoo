"""Untrusted app request input and redacted journal mirror output.

Only the independent OS CLI invokes this adapter. No approval/store credentials
or raw native diagnostic text crosses into the application container.
"""
import json
from uuid import UUID
from datetime import datetime, timezone

from .contracts import load_json, validate_operations_view
from .deployment import _run
from .operator_os import OperatorError


REQUEST_SQL = """BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5s';
SELECT jsonb_build_object('operation_id',o.public_id,'site_id',o.site_public_id,'plan_hash',o.plan_hash,
 'requested_by',p.public_id,'request_id',o.request_id,'bundle',o.bundle)
FROM mp_operation_request o JOIN mp_principal p ON p.id=o.requested_by
 JOIN res_users u ON u.id=p.user_id JOIN mp_application_operator a ON a.principal_id=p.id
WHERE o.public_id=:'operation_id' AND o.site_public_id=:'site_id' AND o.requested AND o.request_id IS NOT NULL
 AND p.kind='human' AND p.state='active' AND u.active AND a.state='active'
 AND octet_length(o.bundle::text)<=2097152;
ROLLBACK;
"""

MIRROR_WRITER = """import configparser,json,sys
import psycopg2
from psycopg2.extras import Json
value=json.load(sys.stdin)
config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');options=config['options']
connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],password=options['db_password'],dbname=options['db_name'],connect_timeout=10)
with connection:
 with connection.cursor() as cursor:
  cursor.execute('''UPDATE mp_operation_request o SET journal_mirror=%s,write_date=timezone('UTC',now())
    FROM mp_principal p WHERE o.requested_by=p.id AND o.public_id=%s AND o.site_public_id=%s
    AND o.plan_hash=%s AND p.public_id=%s AND o.requested''',
    [Json(value['view']),value['view']['operation_id'],value['site_id'],value['view']['plan_hash'],value['view']['requested_by']])
  assert cursor.rowcount==1,'Mirror target changed; no journal authority is conferred'
connection.close()
print('{"status_mirrored":true}')
"""


def read_request(observer, operation):
    if str(UUID(operation)) != operation or len(observer.config['sites']) != 1:
        raise OperatorError('Exact operation and single-site target required')
    site = observer.config['sites'][0]
    raw = _run(['docker','exec','-i',observer._container('db'),'psql','-X','-qAt','-U','postgres','-d',site['database'],
        '-v','ON_ERROR_STOP=1','-v','operation_id='+operation,'-v','site_id='+site['site_id']],input=REQUEST_SQL.encode())
    if not raw.strip():
        raise OperatorError('No eligible active-human app request at this independent target')
    value = load_json(raw)
    if (value['operation_id'] != operation or value['plan_hash'] != value['bundle']['plan_hash']
            or value['site_id'] not in value['bundle']['plan']['site_ids']
            or value['bundle']['plan']['deployment_id'] != observer.config['deployment_id']):
        raise OperatorError('Untrusted application request identity/hash/target mismatch')
    return value


def journal_view(bundle, status, request, state):
    dimensions = []
    for target in bundle['operation_lock']['targets']:
        actual = next((item for item in state['installations'] if item['installation_id']==target['installation_id']
                       and item['workspace_id']==target['workspace_id']),None)
        database = actual['state'] if actual else 'not_installed'
        if status['state']=='recovery_required': database='recovery_required'
        dimensions.append({'plugin_id':target['plugin_id'],'installation_id':target['installation_id'],'workspace_id':target['workspace_id'],
            'artifact_state':'verified','release_state':'failed' if status['state']=='recovery_required' else
                ('active' if state['release_digest']==bundle['plan']['target_release_digest'] else 'planned'),
            'database_state':database,'feature_state':actual['feature_state'] if actual else None,'service_state':None})
    failure = next((item['details'].get('code') for item in reversed(status['history']) if item['details'].get('code')),None)
    value={'schema_version':1,'kind':'status','operation_id':status['operation_id'],'plan_hash':status['plan_hash'],
        'requested_by':request['requested_by'],'state':status['state'],'phase':status['phase'],'source':'operator_journal_mirror',
        'observed_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'stale':False,
        'approval_expires_at':status['approval_expires_at'],'dimensions':dimensions,
        'history':[{key:item[key] for key in ('sequence','utc','code')} for item in status['history'][-200:]],
        'error_code':failure,'control_authority':'independent_local_os'}
    return validate_operations_view(value)


def publish_status(store, observer, catalog, operation):
    bundle=store.bundle(operation)
    store._authorize_plan(bundle['plan'],generation=False)
    request=read_request(observer,operation)
    if request['bundle']!=bundle:
        raise OperatorError('Application request differs from the immutable independent registration')
    observation=observer.read();state=observer.state(observation,catalog.snapshot())['state']
    view=journal_view(bundle,store.status(operation),request,state)
    _run(['docker','exec','-i',observer._container('app'),'/venv/bin/python','-c',MIRROR_WRITER],
        input=json.dumps({'site_id':request['site_id'],'view':view}).encode())
    return view
