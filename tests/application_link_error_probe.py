"""Rollback-only developer-group error confidentiality on an owned native site."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'release'), str(ROOT/'tools'), str(ROOT/'packages/platform_sdk')]
from application_adoption_site import AdoptionSite, load, write
from application_release_checks import native_result, sync

PROBE = '''
import json
from odoo import api,Command
from odoo.exceptions import AccessError
from types import SimpleNamespace
from unittest.mock import patch
uid=FIXTURE['users']['worker']['id']
with env.registry.cursor() as cr:
 admin=api.Environment(cr,1,{})
 before=sorted(admin['res.users'].browse(uid).group_ids.ids)
 admin['res.users'].browse(uid).write({'group_ids':[Command.link(admin.ref('base.group_no_one').id)]})
 actor=api.Environment(cr,uid,{},su=False)
 assert not actor.su and actor.user._has_group('base.group_no_one')
 # This is a known existing link to two resources the actor cannot read.
 actor['mp.aurora.project.task.link'].browse(LINK).exists()
 # Shell has no HTTP session: simulate only the debug presentation flag.
 # Actual group membership, actor, ACLs and record rules remain authoritative.
 with patch('odoo.addons.base.models.res_users.request',SimpleNamespace(session=SimpleNamespace(debug=True))):
  assert actor.user.has_group('base.group_no_one')
  try:actor['mp.aurora.project.task.link'].browse(LINK).read(['display_name','project_id','task_id','note'])
  except AccessError as error:
   message=str(error)
   leaked=any(name in message for name in HIDDEN_NAMES)
  else:raise AssertionError('Unauthorized link read succeeded')
 cr.rollback()
with env.registry.cursor() as cr:
 admin=api.Environment(cr,1,{})
 assert sorted(admin['res.users'].browse(uid).group_ids.ids)==before
 cr.rollback()
print('MP_AT_PUBLICATION='+json.dumps(dict(result='failed' if leaked else 'passed',hidden_record_name_in_error=leaked,ordinary_read_denied=True,temporary_group_change_rolled_back=True,debug_request_flag_simulated=True)))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', default='ap03-projects-tasks-01'); p.add_argument('--port', type=int, default=18176)
    p.add_argument('--label', required=True)
    a = p.parse_args(); assert a.label in {'baseline', 'baseline-debug', 'fixed'}
    site = AdoptionSite(a); path = site.local/('error-confidentiality-'+a.label+'.json')
    assert not path.exists()
    seed = load(site.local/'integration-contract.json')['records']
    write(path, dict(phase='probing_rollback_only'))
    code = 'FIXTURE='+repr(load(site.local/'fixtures.json'))+'\nLINK='+str(seed['link'])+'\nHIDDEN_NAMES='+repr(['Inspect emergency lighting','Workshop inspection'])+'\n'+PROBE
    result = native_result(site, 'link-error-'+a.label, code)
    write(path, result); print(json.dumps(result))


if __name__ == '__main__':
    main()
