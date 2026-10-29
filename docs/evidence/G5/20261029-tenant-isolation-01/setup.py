"""Create two owned DB copies on a new server, preserving all source targets."""
import configparser
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-tenant';LIFE=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import protect_directory
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
import r0

SEED="""import json,os,pathlib,shutil,sys
d=json.load(sys.stdin);root=pathlib.Path('/target');assert not (root/'config').exists() and not (root/'data').exists()
(root/'config').mkdir();(root/'data').mkdir();(root/'config/odoo_config').write_text(d['config']);(root/'config/odoo_config').chmod(0o444)
source=pathlib.Path('/source/filestore')/d['source_database'];dest=root/'data/filestore'/d['database'];dest.parent.mkdir();shutil.copytree(source,dest)
for p in [root/'data',*(root/'data').rglob('*')]:os.chown(p,10001,10001)
"""


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));assert not LOCAL.exists();protect_directory(LOCAL);(OUTPUT/'setup').mkdir()
    life=load(LIFE/'operator/target.json');assert life['generation']==18 and life['project']=='mp-r0-r1lifef99acae9d906'
    matrix=load(LIFE/'worker-fence-matrix.json');assert matrix['state']=='completed_verified'
    removed=matrix['databases']['removed'];reader=DockerObserver(life);source_db=reader._container('db')
    token=uuid4().hex[:12];project='mp-r0-r1ten'+token;image=life['image_id'];pin=life['published_release']['core_inventory_digest']
    state=dict(disposable=True,project=project,image_id=image,inventory_digest=pin,phase='creating',evidence=(OUTPUT/'setup').relative_to(ROOT).as_posix(),variant='v1',active_db='mp_disposable_r0_r1_ten_'+token+'_a',databases=[],cases={},containers=[],source_configuration_sha256=hashlib.sha256((LIFE/'operator/target.json').read_bytes()).hexdigest())
    def save(phase):state.update(phase=phase,utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    def command(args,*,input=None,timeout=180):
        r=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
        if r.returncode:
            (LOCAL/'setup.stderr').write_bytes(r.stderr);raise RuntimeError('Inspect exact setup state/owned resources; never recreate or reset')
        return r.stdout
    save('creating')
    for name in ['postgres-password','app-db-password','bootstrap-password','database-master-password']:(LOCAL/name).write_text(secrets.token_urlsafe(32)+'\n',encoding='utf8')
    (LOCAL/'copied-human-password').write_bytes((LIFE/'bootstrap-password').read_bytes())
    original=command(['docker','exec',life['worker_id'],'/venv/bin/python','-c',"from pathlib import Path;print(Path('/run/secrets/odoo_config').read_text(),end='')"])
    cfg=configparser.ConfigParser();cfg.read_string(original.decode());cfg['options'].update(db_name=state['active_db'],dbfilter='^'+state['active_db']+'$',db_password=(LOCAL/'app-db-password').read_text(encoding='utf8').strip(),admin_passwd=(LOCAL/'database-master-password').read_text(encoding='utf8').strip(),workers='0',max_cron_threads='0')
    with (LOCAL/'odoo.conf').open('x',encoding='utf8') as f:cfg.write(f)
    (LOCAL/'compose.env').write_text('MP_COMPOSE_PROJECT='+project+'\nMP_HTTP_PORT=18082\nMP_IMAGE='+image+'\n',encoding='utf8')
    r0.LOCAL=LOCAL;r0.STATE=LOCAL/'state.json';r0.seed_volumes(state)
    compose=['docker','compose','--env-file',str(LOCAL/'compose.env'),'-f',str(ROOT/'deploy/compose.yaml')]
    save('starting_owned_server');command(compose+['up','-d','--wait','db']);db=command(compose+['ps','-q','db']).decode().strip();state['db_container']=db
    assert load_docker_network(project+'_runtime')['Internal']
    fixture=load(LIFE/'fixtures.json');workspace=fixture['workspaces']['A']['id']
    row=json.loads(sql(reader,"SELECT to_jsonb(t) FROM (SELECT id,public_id,revision FROM mp_example_note WHERE workspace_id="+str(workspace)+" ORDER BY id LIMIT 1) t;"));state['note']=row
    for case,source,source_volume in [('a',life['sites'][0]['database'],life['project']+'_filestore'),('b',removed['database'],removed['volume'])]:
        database='mp_disposable_r0_r1_ten_'+token+'_'+case;volume=project+'_probe_'+case;site=str(uuid4());source_config=dict(life,sites=[dict(life['sites'][0],database=source)]);source_reader=DockerObserver(source_config)
        state['cases'][case]=dict(database=database,volume=volume,site_id=site,source_database=source,source_volume=source_volume,labels_installed=case=='a');state['databases'].append(database);save('copying_'+case)
        before=dict(business=json.loads(sql(source_reader,BUSINESS_SQL)),schema=json.loads(sql(source_reader,SCHEMA)))
        (OUTPUT/'setup'/('source-'+case+'.json')).write_text(json.dumps(before,indent=2)+'\n',encoding='utf8')
        archive=command(['docker','exec',source_db,'pg_dump','-U','postgres','--no-owner','-Fc',source]);(LOCAL/('source-'+case+'.dump')).write_bytes(archive)
        command(['docker','exec',db,'createdb','-U','postgres','-T','template0','-O','modular',database]);command(['docker','exec','-i',db,'pg_restore','-U','postgres','--no-owner','--role=modular','--exit-on-error','-d',database],input=archive)
        # Explicit test-copy identity/sentinel/credential changes only. Stable
        # record/workspace/actor IDs deliberately collide across the two DBs.
        statement="BEGIN; UPDATE ir_config_parameter SET value='"+site+"' WHERE key='mp.site_id'; UPDATE ir_config_parameter SET value='"+str(uuid4())+"' WHERE key='mp.deployment_id'; UPDATE ir_config_parameter SET value='"+secrets.token_hex(32)+"' WHERE key='database.secret'; UPDATE mp_service_binding SET descriptor=jsonb_set(descriptor,'{site_id}',to_jsonb('"+site+"'::text)); UPDATE mp_service_credential SET state='revoked'; UPDATE mp_example_note SET title='TEN_"+case.upper()+"_VISIBLE' WHERE id="+str(row['id'])+"; COMMIT;"
        command(['docker','exec','-i',db,'psql','-X','-q','-U','postgres','-v','ON_ERROR_STOP=1','-d',database],input=statement.encode())
        import io
        cfg['options'].update(db_name=database,dbfilter='^'+database+'$');stream=io.StringIO();cfg.write(stream)
        command(['docker','volume','create','--label','com.modular.qualification=G5-tenant-isolation',volume])
        source_path=source if case=='a' else removed['database']
        source_mount='type=volume,source='+source_volume+',target=/source,readonly'+(',volume-subpath=data' if case=='b' else '')
        command(['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--mount',source_mount,'--mount','type=volume,source='+volume+',target=/target','--entrypoint','/venv/bin/python',image,'-c',SEED],input=json.dumps(dict(config=stream.getvalue(),source_database=source_path,database=database)).encode())
        fixture_case=json.loads(json.dumps(fixture));fixture_case.update(database=database,site_id=site)
        for binding in fixture_case['bindings'].values():binding['site_id']=site
        (LOCAL/('fixtures-'+case+'.json')).write_text(json.dumps(fixture_case,indent=2)+'\n',encoding='utf8')
        own=DockerObserver(dict(life,project=project,sites=[dict(database=database,site_id=site)]));business=json.loads(sql(own,BUSINESS_SQL));schema=json.loads(sql(own,SCHEMA))
        assert schema==before['schema'];assert any(c[1]=='x_notes_labels' for c in schema['columns'])==(case=='a')
        assert json.loads(sql(source_reader,BUSINESS_SQL))==before['business'] and json.loads(sql(source_reader,SCHEMA))==before['schema']
        for name,value in [('business',business),('schema',schema)]: (OUTPUT/'setup'/(case+'-'+name+'.json')).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    assert hashlib.sha256((LIFE/'operator/target.json').read_bytes()).hexdigest()==state['source_configuration_sha256']
    save('copies_verified');report=dict(result='passed',project=project,image_id=image,inventory_digest=pin,cases=state['cases'],record_id=state['note'],source_targets_unchanged=True,no_public_ports=True,private_credentials_rotated=True,limits=['Qualification copies, not deployment of a multi-site product.','Owned test copies have new site/deployment IDs and title sentinels; all actor/workspace/object IDs intentionally collide.'])
    (OUTPUT/'setup/qualification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',project=project,databases=state['databases'])))


def load_docker_network(name):return json.loads(subprocess.check_output(['docker','network','inspect',name]))[0]


if __name__=='__main__':main()
