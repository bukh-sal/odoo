"""Once-only AR baseline from immutable core46 consumer inputs (private state)."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.local/addon-cleanup/baseline46'
KIT = ROOT / '.local/releases/foundation-r1-core46'
SETUP = ROOT / '.local/foundation-release/clean-core46/operator-setup.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'initialize', 'install', 'observe', 'seed', 'seed-complete', 'ownership'])
    args = parser.parse_args()
    setup = json.loads(SETUP.read_bytes())
    source = Path(setup['source'])
    assert Path(sys.executable).resolve() == Path(setup['python']).resolve()
    sys.path[:0] = [str(source / 'release'), str(source / 'tools'),
                    str(source / 'packages/platform_sdk')]
    from initialize_reference import Reference, configuration, write
    from modular_platform.catalog import Catalog
    from modular_platform.operator_os import protect_directory
    if args.phase == 'prepare':
        assert not WORK.exists(), 'Inspect existing phase; never reset or replay an uncertain apply'
        protect_directory(WORK)
        private = protect_directory(WORK / 'private')
        write(WORK / 'operator-setup.json', dict(setup, private=str(private)))
        catalog = Catalog(private / 'catalog', configuration(KIT / 'plugins/curated-trust.json'))
        for row in json.loads((KIT / 'plugins/index.json').read_bytes())['packages']:
            catalog.add(KIT / row['file'], expected_digest=row['digest'])
    options = SimpleNamespace(kit=KIT, workdir=WORK, reference_fixture=True,
                              port=18140, subnets=['10.203.157.0/28', '10.203.157.16/28'],
                              native_app='maintenance')
    # Full multi-GB kit verification is done once before resource creation. Later
    # fixture phases bind that verified manifest; runtime/executor checks remain.
    manifest_digest = hashlib.sha256((KIT / 'kit-inventory.json').read_bytes()).hexdigest()
    if args.phase == 'prepare':
        site = Reference(options)
    else:
        receipt = json.loads((WORK / 'kit-verified.json').read_bytes())
        assert receipt['manifest_sha256'] == manifest_digest
        site = Reference.__new__(Reference)
        site.kit, site.work, site.operator = KIT, WORK, json.loads((WORK / 'operator-setup.json').read_bytes())
        site.private, site.args = WORK / 'private', options
        site.local = site.private / 'reference'
    if args.phase not in ('observe', 'seed', 'seed-complete', 'ownership'):
        getattr(site, args.phase)()
        if args.phase == 'prepare':
            write(WORK / 'kit-verified.json', dict(manifest_sha256=manifest_digest,
                image=site.state()['image_id'], full_kit_checksums_verified=True))
        return
    if args.phase == 'ownership':
        code = '''
import json, hashlib
from psycopg2 import sql
env.cr.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'iap_%' ORDER BY tablename")
tables = [r[0] for r in env.cr.fetchall()]
witnesses = {}
for table in tables + ['fetchmail_server', 'discuss_channel', 'mail_message', 'maintenance_request']:
    env.cr.execute(sql.SQL('SELECT to_jsonb(t) FROM {} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(table)))
    rows = [r[0] for r in env.cr.fetchall()]
    witnesses[table] = dict(count=len(rows), sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())
ids = env['ir.model.data'].search([('module','=','mail'), '|', ('model','=','ir.model.fields'), ('model','=','ir.model')])
owned = [dict(name=r.name,model=r.model,res_id=r.res_id) for r in ids
    if r.name == 'model_fetchmail_server' or r.name.startswith('field_fetchmail_server__') or r.name=='field_mail_mail__fetchmail_server_id']
print('MP_AR_OWNERSHIP=' + json.dumps(dict(table_witnesses=witnesses, gateway_metadata=owned)))
'''
        raw = site.native(site.state(), 'ar-ownership-observe', [], code)
        rows = [json.loads(line.split('=', 1)[1]) for line in raw.decode().splitlines()
                if line.startswith('MP_AR_OWNERSHIP=')]
        assert len(rows) == 1
        write(WORK / 'ownership.json', rows[0])
        print(json.dumps(dict(result='observed', tables=len(rows[0]['table_witnesses']),
                              gateway_metadata=len(rows[0]['gateway_metadata']))))
        return
    if args.phase in ('seed', 'seed-complete'):
        code = '''
import json
from unittest.mock import patch
with patch('requests.sessions.Session.request', side_effect=AssertionError('No external requests in AR seed')):
    assert not env['iap.service'].search_count([('technical_name', '=', 'ar_fictional')]), 'Never replay a committed seed'
    service = env['iap.service'].create({'name': 'AR fictional service', 'technical_name': 'ar_fictional',
        'description': 'Synthetic retention witness', 'unit_name': 'unit', 'integer_balance': False})
    account = env['iap.account'].create({'name': 'AR retained account', 'service_id': service.id,
        'account_token': 'fictional-ar-retention-token', 'company_ids': [(6, 0, env.company.ids)]})
    mailbox = env['fetchmail.server'].create({'name': 'AR disabled fictional mailbox',
        'active': False, 'server': 'mail.invalid', 'user': 'ar@example.invalid', 'password': 'fictional-ar-mailbox'})
    channel = env['discuss.channel'].create({'name': 'AR retained conversation', 'channel_type': 'channel'})
    message = channel.message_post(body='AR synthetic retained conversation', message_type='comment')
    request = env['maintenance.request'].create({'name': 'AR retained repair', 'description': '<p>Retained rich text</p>'})
    env.cr.commit()
    print('MP_AR_SEED=' + json.dumps(dict(service=service.id, account=account.id, mailbox=mailbox.id,
        channel=channel.id, message=message.id, request=request.id, external_requests=0)))
'''
        raw = site.native(site.state(), 'ar-retention-' + args.phase, [], code)
        rows = [json.loads(line.split('=', 1)[1]) for line in raw.decode().splitlines()
                if line.startswith('MP_AR_SEED=')]
        assert len(rows) == 1, 'Inspect committed seed before another mutation'
        write(WORK / 'retention-seed.json', rows[0])
        print(json.dumps(rows[0]))
        return
    code = '''
import json
modules = env['ir.module.module'].search([('state', '=', 'installed')])
tables = ['iap_account', 'fetchmail_server', 'discuss_channel', 'mail_message', 'maintenance_request']
counts = {}
for table in tables:
    env.cr.execute('SELECT count(*) FROM ' + table)
    counts[table] = env.cr.fetchone()[0]
print('MP_AR_BASELINE=' + json.dumps(dict(modules={m.name: m.installed_version for m in modules},
    tables=counts, mail_xmlids=env['ir.model.data'].search_count([('module', '=', 'mail')]),
    iap_xmlids=env['ir.model.data'].search_count([('module', '=', 'iap')]))))
'''
    raw = site.native(site.state(), 'ar-source-observation', [], code)
    rows = [json.loads(line.split('=', 1)[1]) for line in raw.decode().splitlines()
            if line.startswith('MP_AR_BASELINE=')]
    assert len(rows) == 1, 'Inspect native result before retry'
    write(WORK / 'observed.json', rows[0])
    print(json.dumps(rows[0]))


if __name__ == '__main__':
    main()

