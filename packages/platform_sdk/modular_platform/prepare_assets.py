"""Fixed operator maintenance child: compile public host assets before ready.

Only the installed release's fixed host bundle is compiled. Plans supply target
identities, never paths, source text, SQL, bundle names or commands. This is not
an HTTP endpoint or a default-worker startup migration.
"""
import configparser
import hashlib
import json
from pathlib import Path
import re
import sys


def validate_configuration(path, data):
    config = configparser.ConfigParser()
    config.read(path)
    if not config.has_section('options') or config['options'].get('db_name') != data['database']:
        raise ValueError('Asset preparation database differs from fixed configuration')


def prepare(env):
    rows = {}
    # Current bootstrap publishes the regular minified host bundle. Debug and
    # native locale/RTL variants retain their native generation path; they are
    # not falsely declared precompiled by this regular-release preflight.
    bundle = env['ir.qweb']._get_asset_bundle('mp_shell.assets_host', css=True, js=True, rtl=False)
    for asset in bundle.files:
        if asset.get('filename') and not Path(asset['filename']).is_file():
            raise ValueError('Public host asset source missing')
    # Native generate_xml_bundle turns XML errors into browser error code;
    # validate directly so malformed templates fail before traffic opens.
    bundle.xml()
    for kind in ('js', 'css'):
        attachments = getattr(bundle, kind)()
        if bundle.css_errors:
            raise ValueError('Public host asset compilation failed')
        if not attachments:
            raise ValueError('Public host asset output missing')
        for asset in attachments:
            if (not asset.public or asset.res_model != 'ir.ui.view' or asset.res_id != 0
                    or asset.create_uid.id != 1 or not re.fullmatch(
                        r'/web/assets/(?:[0-9a-f]{7}|[0-9a-f]{64})/mp_shell\.assets_host(?:\.rtl)?\.min\.(?:js|css)', asset.url)
                    or asset.mimetype not in ('application/javascript', 'text/javascript', 'text/css')):
                raise ValueError('Unexpected public host asset metadata')
            raw = asset.raw
            if not isinstance(raw, bytes) or not raw or hashlib.sha1(raw).hexdigest() != asset.checksum:
                raise ValueError('Public host asset bytes/checksum mismatch')
            rows[asset.url] = {'url': asset.url, 'mimetype': asset.mimetype,
                               'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    return sorted(rows.values(), key=lambda item: item['url'])


def main():
    data = json.load(sys.stdin)
    if set(data) != {'database', 'site_id', 'deployment_id', 'generation', 'release_digest', 'inventory_digest'}:
        raise ValueError('Exact approved asset preparation target required')
    inventory = Path('/opt/modular/distribution-inventory.json').read_bytes()
    if 'sha256:' + hashlib.sha256(inventory).hexdigest() != data['inventory_digest']:
        raise ValueError('Asset preparation image inventory mismatch')
    validate_configuration('/run/secrets/odoo_config', data)
    import odoo
    from odoo import api, SUPERUSER_ID
    from odoo.modules.registry import Registry

    odoo.tools.config.parse_config(['-c', '/run/secrets/odoo_config',
                                    '--no-http', '--workers=0', '--max-cron-threads=0'])
    if odoo.tools.config['db_name'] != [data['database']]:
        raise ValueError('Asset preparation database mismatch')
    registry = Registry(data['database'])
    with registry.cursor() as cursor:
        expected = {'mp.site_id': data['site_id'], 'mp.deployment_id': data['deployment_id'],
            'mp.release_generation': str(data['generation']), 'mp.release_digest': data['release_digest'],
            'mp.active_inventory_digest': data['inventory_digest']}
        cursor.execute('SELECT key,value FROM ir_config_parameter WHERE key=ANY(%s)', [list(expected)])
        if dict(cursor.fetchall()) != expected:
            raise ValueError('Asset preparation target/publication changed')
        env = api.Environment(cursor, SUPERUSER_ID, {'lang': 'en_US'})
        rows = prepare(env)
        cursor.commit()
    print(json.dumps({'result': 'prepared', 'generation': data['generation'],
                      'inventory_digest': data['inventory_digest'], 'assets': rows}))


if __name__ == '__main__':
    main()
