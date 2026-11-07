"""Real scoped background rows and filestore witnesses for the common upgrade."""
import argparse
import json

from foundation_release import FoundationSite, load, write
from foundation_lifecycle import sql


SEED = '''
import base64,json
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_identity.release import current_release
from odoo.addons.mp_core import job_dispatch
from modular_platform import durable
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),
                         FIXTURE['workspaces']['A']['public_id'])
env.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users']['alice']['principal_id']])
principal=env.cr.fetchone()[0]
now=datetime.now(timezone.utc).replace(microsecond=0)
future=now+timedelta(hours=4)
task=actor['mp.background.task'].create(dict(name='CF scheduled migration witness',points=4,
    assignee_id=principal,due_at=future.replace(tzinfo=None)))
actor['mp.background.task'].create(dict(name='CF report migration witness',points=6))
reminder=task._queue_current()
jobs={}
for label,when in [('pending',future),('running',now)]:
    jobs[label]=job_dispatch.enqueue_scheduled(task._job_env(),'jobs','org.example.background:report',
        dict(first=1,last=500),'cf-'+label,version=2,schedule=durable.JobSchedule(when,when+timedelta(hours=4),20))
release=current_release(env)
claim=durable.claim(env.cr,release['site_id'],release['release_digest'],str(uuid4()),
                    ['org.example.background:report'],lease_seconds=30)
assert claim.job_id==jobs['running']
attachment=env['ir.attachment'].with_user(FIXTURE['users']['alice']['id']).create(dict(
    name='CF checkpoint witness',res_model=APP_MODEL,res_id=APP_ID,
    datas=base64.b64encode(('CF synthetic retained bytes '+SITE+'\\n').encode()*128)))
assert attachment.store_fname and attachment.checksum
env.cr.commit()
print('CF_JOBS='+json.dumps(dict(jobs,reminder=reminder,owner=claim.owner,generation=claim.generation,
    attachment=attachment.id,attachment_checksum=attachment.checksum)))
'''


def shell(site, label, code):
    state = dict(site.state())
    target = load(site.private / 'target.json')
    state.update(database=target['sites'][0]['database'], image_id=target['image_id'])
    return site.native(state, label, [], code).decode()


def queue(target, seed):
    ids = ','.join("'" + seed[key] + "'" for key in ('pending', 'running', 'reminder'))
    return json.loads(sql(target, f"""SELECT jsonb_object_agg(public_id,jsonb_build_object(
        'state',state,'at',available_at,'deadline',deadline_at,'actor',actor_id,'workspace',workspace_id,
        'handler',handler,'key',idempotency_key,'generation',claim_generation,'attempts',attempts,'error',error_code))
        FROM mp_job WHERE public_id IN ({ids})"""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['seed', 'check'])
    parser.add_argument('site', choices=['aurora', 'maintenance'])
    parser.add_argument('--label', default='upgrade')
    args = parser.parse_args()
    args.run = 'cf-01'
    site = FoundationSite(args)
    target = load(site.private / 'target.json')
    path = site.local / 'job-seed.json'
    if args.phase == 'seed':
        assert not path.exists()
        app = load(site.local / 'app-fixtures.json')
        model, ident = ('mp.aurora.task', app['task']) if args.site == 'aurora' else ('maintenance.request', app['request'])
        code = f'FIXTURE={load(site.local / "fixtures.json")!r}\nAPP_MODEL={model!r}\nAPP_ID={ident}\nSITE={args.site!r}\n' + SEED
        raw = shell(site, 'cf-background-seed-v2', code)
        seed, = [json.loads(line.split('=', 1)[1]) for line in raw.splitlines() if line.startswith('CF_JOBS=')]
        seed['original'] = queue(target, seed)
        assert sql(target, "SELECT to_regclass('mp_job_identity') IS NULL;") == 't'
        write(path, seed)
        print(json.dumps(dict(result='seeded', jobs=3, legacy_schema=True)))
    else:
        seed = load(path)
        after = queue(target, seed)
        for ident, old in seed['original'].items():
            for name in ('deadline', 'actor', 'workspace', 'handler', 'key'):
                assert after[ident][name] == old[name], (ident, name)
            if ident != seed['running']:
                assert after[ident]['at'] == old['at']
        assert after[seed['reminder']]['state'] == after[seed['pending']]['state'] == 'pending'
        raw = shell(site, 'cf-stale-claim-' + args.label, f'''
from modular_platform import durable
old=durable.Claim({seed['running']!r},{seed['generation']},{seed['owner']!r})
try:durable.run_fenced(env.cr,old,lambda row:{{'unexpected':True}})
except (durable.ClaimLost,durable.DispatchPaused):print('CF_STALE_DENIED')
else:raise AssertionError('Old claim escaped its release fence')
''')
        assert 'CF_STALE_DENIED' in raw
        result = dict(result='passed', label=args.label, image=target['image_id'],
                      timing_actor_workspace_preserved=True, stale_claim_denied=True, queue=after)
        out = site.local / ('jobs-' + args.label + '.json')
        assert not out.exists()
        write(out, result)
        print(json.dumps(dict(result='passed', stale_claim_denied=True, immutable_fields_preserved=True)))


if __name__ == '__main__':
    main()
