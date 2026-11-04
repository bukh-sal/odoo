"""Fixed read-only native impact child for the independent Docker observer.

Uses the operator-pinned image/network/config volume, including while normal
workers are stopped. No database, image, script or path comes from a proposal.
"""
from pathlib import Path
from uuid import uuid4

from .contracts import load_json
from .lifecycle_impact import impact_view, verified_archive_sources
from .projection import runtime_inputs
from .resolution import PlanningError


CHILD = r'''
import configparser,hashlib,json,pathlib,sys
import psycopg2
from modular_platform.lifecycle_impact import inspect_native_impact
data=json.load(sys.stdin)
assert set(data)=={'site_id','database','requested','descriptors','archive_source_hashes','inventory_digest'}
root=pathlib.Path('/opt/modular')
inventory_raw=(root/'distribution-inventory.json').read_bytes()
assert 'sha256:'+hashlib.sha256(inventory_raw).hexdigest()==data['inventory_digest']
inventory=json.loads(inventory_raw)
addons={'mp_identity'}|{d['manifest']['runtime']['addon_name'] for d in data['descriptors'] if d['manifest']['runtime']['kind']=='native'}
sources={}
for name,digest in inventory['files'].items():
 if name.startswith('addons/') and name.endswith('.py') and name.split('/')[1] in addons:
  raw=(root/name).read_bytes()
  assert hashlib.sha256(raw).hexdigest()==digest,'Actual native source drift'
  sources[name[len('addons/'):]]=raw
for name,digest in data['archive_source_hashes'].items():
 assert hashlib.sha256(sources[name]).hexdigest()==digest,'Image source differs from verified archive'
config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');opts=config['options']
assert opts['db_name']==data['database'],'Wrong independently selected database'
connection=psycopg2.connect(host=opts['db_host'],port=opts.getint('db_port'),user=opts['db_user'],
 password=opts['db_password'],dbname=data['database'],connect_timeout=10)
connection.set_session(isolation_level='REPEATABLE READ',readonly=True)
with connection:
 with connection.cursor() as cursor:cursor.execute("SET LOCAL statement_timeout='5s'")
 result=inspect_native_impact(connection,site_id=data['site_id'],requested=data['requested'],
  descriptors=data['descriptors'],sources=sources)
connection.close()
assert 'odoo' not in sys.modules,'No native registry may be imported during planning'
print(json.dumps(result))
'''


def observe_native_impact(observer, observation, catalog, *, site_id, requested):
    import hashlib
    import json
    import subprocess

    target = next((s for s in observer.config['sites'] if s['site_id'] == site_id), None)
    if target is None or observation['image_id'] != observer.config['image_id'] or len(observer.config['sites']) != 1:
        raise PlanningError('Native impact requires the independently configured single-site Docker profile')
    external = [pin for pin in observer.config.get('published_release', {}).get('plugins', [])
                if pin['runtime'] == 'external_service']
    selected, _, _ = runtime_inputs(observation['runtime'], catalog.snapshot(), external_plugins=external)
    sources = {}
    for descriptor in selected:
        if descriptor['manifest']['runtime']['kind'] == 'native':
            sources.update(verified_archive_sources(catalog.path(descriptor['digest']), descriptor))
    payload = dict(site_id=site_id, database=target['database'], requested=requested, descriptors=selected,
                   archive_source_hashes={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
                   inventory_digest=observation['runtime']['inventory_digest'])
    # Bootstrap our own installed observer implementation, never proposal text.
    # This allows read-only inspection before its SDK is activated in an image.
    source = Path(__file__).with_name('lifecycle_impact.py').read_text(encoding='utf8')
    program = ("import sys,types\nmodule=types.ModuleType('modular_platform.lifecycle_impact')\n"
               "module.__package__='modular_platform'\nexec(compile(" + repr(source) +
               ",'independent-lifecycle-impact.py','exec'),module.__dict__)\n"
               "sys.modules[module.__name__]=module\n") + CHILD
    project = observer.config['project']
    name = project + '-impact-' + uuid4().hex[:12]
    command = ['docker', 'run', '--rm', '--name', name,
        '--label', 'mp.disposable=native-impact-inspection', '--network', project + '_runtime', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp',
        '--mount', 'type=volume,source=' + project + '_appconfig,target=/run/secrets,readonly',
        '--interactive', '--entrypoint', '/venv/bin/python', observer.config['image_id'], '-B', '-c', program]
    try:
        result = subprocess.run(command, input=json.dumps(payload).encode(), capture_output=True, timeout=90)
    except subprocess.TimeoutExpired as error:
        # No native mutation is possible; do not retry an uncertain child blindly.
        raise PlanningError('Read-only native impact inspection timed out; reconcile child ' + name) from error
    if result.returncode:
        raise PlanningError('Read-only native impact inspection failed; no proposal can be approved')
    impact = load_json(result.stdout)
    # Validate bounds/known-vs-unknown invariants before using the raw preimage.
    impact_view(impact, operation_id='00000000-0000-0000-0000-000000000000',
                plan_hash='sha256:' + '0' * 64, observed_at='2026-10-29T00:00:00Z')
    if impact['site_id'] != site_id or impact['requested_addons'] != sorted(requested):
        raise PlanningError('Native impact response differs from the independent nomination')
    return impact
