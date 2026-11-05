"""Check the Aurora Tasks native addon on the pinned R1 Odoo image."""

import argparse
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from maintenance_import_probe import BASE_ID, BASE_TAG, ROOT, command, registry_probe


WORKFLOW = """
from contextlib import contextmanager
import json

from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command


@contextmanager
def denied(exception=AccessError):
    try:
        with env.cr.savepoint():
            yield
    except exception:
        pass
    else:
        raise AssertionError('Expected denial')


group = env.ref('base.group_user')
users = env['res.users']
owner, member, assignee, outsider = users.create([
    {'name': role.title(), 'login': 'probe-' + role,
     'group_ids': [Command.set([group.id])]}
    for role in ('owner', 'member', 'assignee', 'outsider')
])
lists = env['mp.aurora.task.list']
stages = env['mp.aurora.task.stage']
tasks = env['mp.aurora.task']
board = lists.with_user(owner).create({'name': 'Probe schedule', 'member_ids': [Command.link(member.id)]})
assert board.owner_id == owner
board.with_user(member).write({'description': 'Updated by member'})
with denied():
    board.with_user(member).write({'member_ids': [Command.link(outsider.id)]})
with denied():
    board.with_user(member).action_archive()
with denied():
    board.with_user(member).unlink()
with denied():
    board.with_user(assignee).read(['name'])

queued, done = stages.with_user(member).create([
    {'name': 'Queued', 'list_id': board.id},
    {'name': 'Done', 'list_id': board.id, 'done': True},
])
task = tasks.with_user(member).create({'name': 'Probe task', 'list_id': board.id,
    'stage_id': queued.id, 'assignee_id': assignee.id, 'due_date': '2030-01-20 12:00:00'})
assert task.creator_id == member
task.with_user(member).write({'stage_id': done.id})
assert task.stage_id == done
assert task.with_user(assignee).read(['name', 'list_id', 'stage_id'])[0]['name'] == 'Probe task'
task.with_user(assignee).write({'description': 'Updated by assignee'})
with denied():
    task.with_user(member).action_archive()
with denied(ValidationError):
    task.with_user(assignee).write({'active': False, 'assignee_id': outsider.id})
task.with_user(assignee).action_archive()
assert not task.active
task.with_user(assignee).action_unarchive()
assert task.active
assert not tasks.with_user(outsider).search([('id', '=', task.id)])
with denied():
    task.with_user(outsider).read(['name'])
with denied():
    task.with_user(outsider).write({'name': 'Unauthorized'})
with denied():
    tasks.with_user(outsider).create({'name': 'Unauthorized', 'list_id': board.id})

other = lists.with_user(owner).create({'name': 'Other list'})
other_stage = stages.with_user(owner).create({'name': 'Other stage', 'list_id': other.id})
with denied(ValidationError):
    task.with_user(owner).write({'stage_id': other_stage.id})
board.with_user(owner).write({'member_ids': [Command.unlink(member.id)]})
assert not lists.with_user(member).search([('id', '=', board.id)])
assert task.with_user(member).read(['name'])[0]['name'] == 'Probe task'
for model in (lists, stages, tasks):
    assert model.with_user(owner).get_views([(False, 'list'), (False, 'form')])['views'].keys() >= {'list', 'form'}
assert env.ref('mp_aurora_tasks.menu_aurora').id in env['ir.ui.menu'].with_user(owner)._visible_menu_ids()
print('MP_NATIVE_RESULT ' + json.dumps({
    'roles': ['owner', 'member', 'assignee outside the list', 'outsider'],
    'membership_archive_delete_owner_only': True,
    'member_created_and_advanced_task': True,
    'assignee_can_edit_archive_and_restore': True,
    'removed_member_retains_creator_access': True,
    'outsider_search_read_write_create_denied': True,
    'cross_list_stage_denied': True,
    'native_menu_and_list_form_descriptors': True,
}))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError(args.receipt)
    assert command('docker', 'image', 'inspect', BASE_TAG, '--format', '{{.Id}}').stdout.strip() == BASE_ID
    suffix = uuid.uuid4().hex[:12]
    tag = 'mp-disposable-aurora-native:' + suffix
    with tempfile.TemporaryDirectory(prefix='mp-aurora-native-') as directory:
        context = Path(directory)
        shutil.copytree(ROOT / 'platform_addons/mp_aurora_tasks', context / 'mp_aurora_tasks')
        (context / 'Dockerfile').write_text(
            f'FROM {BASE_TAG}\nCOPY mp_aurora_tasks /probe/apps/mp_aurora_tasks\n', encoding='utf8')
        command('docker', 'build', '--network', 'none', '--tag', tag, str(context))
    image = command('docker', 'image', 'inspect', tag, '--format', '{{.Id}}').stdout.strip()
    try:
        result = registry_probe(image, suffix, addon='mp_aurora_tasks', workflow=WORKFLOW,
                                addons_path='/opt/modular/addons,/probe/apps')
    finally:
        assert command('docker', 'image', 'inspect', tag, '--format', '{{.Id}}').stdout.strip() == image
        command('docker', 'image', 'rm', tag)
    report = {'base_image': BASE_ID, 'probe_image': image, 'registry': result, 'probe_tag_removed': True}
    with args.receipt.open('x', encoding='utf8') as receipt:
        json.dump(report, receipt, indent=2)
        receipt.write('\n')
    print(json.dumps(report))
    return int(not result.get('workflow_passed'))


if __name__ == '__main__':
    raise SystemExit(main())
