"""Exercise the native history action and scope boundaries over the guarded edge."""

from datetime import datetime, timedelta, timezone
import json
import sys
from uuid import uuid4

from background_lifecycle import shell
from background_site import load, write
from background_workers import Probe
from check_reference import Client


RUN = 'bx-01-scoped-history-01'
MODEL = 'mp.job.history'
SPEC = {key: {} for key in ('public_id', 'state', 'status_at', 'archived')}


PLAN = """
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.tools import SQL
assert env.cr.dbname == EXPECTED_DB and EXPECTED_DB.startswith('mp_disposable_r0_r1_release_')
actor = scoped_environment(api.Environment(env.cr, FIXTURE['users']['alice']['id'], {}),
                           FIXTURE['workspaces']['A']['public_id'])
history = actor['mp.job.history']
query = history._search([], offset=50, limit=50, order=history._order)
env.cr.execute(SQL('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) %s', query.select(SQL.identifier(history._table, 'id'))))
plan, = env.cr.fetchone()[0]
print('MP_HISTORY_PLAN='+json.dumps(plan))
"""


def rpc(client, path, params, *, workspace='A', denied=False, headers=None):
    status, value = client.request(path, dict(jsonrpc='2.0', method='call', id=1, params=params), workspace, headers)
    assert status == 200, (path, status)
    if denied:
        assert value.get('error', {}).get('data', {}).get('name', '').endswith(('AccessError', 'ClientReleaseMismatch')), value
        return
    assert 'result' in value, value.get('error', {}).get('data', {}).get('name')
    return value['result']


def dataset(client, method, *, args=(), kwargs=None, workspace='A', denied=False, headers=None, model=MODEL):
    return rpc(client, '/web/dataset/call_kw/' + model + '.' + method,
               dict(model=model, method=method, args=list(args), kwargs=kwargs or {}),
               workspace=workspace, denied=denied, headers=headers)


def seed(probe):
    own = [str(uuid4()) for _ in range(55)]
    alice_b, bob_b, foreign_site, same_workspace_other = [str(uuid4()) for _ in range(4)]
    wrong_site = str(uuid4())
    values = [(job, 'alice', 'A', ('held', 'outcome_unknown', 'completed')[min(index, 2)], index == 54, False)
              for index, job in enumerate(own)]
    values += [(alice_b, 'alice', 'B', 'completed', False, False), (bob_b, 'bob', 'B', 'completed', False, False),
               (foreign_site, 'alice', 'A', 'completed', False, True),
               (same_workspace_other, 'bob', 'A', 'completed', False, False)]
    rows = ','.join(f"({n},'{job}','{probe.fixture['users'][actor]['principal_id']}',"
                    f"'{probe.fixture['workspaces'][workspace]['public_id']}','{state}',{str(old).lower()},{str(foreign).lower()})"
                    for n, (job, actor, workspace, state, old, foreign) in enumerate(values))
    probe.sql(f"""WITH seed(n,job,actor,workspace,state,old,foreign_site) AS (VALUES {rows})
        INSERT INTO mp_job
            (public_id,site_id,workspace_id,actor_id,installation_id,handler,handler_version,
             release_digest,payload,input_digest,idempotency_key,effect_mode,state,attempts,
             max_attempts,claim_generation,dispatch_generation,available_at,deadline_at,
             cancel_requested,effect_started,progress,created_at,finished_at,result)
        SELECT s.job,CASE WHEN s.foreign_site THEN '{wrong_site}' ELSE c.site_id END,w.id,p.id,i.id,
            'org.example.background:report',2,c.release_digest,'{{"fixture":"BX-private-input"}}'::jsonb,
            'sha256:'||repeat('a',64),'bx-scoped-history:'||s.n,
            CASE WHEN s.state='outcome_unknown' THEN 'reconcile' ELSE 'idempotent' END,s.state,1,1,1,c.generation,
            now()-interval '12 days',now()-CASE WHEN s.old THEN interval '10 days' ELSE interval '1 day' END,
            false,s.state='outcome_unknown',100,now()-interval '12 days',
            now()-CASE WHEN s.old THEN interval '11 days' ELSE interval '1 day' END-s.n*interval '1 second',
            '{{"fixture":"BX-private-result"}}'::jsonb
        FROM seed s CROSS JOIN mp_dispatch_control c CROSS JOIN mp_workspace w CROSS JOIN mp_principal p
        CROSS JOIN mp_plugin_installation i WHERE p.public_id=s.actor AND w.public_id=s.workspace
            AND i.plugin_id='org.example.background' ORDER BY s.n""")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    review = probe.operator.run('archive-review', cutoff=cutoff, limit=1)
    assert review['review']['jobs'] == [own[-1]]
    assert probe.operator.run('archive-apply', approval=review['approval'])['jobs'] == [own[-1]]
    record = dict(own=own, alice_b=alice_b, bob_b=bob_b, foreign_site=foreign_site, other=same_workspace_other)
    write(probe.site.local / 'scoped-history-seed.json', record)
    return record


def check(probe, seed):
    alice, bob = Client(probe.site, 'alice'), Client(probe.site, 'bob')
    action = rpc(alice, '/web/action/load', dict(action_id='mp_core.action_job_history'))
    assert action['res_model'] == MODEL and action['view_mode'] == 'list' and action['limit'] == 50
    requested = [*action['views'], [action['search_view_id'][0], 'search']]
    views = dataset(alice, 'get_views', kwargs=dict(views=requested, options={}))
    arch = views['views']['list']['arch']
    assert 'create="0"' in arch and 'edit="0"' in arch and 'export_xlsx="0"' in arch
    assert 'needs_attention' in views['views']['search']['arch']

    def page(client, domain, *, workspace='A', offset=0):
        return dataset(client, 'web_search_read', workspace=workspace, kwargs=dict(
            domain=domain, specification=SPEC, offset=offset, limit=50, count_limit=10000))

    all_ids = [*seed['own'], seed['alice_b'], seed['bob_b'], seed['foreign_site'], seed['other']]
    domain = [['public_id', 'in', all_ids]]
    first = page(alice, domain)
    second = page(alice, domain, offset=50)
    receipts = first['records'] + second['records']
    assert first['length'] == second['length'] == 55 and len(first['records']) == 50 and len(second['records']) == 5
    assert [row['public_id'] for row in receipts] == seed['own']
    assert all(set(row) == {'id', *SPEC} for row in receipts)
    assert receipts[-1]['archived'] and receipts[-1]['state'] == 'completed'
    assert not any(row['archived'] for row in receipts[:-1])
    assert [row['state'] for row in receipts[:2]] == ['held', 'outcome_unknown']
    assert [row['public_id'] for row in page(alice, domain, workspace='B')['records']] == [seed['alice_b']]
    bob_rows = page(bob, domain, workspace='B')['records']
    assert [row['public_id'] for row in bob_rows] == [seed['bob_b']]
    dataset(alice, 'web_read', args=([bob_rows[0]['id']], {}), workspace='B', denied=True)
    dataset(alice, 'read', args=([receipts[-1]['id']], ['public_id']), workspace='B', denied=True)
    dataset(alice, 'read', args=([receipts[-1]['id']], ['public_id']), workspace=None, denied=True)
    dataset(bob, 'search_count', args=([],), workspace='A', denied=True)
    dataset(alice, 'write', args=([receipts[0]['id']], {'state': 'completed'}), denied=True)
    dataset(alice, 'unlink', args=([receipts[0]['id']],), denied=True)
    dataset(alice, 'create', args=({'public_id': str(uuid4())},), denied=True)
    dataset(alice, 'search_count', args=([],), model='mp.job', denied=True)
    dataset(alice, 'search_count', args=([],), model='mp.job.identity', denied=True)

    alerts = probe.operator.run('history')['alerts']
    assert alerts == []
    probe.sql("""INSERT INTO mp_job
        (public_id,site_id,workspace_id,actor_id,installation_id,handler,handler_version,release_digest,
         payload,input_digest,idempotency_key,effect_mode,state,attempts,max_attempts,claim_generation,
         dispatch_generation,available_at,deadline_at,cancel_requested,effect_started,progress,created_at)
        SELECT gen_random_uuid()::text,site_id,workspace_id,actor_id,installation_id,handler,handler_version,
            release_digest,'{}'::jsonb,input_digest,'bx-alert-load:'||n,'idempotent','completed',1,1,1,
            dispatch_generation,now(),now(),false,false,100,now()
        FROM (SELECT * FROM mp_job ORDER BY id LIMIT 1) sample CROSS JOIN generate_series(1,100002) n""")
    alerts = probe.operator.run('history')['alerts']
    assert alerts == [dict(table='mp_job', status='over_limit', rows_observed=100001, count_is_lower_bound=True)]
    assert page(alice, domain)['records'] == first['records']
    assert probe.sql("SELECT count(*) FROM pg_indexes WHERE tablename IN ('mp_job','mp_job_identity') AND indexname LIKE '%history_order%'") == '2'
    alice_id = probe.fixture['users']['alice']['principal_id']
    workspace_b = probe.fixture['workspaces']['B']['public_id']
    probe.sql(f"""UPDATE mp_membership m SET state='revoked' FROM mp_principal p,mp_workspace w
        WHERE m.principal_id=p.id AND p.public_id='{alice_id}' AND m.workspace_id=w.id AND w.public_id='{workspace_b}'""")
    dataset(alice, 'search_count', args=([],), workspace='B', denied=True)
    report = dict(image=probe.state['image_id'], stock_action_and_view=True, page_sizes=[50, 5],
                  archived_original_id=True, held_and_unknown_visible=True, actor_workspace_and_site_isolated=True,
                  direct_foreign_ids_denied=True, absent_scope_denied=True, private_models_denied=True,
                  revoked_workspace_denied=True, mutations_denied=True, safe_projection=True,
                  indexes_present=2, operator_alerts=alerts)
    write(probe.site.local / 'scoped-history-result.json', report)
    print(json.dumps(report), flush=True)


def measure(probe):
    receipt = probe.site.local / 'scoped-history-result.json'
    result = load(receipt)
    assert result['stock_action_and_view'] and 'page_plan' not in result
    path = probe.site.local / 'scoped-history-plan.json'
    if path.exists():
        plan = load(path)
    else:
        probe.sql('ANALYZE mp_job; ANALYZE mp_job_identity;')
        source = f"import json\nFIXTURE={probe.fixture!r}\nEXPECTED_DB={probe.state['database']!r}\n" + PLAN
        raw = shell(probe, 'bx01-scoped-history-plan', source)
        plan, = [json.loads(row.split('=', 1)[1]) for row in raw.splitlines() if row.startswith('MP_HISTORY_PLAN=')]
        write(path, plan)

    def indexes(node):
        return ([node['Index Name']] if 'Index Name' in node else []) + [
            name for child in node.get('Plans', []) for name in indexes(child)]

    selected = indexes(plan['Plan'])
    assert plan['Plan']['Actual Rows'] == 50
    result['page_plan'] = dict(rows=50, offset=50, selected_indexes=selected, execution_ms=plan['Execution Time'])
    write(receipt, result)
    print(json.dumps(result['page_plan']), flush=True)


if __name__ == '__main__':
    probe = Probe(RUN)
    assert probe.state['database'].startswith('mp_disposable_r0_r1_release_')
    if sys.argv[1:] != ['--measure-existing']:
        check(probe, seed(probe))
    measure(probe)
