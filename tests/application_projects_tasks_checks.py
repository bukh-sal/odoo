"""Once-only actual optional integration checks on an owned AP-03 site."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'release'), str(ROOT/'tools'), str(ROOT/'packages/platform_sdk')]
from application_adoption_site import AdoptionSite, load, write
from check_reference import Client

PROJECT = 'mp.aurora.project'
TASK = 'mp.aurora.task'
LIST = 'mp.aurora.task.list'
LINK = 'mp.aurora.project.task.link'


def call(client, model, method, args=None, kwargs=None):
    status, value = client.request('/web/dataset/call_kw/'+model+'.'+method,
        dict(jsonrpc='2.0', method='call', id=1,
             params=dict(model=model, method=method, args=args or [], kwargs=kwargs or {})))
    assert status == 200 and 'result' in value, (model, method, value.get('error'))
    return value['result']


def denied(client, model, method, args, kind='AccessError'):
    status, value = client.request('/web/dataset/call_kw/'+model+'.'+method,
        dict(jsonrpc='2.0', method='call', id=1,
             params=dict(model=model, method=method, args=args, kwargs={})))
    assert status == 200 and value.get('error', {}).get('data', {}).get('name') == 'odoo.exceptions.'+kind, (model, method, value)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', default='ap03-projects-tasks-01')
    p.add_argument('--port', type=int, default=18176)
    a = p.parse_args(); site = AdoptionSite(a); assert site.state()['phase'] == 'native_installed'
    path = site.local/'integration-contract.json'
    assert not path.exists(), 'Inspect prior saved step/effects before any continuation'
    record = dict(phase='authenticating', checks=[], records={}); write(path, record)
    def step(name):
        record['phase'] = name; write(path, record)
    def passed(name):
        record['checks'].append(name); write(path, record)
    clients = {n: Client(site, n) for n in ('alice', 'bob', 'operator', 'worker')}
    alice, bob, manager, outsider = [clients[n] for n in ('alice', 'bob', 'operator', 'worker')]
    users = load(site.local/'fixtures.json')['users']; uid = lambda n: users[n]['id']
    c = lambda actor, model, method, args=None, kwargs=None: call(actor, model, method, args, kwargs)
    step('creating_useful_linked_work')
    assert c(alice, PROJECT, 'search_count', [[]]) == c(alice, LINK, 'search_count', [[]]) == 0
    project, = c(alice, PROJECT, 'create', [[dict(name='Workshop inspection', manager_id=uid('operator'), member_ids=[(6, 0, [uid('bob')])])]])
    task_list, = c(alice, LIST, 'create', [[dict(name='Inspection handover', member_ids=[(6, 0, [uid('bob')])])]])
    task, = c(alice, TASK, 'create', [[dict(name='Inspect emergency lighting', list_id=task_list)]])
    link, = c(alice, LINK, 'create', [[dict(project_id=project, task_id=task, note='Evidence for workshop readiness')]])
    record['records'].update(project=project, task_list=task_list, task=task, link=link); write(path, record)
    for actor in (alice, bob):
        assert c(actor, PROJECT, 'read', [[project], ['task_link_count', 'task_link_ids']])[0] == dict(id=project, task_link_count=1, task_link_ids=[link])
        action = c(actor, LINK, 'action_open_task', [[link]])
        assert action['res_id'] == task and action['res_model'] == TASK and action['type'] == 'ir.actions.act_window'
    assert c(manager, PROJECT, 'read', [[project], ['task_link_count', 'task_link_ids']])[0] == dict(id=project, task_link_count=0, task_link_ids=[])
    passed('useful native association;member read/Open;task-outsider project manager sees zero filtered links/count')
    step('checking_asymmetric_denials')
    for actor in (manager, outsider):
        assert c(actor, LINK, 'search_count', [[]]) == 0
        assert c(actor, LINK, 'search_read', [[]], dict(fields=['display_name', 'project_id', 'task_id'])) == []
        assert c(actor, LINK, 'read_group', [[], ['project_id'], ['project_id']]) == []
        denied(actor, LINK, 'read', [[link], ['display_name', 'project_id', 'task_id', 'note']])
        denied(actor, LINK, 'web_read', [[link], dict(project_id=dict(fields=dict(display_name={})), task_id=dict(fields=dict(display_name={})))])
        denied(actor, LINK, 'action_open_task', [[link]])
        denied(actor, LINK, 'create', [[dict(project_id=project, task_id=task)]])
    denied(bob, LINK, 'write', [[link], dict(note='Member write denied')])
    denied(bob, LINK, 'unlink', [[link]])
    denied(bob, LINK, 'create', [[dict(project_id=project, task_id=task)]])
    denied(alice, LINK, 'write', [[link], dict(task_id=task)])
    denied(alice, PROJECT, 'write', [[project], dict(task_link_count=50)])
    denied(alice, PROJECT, 'write', [[project], dict(task_link_ids=[(5,)])])
    passed('asymmetric search/count/group/read/display/web-read/Open/create denials;readonly project member cannot mutate;pair/projection immutable')
    step('testing_current_task_revocation')
    assert c(alice, LIST, 'write', [[task_list], dict(member_ids=[(5,)])])
    assert c(bob, PROJECT, 'read', [[project], ['task_link_count', 'task_link_ids']])[0] == dict(id=project, task_link_count=0, task_link_ids=[])
    assert c(bob, LINK, 'search_count', [[]]) == 0
    denied(bob, LINK, 'read', [[link], ['note']]); denied(bob, LINK, 'action_open_task', [[link]])
    assert c(alice, LIST, 'write', [[task_list], dict(member_ids=[(6, 0, [uid('bob'), uid('operator')])])])
    assert c(bob, LINK, 'search_count', [[]]) == 1
    assert c(manager, LINK, 'write', [[link], dict(note='Manager confirmed linked inspection')])
    passed('task-list revocation hides prior links/counts in same session;restored rights permit manager with both-write to edit')
    step('testing_current_project_revocation')
    assert c(alice, PROJECT, 'write', [[project], dict(member_ids=[(5,)], manager_id=uid('alice'))])
    for actor in (bob, manager):
        assert c(actor, TASK, 'read', [[task], ['name']])[0]['name'] == 'Inspect emergency lighting'
        assert c(actor, LINK, 'search_count', [[]]) == 0
        denied(actor, LINK, 'read', [[link], ['task_id']]); denied(actor, LINK, 'write', [[link], dict(note='Revoked')])
    assert c(alice, PROJECT, 'write', [[project], dict(member_ids=[(6, 0, [uid('bob')])], manager_id=uid('operator'))])
    passed('project membership/manager revocation hides links despite continuing task access;rights restored explicitly')
    step('testing_duplicate_and_active_boundary')
    denied(alice, LINK, 'create', [[dict(project_id=project, task_id=task)]], 'ValidationError')
    assert c(alice, PROJECT, 'write', [[project], dict(active=False)])
    assert c(bob, LINK, 'read', [[link], ['note']])[0]['note'] == 'Manager confirmed linked inspection'
    extra, = c(alice, TASK, 'create', [[dict(name='Check access route', list_id=task_list)]])
    record['records']['extra_task'] = extra; write(path, record)
    denied(alice, LINK, 'create', [[dict(project_id=project, task_id=extra)]], 'ValidationError')
    assert c(alice, PROJECT, 'write', [[project], dict(active=True)])
    assert c(alice, TASK, 'write', [[extra], dict(active=False)])
    denied(alice, LINK, 'create', [[dict(project_id=project, task_id=extra)]], 'ValidationError')
    assert c(alice, TASK, 'write', [[extra], dict(active=True)])
    passed('unique pair;historical archived read;new archived Project or Task association refused')
    step('testing_cascade_and_explicit_unlink')
    witness, = c(alice, LINK, 'create', [[dict(project_id=project, task_id=extra)]])
    assert c(manager, LINK, 'unlink', [[witness]])
    witness, = c(alice, LINK, 'create', [[dict(project_id=project, task_id=extra)]])
    assert c(alice, TASK, 'unlink', [[extra]])
    assert c(alice, LINK, 'search_count', [[('id', '=', witness)]]) == 0 and c(alice, PROJECT, 'read', [[project], ['name']])
    disposable, = c(alice, PROJECT, 'create', [[dict(name='Cascade witness')]])
    witness, = c(alice, LINK, 'create', [[dict(project_id=disposable, task_id=task)]])
    assert c(alice, PROJECT, 'unlink', [[disposable]])
    assert c(alice, LINK, 'search_count', [[('id', '=', witness)]]) == 0 and c(alice, TASK, 'read', [[task], ['name']])
    passed('both-write explicit unlink;Task/Project deletion cascades associations only and preserves opposite business record')
    step('testing_lifecycle_independence_and_views')
    assert c(manager, PROJECT, 'action_activate', [[project]]) and c(manager, PROJECT, 'action_complete', [[project]])
    assert c(alice, TASK, 'read', [[task], ['completed']])[0]['completed'] is False
    for model in (PROJECT, LINK):
        views = c(alice, model, 'get_views', kwargs=dict(views=[(False, 'list'), (False, 'form')], options={}))
        assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
    assert c(manager, PROJECT, 'action_reopen', [[project]])
    assert site.sql(site.state(), 'no-workspaces', 'SELECT (SELECT count(*) FROM mp_workspace),(SELECT count(*) FROM mp_membership),(SELECT count(*) FROM mp_workspace_plugin);').strip() == b'0|0|0'
    passed('Project lifecycle does not mutate Task;native inherited/list/form descriptors;no workspace authority')
    record['phase'] = 'passed'; write(path, record)
    print('passed '+str(len(record['checks']))+' actual integration groups', flush=True)


if __name__ == '__main__':
    main()
