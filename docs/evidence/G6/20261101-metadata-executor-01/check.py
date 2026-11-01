"""Real OS journal through the shared executor; Docker/SQL effects substituted."""
import hashlib,json,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
from uuid import UUID,uuid5
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular import configuration
from reference_package import assemble

def main():
    attempt=sys.argv[1] if len(sys.argv)>1 else '01'
    if not attempt.isdigit():raise ValueError('Numeric source attempt required')
    local=ROOT/'.local/g6-events';label='metadata-executor-loop-'+attempt
    marker=local/(label+'.json')
    if marker.exists():raise RuntimeError('Inspect original source attempt; never replay it')
    state=json.loads((local/'state.json').read_text());target_path=local/'operator/target.json';config=json.loads(target_path.read_text())
    protected={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in state['protected_configurations']}
    assert protected==state['protected_configurations']
    own_hash=hashlib.sha256(target_path.read_bytes()).hexdigest()
    observer=DockerObserver(config);observation=observer.read()
    assert observation['image_id']==state['image_id'] and observation['runtime']['inventory_digest']==state['inventory_digest']
    catalog=Catalog(local/'operator/catalog',configuration(local/'operator/trust.json'),readonly=True).snapshot()
    _,raw,_=assemble(ROOT,'plugins/document_stats/plugin.toml')
    with tempfile.TemporaryDirectory(prefix='mp-metadata-source-') as folder:
        path=Path(folder)/'source.mplug';path.write_bytes(raw)
        value=ArtifactValidator(TrustPolicy('development',allow_unsigned_development=True)).verify(path)
        descriptor=dict(manifest=value.manifest,digest=value.digest,inventory=value.inventory,trust=value.trust)
    catalog.append(descriptor)
    fixtures=json.loads((local/'fixtures.json').read_text());workspace=fixtures['workspaces']['C']['public_id']
    install=str(uuid5(UUID(config['sites'][0]['site_id']),'plugin:org.example.document_stats'))
    endpoint=json.loads((ROOT/'packages/contracts/examples/v1/endpoint.json').read_text())
    endpoint.update(site_id=config['sites'][0]['site_id'],workspace_id=workspace,installation_id=install,
        expected_image_digest=descriptor['manifest']['external_service']['expected_image'].split('@')[1])
    external=dict(endpoints=[endpoint],service_health={install+':'+workspace:dict(state='healthy',expected_image_digest=endpoint['expected_image_digest'])})
    target=dict(installation_id=install,site_id=endpoint['site_id'],workspace_id=workspace,plugin_id='org.example.document_stats')
    values=dict(CONFIG=config,RUNTIME=observation['runtime'],CATALOG=catalog,EXTERNAL=external,TARGET=target,DATABASE=config['sites'][0]['database'])
    qualified=(OUT.parent/'20261101-external-metadata-01/native_tests.py').read_text(encoding='utf8')
    assert '\nresult=unittest.' in qualified
    values['SOURCE_HELPERS']=qualified.split('\nresult=unittest.',1)[0]
    values['PUBLICATION_HELPERS']=(ROOT/'tests/test_worker_publication.py').read_text(encoding='utf8')
    sources={name:(ROOT/'packages/platform_sdk/modular_platform'/f'{name}.py').read_text(encoding='utf8') for name in
        ['plans','projection','planning_cli','deployment','operator_store','worker_operator','dispatch_lifecycle','dispatch_operator',
         'reference_dispatch','external_planning','external_metadata','native_executor','metadata_executor']}
    script='import configparser,json,types,sys,psycopg2\nsources='+repr(sources)+'\n'
    script+='for name,source in sources.items():\n ident="modular_platform."+name\n module=types.ModuleType(ident);module.__package__="modular_platform";module.__file__="/opt/modular/packages/platform_sdk/modular_platform/"+name+".py";sys.modules[ident]=module\n exec(compile(source,module.__file__,"exec"),module.__dict__)\n'
    script+='values=json.loads('+repr(json.dumps(values))+');globals().update(values)\n'
    script+='c=configparser.ConfigParser();c.read("/run/secrets/odoo_config");o=c["options"];assert o["db_name"]==DATABASE\n'
    script+='CONNECTION=psycopg2.connect(host=o["db_host"],port=o["db_port"],user=o["db_user"],password=o["db_password"],dbname=DATABASE,connect_timeout=10)\n'
    script+='from modular_platform.external_metadata import apply_external_metadata as APPLY\n'
    script+='try:\n exec(compile('+repr((OUT/'native_tests.py').read_text(encoding='utf8'))+',"metadata_rollback_tests","exec"),globals())\nfinally:\n CONNECTION.rollback();CONNECTION.close()\n'
    marker.write_text(json.dumps(dict(state='running',label=label))+'\n')
    app=observer._container('app');stdout=local/'logs'/(label+'.stdout');stderr=local/'logs'/(label+'.stderr')
    if stdout.exists() or stderr.exists():raise RuntimeError('Private test logs already exist')
    with stdout.open('xb') as out,stderr.open('xb') as err:
        process=subprocess.run(['docker','exec','-i',app,'/venv/bin/python','-'],input=script.encode(),stdout=out,stderr=err,timeout=120)
    records=[json.loads(line.split('=',1)[1]) for line in stdout.read_text(encoding='utf8').splitlines() if line.startswith('MP_METADATA_EXECUTOR=')]
    if len(records)!=1:raise RuntimeError('Inspect exact process/private output; source attempt is not qualified')
    result=records[0];assert result['successful']==(process.returncode==0)
    assert hashlib.sha256(target_path.read_bytes()).hexdigest()==own_hash
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in protected.items())
    report=dict(result='source_transactions_passed' if result['successful'] else 'source_transactions_failed',
        utc=datetime.now(timezone.utc).isoformat(),attempt=attempt,**result,image=state['image_id'],inventory=state['inventory_digest'],
        sources={name:hashlib.sha256(text.encode()).hexdigest() for name,text in sources.items()},
        no_new_docker_assets=True,no_committed_test_rows=True,actual_metadata_operation=False,
        limits=['Candidate source loaded in an isolated existing-container process, not installed code.',
            'Endpoint/health are explicit synthetic source-test data, not actual OS approval or a running worker.',
            'All test transactions roll back; PostgreSQL sequence counters may advance.',
            'Temporary real OS store/locks exercise the shared executor with substituted Docker/native validation/SQL effects; checkpoint IDs are fixtures, not real backups.',
            'No integrated approved operation, runtime control, actual checkpoint/restore or complete SVC acceptance is claimed.'])
    name='attempt-'+attempt+'.json';(OUT/name).write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    marker.write_text(json.dumps(dict(state='completed',**report),indent=2)+'\n',encoding='utf8')
    if result['successful']:(OUT/'qualification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report));raise SystemExit(0 if result['successful'] else 1)

if __name__=='__main__':main()
