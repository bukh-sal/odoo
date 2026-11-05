"""Provision two independent disposable stock WebClient lifecycle targets."""

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'release'))
from initialize_reference import Reference, inspect_image, load, protect_directory, write
from modular_platform.catalog import Catalog
from modular_platform.artifacts import ArtifactValidator, TrustPolicy


ADDONS = {'aurora': 'mp_aurora_tasks', 'maintenance': 'maintenance'}
POSTGRES = 'sha256:d81f7b51697014367236d07ec58b54153fc28f828b72bf247fe5c7487520bcb0'
PROXY = 'sha256:dece6f0a0402ab7187d5d0594056ad12fdbe1265c30f0e6134966e55c432828f'
SUBNETS = {
    'aurora': {'runtime': '10.233.241.0/28', 'edge': '10.233.241.16/28'},
    'maintenance': {'runtime': '10.233.241.32/28', 'edge': '10.233.241.48/28'},
}
TRUST = {'schema_version': 1, 'mode': 'curated', 'approved_digests': [],
         'allow_unsigned_development': False, 'generation': 1}
SEED_APP = """
import json
from odoo.fields import Command

assert env.cr.dbname.startswith('mp_disposable_r0_r1_release_')
users = env['res.users']
alice = users.search([('login', '=', 'r1_alice')], limit=1)
bob = users.search([('login', '=', 'r1_bob')], limit=1)
operator = users.search([('login', '=', 'r1_operator')], limit=1)
assert alice and bob and operator
if APP == 'mp_aurora_tasks':
    board = env['mp.aurora.task.list'].with_user(alice).create({
        'name': 'Foundation schedule', 'member_ids': [Command.link(bob.id)]})
    queued, done = env['mp.aurora.task.stage'].with_user(alice).create([
        {'name': 'Queued', 'list_id': board.id},
        {'name': 'Done', 'list_id': board.id, 'done': True},
    ])
    task = env['mp.aurora.task'].with_user(bob).create({
        'name': 'Inspect foundation fixtures', 'list_id': board.id,
        'stage_id': queued.id, 'assignee_id': bob.id,
        'due_date': '2030-01-20 12:00:00',
    })
    result = {'list': board.id, 'task': task.id, 'queued': queued.id, 'done': done.id}
else:
    alice.group_ids = [Command.link(env.ref('maintenance.group_equipment_manager').id)]
    equipment = env['maintenance.equipment'].with_user(alice).create({'name': 'Foundation pump'})
    request = env['maintenance.request'].with_user(alice).create({
        'name': 'Inspect foundation pump', 'equipment_id': equipment.id,
        'owner_user_id': alice.id, 'user_id': alice.id,
    })
    result = {'equipment': equipment.id, 'request': request.id, 'queued': request.stage_id.id,
              'done': env['maintenance.stage'].search([('done', '=', True)], limit=1).id}
assert all(result.values())
env.cr.commit()
print('MP_STRESS_RESULT=' + json.dumps(result))
"""


class StressSite(Reference):
    def __init__(self, args):
        self.args = args
        self.local = ROOT / '.local/foundation-stress/sites-02' / args.site
        self.private = self.local / 'operator'

    def prepare(self):
        record = load(self.args.candidate)
        image = record['image_id']
        runtime = inspect_image(image)
        policy = load(ROOT / 'deploy/distribution-r1-foundation-stress.json')
        if record['state'] != 'built' or runtime['inventory']['policy'] != policy:
            raise ValueError('Use the exact disposable stress-test policy and build receipt')
        if record['inventory_digest'] != runtime['inventory_digest']:
            raise ValueError('Candidate inventory changed')
        images = {'application': image, 'postgres': POSTGRES, 'proxy': PROXY}
        self.prepare_resources({'images': {key: {'image_id': value} for key, value in images.items()},
                                'application_inventory_digest': record['inventory_digest']},
                               record['git_base'], json.dumps(TRUST).encode(), subnets=SUBNETS[self.args.site])
        Catalog(self.private / 'catalog', ArtifactValidator(TrustPolicy()))

    def initialize(self):
        state = self.state()
        if state['phase'] != 'configured':
            raise ValueError('Inspect the recorded phase before attempting further mutations')
        addon = ADDONS[self.args.site]
        self.initialize_core(state, 'mp_core,auth_password_policy,' + addon)
        raw = self.native(state, 'stress-app-provision', [], f'APP = {addon!r}\n' + SEED_APP)
        rows = [line.split('=', 1)[1] for line in raw.decode().splitlines() if line.startswith('MP_STRESS_RESULT=')]
        if len(rows) != 1:
            raise ValueError('Inspect the native transaction before attempting another seed')
        write(self.local / 'app-fixtures.json', json.loads(rows[0]))
        self.publish(state, prepare_assets=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'initialize', 'status'])
    parser.add_argument('site', choices=ADDONS)
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    args.port = {'aurora': 18104, 'maintenance': 18105}[args.site]
    getattr(StressSite(args), args.action)()
