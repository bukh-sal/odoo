"""Run both import orders in isolated owned actual-Odoo qualification processes."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-tenant'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');dest=OUTPUT/'registry-qualification.json';assert state['phase']=='copies_verified' and not dest.exists()
    assert state['disposable'] and state['project'].startswith('mp-r0-r1ten');fixture=load(LOCAL/'fixtures-a.json');life=load(ROOT/'.local/g5-lifecycle/operator/target.json');reports=[]
    data=dict(order=[],cases=state['cases'],inventory_digest=state['inventory_digest'],note=state['note'],uid=fixture['users']['alice']['id'],workspace=fixture['workspaces']['A']['public_id'],notes_installation=fixture['bindings']['A']['consumer_installation_id'])
    def save(phase):state.update(phase=phase,utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    for order in [['a','b'],['b','a']]:
        label=''.join(order);name=state['project']+'-registry-'+label+'-orm-flush';data['order']=order;source=(OUTPUT/'inside.py').read_bytes();payload=json.dumps(data)
        args=['docker','create','-i','--name',name,'--label','com.modular.qualification=G5-tenant-isolation','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',state['project']+'_runtime','--memory','1024m','--pids-limit','128','--tmpfs','/tmp','--mount','type=volume,source='+state['cases']['a']['volume']+',target=/var/lib/modular,volume-subpath=data']
        for case in ['a','b']:args+=['--mount','type=volume,source='+state['cases'][case]['volume']+',target=/cases/'+case+',readonly']
        args+=['--entrypoint','/venv/bin/python',state['image_id'],'-c','import sys;exec(compile(sys.stdin.buffer.read(),"tenant-isolation-inside.py","exec"))',payload]
        created=subprocess.run(args,capture_output=True,check=True,timeout=30);cid=created.stdout.decode().strip();state['containers'].append(dict(purpose='registry-'+label,container_id=cid));save('running_registry_'+label)
        run=subprocess.run(['docker','start','-a','-i',cid],input=source,capture_output=True,timeout=180)
        (LOCAL/('registry-'+label+'.stdout')).write_bytes(run.stdout);(LOCAL/('registry-'+label+'.stderr')).write_bytes(run.stderr)
        current=json.loads(subprocess.check_output(['docker','inspect',cid]))[0];assert not current['State']['Running']
        subprocess.run(['docker','network','disconnect',state['project']+'_runtime',cid],check=True,capture_output=True,timeout=30)
        assert run.returncode==0 and current['State']['ExitCode']==0,'Read private registry diagnostics; no reset/retry'
        values=[json.loads(line.split(b'MP_TEN_RESULT=',1)[1]) for line in run.stdout.splitlines() if line.startswith(b'MP_TEN_RESULT=')];assert len(values)==1 and values[0]['result']=='passed'
        report=dict(values[0],container_id=cid,inside_source_sha256=hashlib.sha256(source).hexdigest(),retained_stopped_disconnected=True,no_public_port=True)
        (OUTPUT/('registry-'+label+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');reports.append(report)
    for case in ['a','b']:
        row=state['cases'][case];reader=DockerObserver(dict(life,project=state['project'],sites=[dict(database=row['database'],site_id=row['site_id'])]))
        assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'setup'/(case+'-business.json')) and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'setup'/(case+'-schema.json'))
    save('registry_isolation_verified');dest.write_text(json.dumps(dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),cases=reports,exact_business_schema_after_rollback=True,limits=['Actual two-registry process is an owned test harness; R1 web deployment remains fixed to one site by default.','Same-origin/native code remains trusted; these checks prove supported context/data separation, not native-plugin containment.']),indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',import_orders=2,concurrent_reads=64,business_schema_unchanged=True)))


if __name__=='__main__':main()
