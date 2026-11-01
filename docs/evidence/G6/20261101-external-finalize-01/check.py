"""Candidate native source in existing app process only; no Docker asset creation."""
import hashlib,json,subprocess,sys,tomllib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.contracts import normalize_manifest
from modular_platform.deployment import DockerObserver
from reference_package import assemble

def main():
    attempt=sys.argv[1] if len(sys.argv)>1 else '01'
    if not attempt.isdigit():raise ValueError('Numeric attempt required')
    local=ROOT/'.local/g6-events';label='external-final-apply-'+attempt;marker=local/(label+'.json')
    if marker.exists():raise RuntimeError('Inspect retained attempt; never replay it')
    state=json.loads((local/'state.json').read_text());target=local/'operator/target.json';target_hash=hashlib.sha256(target.read_bytes()).hexdigest()
    protected=state['protected_configurations']
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protected.items())
    config=json.loads(target.read_text());observer=DockerObserver(config);observation=observer.read()
    assert observation['image_id']==state['image_id'] and observation['runtime']['inventory_digest']==state['inventory_digest']
    code='import json,sys,types,unittest\n'
    code+="pkg=types.ModuleType('odoo.addons.mp_example_notes_stats');pkg.__path__=[];sys.modules[pkg.__name__]=pkg\n"
    paths=['platform_addons/mp_core/external_authority.py','platform_addons/mp_core/external_job.py',
        *['platform_addons/mp_example_notes_stats/'+name+'.py' for name in ['contracts','models','services','jobs']]]
    for path in paths:
        parts=path.split('/');package='odoo.addons.'+parts[1];module=package+'.'+Path(path).stem
        code+='m=types.ModuleType('+repr(module)+');m.__package__='+repr(package)+';m.__file__='+repr('/opt/modular/'+path)+';sys.modules[m.__name__]=m\n'
        code+='exec(compile('+repr((ROOT/path).read_text(encoding='utf8'))+',m.__file__,"exec"),m.__dict__)\n'
        code+='setattr(sys.modules['+repr(package)+'],'+repr(Path(path).stem)+',m)\n'
        if module.endswith('notes_stats.models'):
            code+="env.registry.load(types.SimpleNamespace(name='mp_example_notes_stats'));env.registry._setup_models__(env.cr,['mp.example.notes.stats'])\n"
    values=dict(ENV=None,FIXTURE=json.loads((local/'fixtures.json').read_text()),
        MANIFEST=normalize_manifest(tomllib.loads((ROOT/'plugins/notes_stats/plugin.toml').read_text())),
        PROVIDER=normalize_manifest(tomllib.loads((ROOT/'plugins/document_stats/plugin.toml').read_text())),
        ENDPOINT=json.loads((ROOT/'packages/contracts/examples/v1/endpoint.json').read_text()))
    values.pop('ENV')
    code+='scope='+repr(values)+';scope.update(ENV=env,__name__="native_final_apply")\n'
    previous=ROOT/'docs/evidence/G6/20261101-notes-analysis-01/native_tests.py'
    code+='exec(compile('+repr(previous.read_text())+',"retained_connector_test_helpers","exec"),scope)\n'
    code+='exec(compile('+repr((OUT/'native_tests.py').read_text())+',"current_final_apply_tests","exec"),scope)\n'
    code+='env.cr.rollback();before=scope["rows"]();env.cr.rollback()\nresult=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(scope["FinalizeTests"]))\n'
    code+='env.cr.rollback();restored=scope["rows"]()==before\nprint("MP_FINAL_APPLY="+json.dumps(dict(successful=result.wasSuccessful() and restored,tests=result.testsRun,errors=[t.id() for t,_ in result.errors],failures=[t.id() for t,_ in result.failures],original_rows_restored=restored)))\nenv.cr.rollback();raise SystemExit(0 if result.wasSuccessful() and restored else 1)\n'
    marker.write_text(json.dumps(dict(state='running',label=label))+'\n')
    with (local/'logs'/(label+'.stdout')).open('xb') as stdout,(local/'logs'/(label+'.stderr')).open('xb') as stderr:
        process=subprocess.run(['docker','exec','-i',observer._container('app'),'/venv/bin/python','odoo-bin','shell',
            '-c','/run/secrets/odoo_config','-d',config['sites'][0]['database'],'--no-http','--workers=0','--max-cron-threads=0'],
            input=code.encode(),stdout=stdout,stderr=stderr,timeout=180)
    records=[json.loads(line.split('=',1)[1]) for line in (local/'logs'/(label+'.stdout')).read_text().splitlines() if line.startswith('MP_FINAL_APPLY=')]
    if len(records)!=1:raise RuntimeError('Inspect exact private logs and process; no result marker')
    result=records[0];assert result['successful']==(process.returncode==0)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==target_hash
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protected.items())
    report=dict(utc=datetime.now(timezone.utc).isoformat(),result='passed' if result['successful'] else 'failed',attempt=attempt,**result,
        sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
        image=state['image_id'],inventory=state['inventory_digest'],new_docker_assets=0,installed=False,actual_remote_compute=False,
        acceptance_credit=False,limits=['Candidate source loaded in isolated existing-container Odoo process; no installed code changed.',
            'Native provider/connector/queue/business fixture writes roll back; sequence counters may advance.',
            'Temporary public-key/authority files are test fixtures, not actual operator approval or image attestation.',
            'No actual worker request, metadata lifecycle/connector deployment or cross-runtime atomicity claim.'])
    (OUT/('attempt-'+attempt+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    marker.write_text(json.dumps(dict(state='completed',**report),indent=2)+'\n')
    if result['successful']:(OUT/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['result','tests','errors','failures']}))
    raise SystemExit(0 if result['successful'] else 1)

if __name__=='__main__':main()
