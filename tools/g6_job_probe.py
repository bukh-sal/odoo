"""Run captured real-registry F-01b checks once; preserve failed attempts."""
import argparse,hashlib,json,sys
from pathlib import Path
import g6_job_fixture as fixture
f=fixture.f;ROOT=fixture.ROOT;LOCAL=fixture.LOCAL;OUTPUT=fixture.OUTPUT.parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='backend-01');parser.add_argument('--case');parser.add_argument('--resume-suite',action='store_true');args=parser.parse_args()
    import re
    assert re.fullmatch('[a-z0-9-]{1,40}',args.label)
    state=f.load(LOCAL/'state.json');f.guard(state)
    assert state['phase'] in ({'job_tests_failed'} if args.case or args.resume_suite else {'references_installed'})
    marker=LOCAL/('jobs-'+args.label+'.json');assert not marker.exists()
    source=(OUTPUT/'native_tests.py').read_text();selection=f"suite.addTest(scope['AuthorizedJobTests']({args.case!r}))" if args.case else "suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(scope['AuthorizedJobTests']))"
    code=f"""import json,sys,unittest
env.cr.rollback()
scope={{'ENV':env,'FIXTURE':json.loads({(LOCAL/'fixtures.json').read_text()!r}),'__name__':'g6_native_authorized','__file__':'/opt/modular/g6_native_authorized.py'}}
exec(compile({source!r},scope['__file__'],'exec'),scope)
suite=unittest.TestSuite()
{selection}
result=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)
print('MP_G6_JOBS='+json.dumps(dict(tests=result.testsRun,failures=[test.id() for test,_ in result.failures],errors=[test.id() for test,_ in result.errors],successful=result.wasSuccessful())))
env.cr.rollback()
raise SystemExit(0 if result.wasSuccessful() else 1)
"""
    f.write(marker,dict(state='running',image=state['image_id'],case=args.case))
    label='jobs-'+args.label
    try:raw=f.native(state,label,[],code)
    except AssertionError:raw=(LOCAL/'logs'/(label+'.stdout')).read_bytes()
    rows=[json.loads(line.split('MP_G6_JOBS=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_G6_JOBS=')]
    assert len(rows)==1,'Uncertain test outcome: inspect stopped native child and private diagnostics'
    result=rows[0];phase='job_tests_verified' if result['successful'] else 'job_tests_failed'
    f.write(marker,dict(state='completed',**result));f.phase(state,phase)
    path=OUTPUT/(label+'.json');assert not path.exists()
    f.write(path,dict(result='passed' if result['successful'] else 'failed',**result,image_id=state['image_id'],inventory_digest=state['inventory_digest'],project=state['project'],database=state['active_db'],container=state['project']+'-'+label,native_test_sha256=hashlib.sha256(source.encode()).hexdigest(),limits=['Native job authorization integration only; real runner process death, scoped events, external worker and queue-aware restore remain required.','Synthetic rows retained and dispatch paused; metadata temporarily changed by tests is restored. No full G6 acceptance credit.']))
    f.guard(state);print(json.dumps(dict(result=phase,tests=result['tests'],failures=len(result['failures']),errors=len(result['errors']))))
    return 0 if result['successful'] else 1


if __name__=='__main__':sys.exit(main())
