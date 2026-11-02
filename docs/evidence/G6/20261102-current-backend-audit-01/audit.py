"""Bounded current G6 backend audit; no lifecycle replay or browser claim."""
import argparse,ast,gzip,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('current_ui_release',OUT.parent/'20261102-notes-stats-ui-source-01/upgrade.py')
current=importlib.util.module_from_spec(spec);spec.loader.exec_module(current)
base,f,j=current.base,current.f,current.j;f.OUTPUT=OUT
from modular_platform.operator_os import protect_directory
PRIVATE=j.LOCAL/'current-backend-audit-01';MARKER=PRIVATE/'audit.json'

def native(second=False):
    state,executor=current.context();assert executor.config['generation']==24
    if not second:assert not PRIVATE.exists();protect_directory(PRIVATE)
    else:assert f.load(MARKER)['state']=='running_native_guards'
    suffix='02' if second else '01'
    before=base.snapshot(state,'current-backend-data-before-'+suffix);worker=base.worker(executor,'current-backend-worker-before-'+suffix)
    assert len(before['mp_job'])==30 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    if not second:f.write(PRIVATE/'data-before.json',before);f.write(PRIVATE/'worker-before.json',worker)
    else:
        assert before==f.load(PRIVATE/'data-before.json') and worker==f.load(PRIVATE/'worker-before.json')
    source=ROOT/'docs/evidence/G6/20261101-core12-runner-01/native_guards.py'
    retained=f.load(source.parent/'native-guards-02.json');assert hashlib.sha256(source.read_bytes()).hexdigest()==retained['test_sha256']
    if second:source=OUT/'native_guards.py'
    label='current-backend-native-guards-'+suffix;f.write(MARKER,dict(state='running_native_guards'+('_02' if second else ''),container=state['project']+'-'+label))
    code="import json,sys,unittest\nscope={'ENV':env,'FIXTURE':"+repr(f.load(j.LOCAL/'fixtures.json'))+",'__name__':'current_installed_job_guards'}\nexec(compile("+repr(source.read_text())+",'current_installed_job_guards','exec'),scope)\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(scope['CurrentJobGuards']))\nprint('MP_CURRENT_GUARDS='+json.dumps(dict(tests=result.testsRun,successful=result.wasSuccessful(),errors=[t.id() for t,_ in result.errors],failures=[t.id() for t,_ in result.failures])))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() else 1)"
    try:raw=f.native(state,label,[],code)
    except AssertionError:raw=(j.LOCAL/'logs'/(label+'.stdout')).read_bytes()
    rows=[json.loads(line.split('MP_CURRENT_GUARDS=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_CURRENT_GUARDS=')]
    assert len(rows)==1,'Inspect retained process/log before continuation; never blindly rerun'
    row=rows[0];assert row['successful'] and row['tests']==12,row
    assert base.snapshot(state,'current-backend-data-after-native-'+suffix)==before
    assert base.worker(executor,'current-backend-worker-after-native-'+suffix)==worker
    f.save('native-guards.json',dict(result='passed_current_installed_native_job_guards',**row,native_generation=24,image=state['image_id'],
        original_test_sha256=retained['test_sha256'],test_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        unchanged_test_reused=not second,fixture_only_reuses_existing_Bob_membership=second,source_substitution=False,all_test_writes_rolled_back=True,
        all17tables_and_worker_authority_exact=True,browser_verified=False))
    marker=f.load(MARKER);marker['state']='native_guards_verified';f.write(MARKER,marker)
    print('12 actual installed native job guard cases pass; fixture-only membership adaptation, all17tables/worker exact, no crash/recovery replay')

def native02():native(second=True)

def nodes(source):
    result={}
    def walk(body,prefix=''):
        for node in body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                name=prefix+node.name;result[name]=ast.dump(node,include_attributes=False)
                if isinstance(node,ast.ClassDef):walk(node.body,name+'.')
    walk(ast.parse(source).body);return result

def boundaries():
    assert not (OUT/'source-boundaries.json').exists()
    names=['20261101-core12-runner-01/qualification.json','20261102-job03-01/qualification.json',
           '20261102-reference-restore-01/qualification.json','20261102-worker-image-success-01/qualification.json']
    rows=[]
    for name in names:
        proof=f.load(OUT.parent/name)
        for path,digest in proof['source_sha256'].items():
            raw=(ROOT/path).read_bytes();actual=hashlib.sha256(raw).hexdigest()
            row=dict(evidence=name,path=path,qualified_sha256=digest,current_sha256=actual,byte_exact=actual==digest)
            if actual!=digest:
                history=subprocess.check_output(['git','log','-40','--format=%H','--',path],cwd=ROOT).decode().split()
                match=None
                for commit in history:
                    old=subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
                    if hashlib.sha256(old).hexdigest()==digest:match=(commit,old);break
                assert match,'Missing exact old source for '+path
                a,b=nodes(match[1]),nodes(raw);row.update(qualified_source_commit=match[0],changed_definitions=sorted(n for n in a.keys()|b.keys() if a.get(n)!=b.get(n)))
            rows.append(row)
    events=f.load(OUT.parent/'20261101-notes7-candidate-01/candidate-build.json')['source_sha256']
    paths=['platform_addons/mp_core/event_models.py','platform_addons/mp_core/async_models.py','platform_addons/mp_core/controllers.py',
        'platform_addons/mp_core/dispatch.py','platform_addons/mp_core/events.py','packages/platform_sdk/modular_platform/event_store.py',
        'platform_addons/mp_example_notes_labels/event_projection.py','platform_addons/mp_example_notes_labels/models.py',
        'platform_addons/mp_identity/models/scoped.py','platform_addons/mp_identity/scopes.py','platform_addons/mp_shell/static/src/event_client.js']
    assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==events[path] for path in paths)
    f.save('source-boundaries.json',dict(result='source_boundaries_observed_review_required',qualified_to_current=rows,
        all11_event_authority_transport_consumer_paths_byte_exact=True,event_paths={p:events[p] for p in paths},
        limits=['Changed definitions are identified, not automatically accepted as covered. Review the exact source diff and successor evidence.',
                'No browser or whole G6 qualification claim.']))
    print(json.dumps(dict(rows=len(rows),drift=[dict(evidence=r['evidence'],path=r['path'],definitions=r.get('changed_definitions')) for r in rows if not r['byte_exact']],event_paths_exact=len(paths))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['native','native02','boundaries']);globals()[p.parse_args().action]()
