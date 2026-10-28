"""Fixed application bootstrap: validate release/DB before native imports.

Maintenance deliberately uses a separate controlled entrypoint. No startup
path accepts init/update or discovers addons outside the approved inventory.
"""
import ast
import configparser
import hashlib
import json
import os
from pathlib import Path
import sys


def validate_data_addons(data_dir):
    data_addons=Path(data_dir)/'addons'
    if data_addons.is_symlink() or any(path.is_symlink() or not path.is_dir() for path in data_addons.rglob('*')):
        raise ValueError('Unexpected writable data-dir addon search-path content')


def validate(root,options,connection,expected_database,expected_inventory):
    root=Path(root)
    raw=(root/'distribution-inventory.json').read_bytes();inventory=json.loads(raw)
    digest='sha256:'+hashlib.sha256(raw).hexdigest()
    if digest!=expected_inventory:raise ValueError('Application release inventory pin mismatch')
    if (options['db_name']!=expected_database or options.get('addons_path')!='/opt/modular/addons'
            or options.get('server_wide_modules')!='base,web' or options.getboolean('list_db')
            or options.getint('max_cron_threads')!=0 or options.get('data_dir')!='/var/lib/modular'
            or any(options.get(key,'').strip() for key in ('init','update','reinit','upgrade_path',
                'pre_upgrade_scripts','load_language','test_file','test_tags'))):
        raise ValueError('Application bootstrap configuration violates the curated profile')
    files=inventory['files']
    if any(not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=value for name,value in files.items()):
        raise ValueError('Application source differs from release inventory')
    # Python can import sourceless bytecode and follow symlinked packages. The
    # read-only image never needs runtime caches in these executable roots.
    directories=('addons','odoo','packages')
    expected={name for name in files if name.startswith(tuple(name+'/' for name in directories))}
    paths=[path for directory in directories for path in [root/directory,*(root/directory).rglob('*')]]
    if any(path.is_symlink() for path in paths):raise ValueError('Unexpected application source symlink')
    actual={path.relative_to(root).as_posix() for path in paths if path.is_file()}
    if actual!=expected:raise ValueError('Unexpected application addon search-path content')
    # Upstream initialize_sys_path also searches data_dir/addons/19.0. Empty
    # directories created by Odoo are harmless; all other content is denied.
    validate_data_addons(options['data_dir'])
    versions={}
    for name in inventory['native_addons']:
        path=root/('odoo/addons' if name=='base' else 'addons')/name/'__manifest__.py'
        manifest=ast.literal_eval(path.read_text());version=manifest.get('version','1.0')
        versions[name]=version if version.startswith('19.0.') else '19.0.'+version
    with connection.cursor() as cursor:
        cursor.execute("SELECT value FROM ir_config_parameter WHERE key='mp.active_inventory_digest'")
        if cursor.fetchone()!=(digest,):raise ValueError('Database release inventory differs; controlled maintenance required')
        cursor.execute("SELECT name,state,latest_version FROM ir_module_module WHERE state IN ('installed','to install','to upgrade','to remove')")
        if any(state!='installed' or name not in versions or versions[name]!=version for name,state,version in cursor.fetchall()):
            raise ValueError('Native module state/version differs; startup never performs migration')
    return digest


def main():
    import psycopg2
    database,inventory=sys.argv[1:]
    config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');options=config['options']
    connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],
        password=options['db_password'],dbname=options['db_name'],connect_timeout=10)
    connection.set_session(readonly=True,autocommit=True)
    try:validate('/opt/modular',options,connection,database,inventory)
    finally:connection.close()
    os.execv('/venv/bin/python',['/venv/bin/python','odoo-bin','-c','/run/secrets/odoo_config'])


if __name__=='__main__':main()
