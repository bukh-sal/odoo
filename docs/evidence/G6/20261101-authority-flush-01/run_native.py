"""Source probe uses existing Scope class/native adapters, no image patch."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
parser=argparse.ArgumentParser();parser.add_argument('--installed',action='store_true');parser.add_argument('--case');parser.add_argument('--label',default='source-01');args=parser.parse_args()
assert state['phase'] in ({'identity12_source_failed'} if args.case else {'core10_history_qualified_identity_fix_required'}) if not args.installed else state['phase']=='identity12_completed_needs_verification'
path=ROOT/'platform_addons/mp_identity/scopes.py'
code='FIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\nSEED='+repr(f.load(j.LOCAL/'core10-seed-01.json'))+'\n'
code+="import ast,json,sys,unittest\nfrom odoo.addons.mp_identity import scopes\nenv.cr.rollback()\n"
if not args.installed:
    code+="tree=ast.parse("+repr(path.read_text())+");tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_flush_identity_policy','resolve_scope'}]\nexec(compile(tree,'host_corrected_identity_policy','exec'),scopes.__dict__)\n"
suite="unittest.TestSuite([scope['PendingAuthorityTests']("+repr(args.case)+")])" if args.case else "unittest.defaultTestLoader.loadTestsFromTestCase(scope['PendingAuthorityTests'])"
code+="scope={'ENV':env,'FIXTURE':FIXTURE,'SEED':SEED,'__name__':'native_pending_authority'}\nexec(compile("+repr((OUT/'native_tests.py').read_text())+",'pending_authority_tests','exec'),scope)\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run("+suite+")\nprint('MP_POLICY_FLUSH='+json.dumps(dict(successful=result.wasSuccessful(),tests=result.testsRun,failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors])))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
marker=j.LOCAL/('identity-flush-'+args.label+'.json');assert not marker.exists();f.write(marker,dict(state='running'))
label='identity-flush-'+args.label
try:raw=f.native(state,label,[],code)
except AssertionError:raw=(j.LOCAL/'logs'/(label+'.stdout')).read_bytes()
rows=[json.loads(l.split('MP_POLICY_FLUSH=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_POLICY_FLUSH=')];assert len(rows)==1,'Inspect exact child; no mutation or runner replay'
result=dict(result='passed' if rows[0]['successful'] else 'failed',**rows[0],image_id=state['image_id'],source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [path,ROOT/'platform_addons/mp_identity/__manifest__.py',OUT/'native_tests.py']},installed_source=args.installed,preserves_original_Scope_class=True,all_fixture_writes_rolled_back=True,limits=[] if args.installed else ['Corrected source functions in one short-lived native process; actual immutable identity1.2/HTTP/cross-worker requalification still required before restoring invalidated acceptances.'])
f.save(args.label+'.json',result);f.write(marker,dict(state='completed',**result));f.phase(state,'identity12_'+('installed_' if args.installed else 'source_')+('verified' if rows[0]['successful'] else 'failed'));f.guard(state)
print(json.dumps(dict(result=result['result'],tests=result['tests'],failures=len(result['failures']),errors=len(result['errors']))));raise SystemExit(0 if rows[0]['successful'] else 1)
