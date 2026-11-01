"""Load candidate feature writer in an existing-container rollback-only process."""
import hashlib,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from modular_platform.catalog import Catalog
from modular import configuration

def main():
    attempt=sys.argv[1] if len(sys.argv)>1 else '01'
    if not attempt.isdigit():raise ValueError('Numeric attempt required')
    local=ROOT/'.local/g6-events';label='native-feature-sql-'+attempt;marker=local/(label+'.json')
    if marker.exists():raise RuntimeError('Inspect existing attempt; never replay')
    state=json.loads((local/'state.json').read_text());target=local/'operator/target.json';config=json.loads(target.read_text())
    protected={str(target):hashlib.sha256(target.read_bytes()).hexdigest(),**{str(ROOT/p):h for p,h in state['protected_configurations'].items()}}
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items())
    observer=DockerObserver(config);observation=observer.read()
    assert observation['image_id']==state['image_id'] and observation['runtime']['inventory_digest']==state['inventory_digest']
    catalog=Catalog(local/'operator/catalog',configuration(local/'operator/trust.json'),readonly=True).snapshot()
    names=['plans','projection','planning_cli','lifecycle_planning','feature_metadata','coordinated_feature_metadata']
    sources={n:(ROOT/'packages/platform_sdk/modular_platform'/f'{n}.py').read_text(encoding='utf8') for n in names}
    code='import configparser,json,types,sys,psycopg2\nsources='+repr(sources)+'\n'
    code+='for name,source in sources.items():\n ident="modular_platform."+name\n m=types.ModuleType(ident);m.__package__="modular_platform";m.__file__="/opt/modular/packages/platform_sdk/modular_platform/"+name+".py";sys.modules[ident]=m\n exec(compile(source,m.__file__,"exec"),m.__dict__)\n'
    values=dict(CONFIG=config,RUNTIME=observation['runtime'],CATALOG=catalog,DATABASE=config['sites'][0]['database'],
        WORKSPACE=json.loads((local/'fixtures.json').read_text())['workspaces']['C']['public_id'],
        GRANT_WORKSPACE=json.loads((local/'fixtures.json').read_text())['workspaces']['A']['public_id'],
        OPERATION=str(uuid4()),STAMP=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    code+='globals().update(json.loads('+repr(json.dumps(values))+'))\n'
    code+='c=configparser.ConfigParser();c.read("/run/secrets/odoo_config");o=c["options"];assert o["db_name"]==DATABASE\n'
    code+='CONNECTION=psycopg2.connect(host=o["db_host"],port=o["db_port"],user=o["db_user"],password=o["db_password"],dbname=DATABASE,connect_timeout=10)\n'
    retained=ROOT/'docs/evidence/G6/20261101-external-metadata-01/native_tests.py'
    helpers=retained.read_text();code+=helpers[helpers.index('TABLES='):helpers.index('class ExternalMetadataTests')]+'\n'
    code+='try:\n exec(compile('+repr((OUT/'native_tests.py').read_text())+',"native_feature_sql_tests","exec"),globals())\nfinally:\n CONNECTION.rollback();CONNECTION.close()\n'
    marker.write_text(json.dumps(dict(state='running',label=label))+'\n')
    with (local/'logs'/(label+'.stdout')).open('xb') as stdout,(local/'logs'/(label+'.stderr')).open('xb') as stderr:
        process=subprocess.run(['docker','exec','-i',observer._container('app'),'/venv/bin/python','-'],input=code.encode(),stdout=stdout,stderr=stderr,timeout=120)
    records=[json.loads(l.split('=',1)[1]) for l in (local/'logs'/(label+'.stdout')).read_text().splitlines() if l.startswith('MP_NATIVE_FEATURE=')]
    if len(records)!=1:raise RuntimeError('Inspect private logs/process; missing exact result')
    result=records[0];assert result['successful']==(process.returncode==0)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items())
    report=dict(utc=datetime.now(timezone.utc).isoformat(),attempt=attempt,result='passed' if result['successful'] else 'failed',**result,
        sources={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},image=state['image_id'],inventory=state['inventory_digest'],
        installed=False,actual_lifecycle=False,new_docker_assets=0,acceptance_credit=False,
        limits=['Candidate modules in isolated existing-container process; every fixture transaction rolls back, sequences may advance.',
            'SQL gates are real; no coordinated backup/worker replacement/journal/readiness/recovery operation is performed.'])
    (OUT/('attempt-'+attempt+'.json')).write_text(json.dumps(report,indent=2)+'\n');marker.write_text(json.dumps(dict(state='completed',**report),indent=2)+'\n')
    if result['successful']:(OUT/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['result','tests','errors','failures']}));raise SystemExit(not result['successful'])

if __name__=='__main__':main()
