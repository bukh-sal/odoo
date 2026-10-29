"""Read-only discrimination: guard versus real post-native/pre-metadata states."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql

PROBE="""import configparser,hashlib,json,pathlib,runpy,sys
import psycopg2
config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');options=config['options']
options['db_name']=sys.argv[1]
root=pathlib.Path('/opt/modular');raw=(root/'distribution-inventory.json').read_bytes();inventory=json.loads(raw);pin='sha256:'+hashlib.sha256(raw).hexdigest()
guard=root/'packages/platform_sdk/modular_platform/worker_start.py';assert hashlib.sha256(guard.read_bytes()).hexdigest()==inventory['files']['packages/platform_sdk/modular_platform/worker_start.py']
connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],password=options['db_password'],dbname=options['db_name'],connect_timeout=10)
connection.set_session(readonly=True,autocommit=True)
with connection.cursor() as cursor:
 cursor.execute('SHOW transaction_read_only');assert cursor.fetchone()==('on',)
 cursor.execute("SELECT i.plugin_id,i.state,m.state,m.latest_version FROM mp_plugin_installation i LEFT JOIN ir_module_module m ON m.name=i.manifest->'runtime'->>'addon_name' WHERE i.plugin_id='org.example.notes_labels'");labels=cursor.fetchall()
 cursor.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='mp_example_note' AND column_name='x_notes_labels'");field=cursor.fetchone()[0]==1
bootstrap=runpy.run_path(str(guard),run_name='read_only_guard_qualification')
try:
 bootstrap['validate'](root,options,connection,sys.argv[1],pin)
 result=dict(result='accepted')
except ValueError as error:result=dict(result='rejected',reason=str(error))
finally:connection.close()
assert 'odoo' not in sys.modules
print(json.dumps(dict(result,database=sys.argv[1],inventory_digest=pin,labels=labels,labels_field_present=field,transaction_read_only=True,native_code_imported=False,native_entrypoint_invoked=False)))
"""


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'read-only-baseline.json';assert not dest.exists()
    config=load(LOCAL/'operator/target.json');assert config['generation']==17 and config['project']=='mp-r0-r1lifef99acae9d906'
    databases=[config['sites'][0]['database'],'mp_disposable_r0_r1_g5_life_f99acae9d906','mp_disposable_r0_r1_restore_c515909c969c4f9a8e76d475ffd0df46']
    reports=[]
    for database in databases:
        target=dict(config,sites=[dict(config['sites'][0],database=database)]);reader=DockerObserver(target)
        business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA))
        r=subprocess.run(['docker','exec','-i',config['worker_id'],'/venv/bin/python','-c',PROBE,database],capture_output=True,timeout=90)
        if r.returncode:
            (LOCAL/'worker-fence-observe.stderr').write_bytes(r.stderr);raise RuntimeError('Read-only guard probe failed; inspect private diagnostics')
        value=json.loads(r.stdout);assert json.loads(sql(reader,BUSINESS_SQL))==business and json.loads(sql(reader,SCHEMA))==schema
        value.update(business_sha256=hashlib.sha256(json.dumps(business,sort_keys=True).encode()).hexdigest(),schema_sha256=hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest(),business_schema_unchanged=True);reports.append(value)
    workers=[]
    raw=subprocess.check_output(['docker','ps','--all','-q','--filter','label=com.docker.compose.project='+config['project'],'--filter','label=com.docker.compose.service=app'])
    for ident in raw.decode().split():
        item=json.loads(subprocess.check_output(['docker','inspect',ident]))[0]
        workers.append(dict(container_id=item['Id'],image_id=item['Image'],running=item['State']['Running'],networks=sorted(item['NetworkSettings']['Networks']),current=item['Id']==config['worker_id']))
    assert sum(w['running'] for w in workers)==1 and all(not w['running'] and not w['networks'] for w in workers if not w['current'])
    dest.write_text(json.dumps(dict(result='observed',utc=datetime.now(timezone.utc).isoformat(),guard_cases=reports,managed_workers=workers,configuration_unchanged=load(LOCAL/'operator/target.json')==config),indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(result='observed',guard_cases=reports)))


if __name__=='__main__':main()
