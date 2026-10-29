"""Run native PostgreSQL primitive proofs only on the once-owned G6 site."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from g6_fixture import ROOT,LOCAL,OUTPUT,load,write,save,phase,guard,native,sql
from modular_platform.deployment import inspect_image


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='backend-01');parser.add_argument('--case');args=parser.parse_args()
    import re
    assert re.fullmatch('[a-z0-9-]{1,40}',args.label)
    state=load(LOCAL/'state.json');guard(state)
    if args.case:
        assert state['phase']=='primitive_tests_failed' and re.fullmatch('test_[a-z0-9_]+',args.case)
    else:
        assert state['phase']=='references_installed'
        assert json.loads(sql(state,'assert-primitive-start-empty',"SELECT jsonb_build_array((SELECT count(*) FROM mp_job),(SELECT count(*) FROM mp_outbox),(SELECT count(*) FROM mp_dispatch_control));"))==[0,0,0]
    marker=LOCAL/('primitive-'+args.label+'.json');assert not marker.exists()
    runtime=inspect_image(state['image_id']);paths=['packages/platform_sdk/modular_platform/durable.py','platform_addons/mp_core/async_models.py','platform_addons/mp_core/__manifest__.py']
    for path in paths:
        name=path.replace('platform_addons/','addons/');assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==runtime['inventory']['files'][name]
    source=(OUTPUT/'native_tests.py').read_text();validation=(ROOT/'tests/test_durable_validation.py').read_text()
    code="""import json,sys,types,unittest
env.cr.rollback()
scope={'ENV':env,'FIXTURE':json.loads(FIXTURE),'__name__':'g6_native_primitive','__file__':'/opt/modular/g6_native_primitive.py'}
exec(compile(SOURCE,scope['__file__'],'exec'),scope)
tests=unittest.TestSuite()
if CASE:tests.addTest(scope['DurablePostgresTests'](CASE))
else:tests.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(scope['DurablePostgresTests']))
unit=types.ModuleType('g6_private_validation');unit.__file__='/opt/modular/tests/test_durable_validation.py'
exec(compile(VALIDATION,unit.__file__,'exec'),unit.__dict__)
tests.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(unit.DurableValidationTests))
result=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(tests)
print('MP_G6_PRIMITIVES='+json.dumps({'tests':result.testsRun,'failures':[test.id() for test,_ in result.failures],'errors':[test.id() for test,_ in result.errors],'skipped':len(result.skipped),'successful':result.wasSuccessful()}))
env.cr.rollback()
raise SystemExit(0 if result.wasSuccessful() else 1)
"""
    # Replace full tokens, not text inside already inserted fixture/source JSON.
    code=code.replace('json.loads(FIXTURE)','json.loads('+repr((LOCAL/'fixtures.json').read_text())+')').replace('compile(SOURCE,','compile('+repr(source)+',').replace('compile(VALIDATION,','compile('+repr(validation)+',').replace('if CASE:','if '+repr(args.case)+':').replace('(CASE))','('+repr(args.case)+'))')
    write(marker,dict(state='running',image_id=state['image_id'],case=args.case))
    label='primitive-'+args.label
    try:raw=native(state,label,[],code)
    except AssertionError:
        raw=(LOCAL/'logs'/(label+'.stdout')).read_bytes()
    rows=[json.loads(line.split('MP_G6_PRIMITIVES=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_G6_PRIMITIVES=')]
    assert len(rows)==1,'Uncertain test outcome: inspect native child/private diagnostics before any new invocation'
    result=rows[0];finished='durable_primitives_verified' if result['successful'] else 'primitive_tests_failed'
    write(marker,dict(state='completed',**result));phase(state,finished)
    save(label+'.json',dict(result='passed' if result['successful'] else 'failed',**result,image_id=state['image_id'],inventory_digest=state['inventory_digest'],project=state['project'],database=state['active_db'],container=state['project']+'-'+label,core_native_version='19.0.0.1.7',source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths+['tests/test_durable_validation.py']},native_test_sha256=hashlib.sha256(source.encode()).hexdigest(),limits=['Real primitive/native/PostgreSQL proof; current actor/plugin dispatch adapters, subscriptions, external service and restore reconciliation remain F-01b..f.','Only explicitly owned synthetic unfinished test jobs held; rows/business effects/uncertain outcomes retained. Site dispatch is paused after suite.','No complete G6 acceptance credit from primitives alone.']))
    guard(state);print(json.dumps(dict(result=finished,tests=result['tests'],failures=len(result['failures']),errors=len(result['errors']))))
    return 0 if result['successful'] else 1


if __name__=='__main__':sys.exit(main())
