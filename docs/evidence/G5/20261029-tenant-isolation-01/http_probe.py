"""Default immutable workers, one pinned DB each, no public ports/aliases.

Named http_probe to avoid shadowing the standard-library http package.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-tenant'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.workers import wait_ready
from modular_platform.deployment import DockerObserver
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');dest=OUTPUT/'http-qualification.json';resume=sys.argv[1:]==['--resume-a'];assert sys.argv[1:] in ([],['--resume-a']);assert state['phase']==('running_http_a' if resume else 'registry_isolation_verified') and not dest.exists();reports=[];cookie=None
    def save(phase):state.update(phase=phase,utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    for case in ['a','b']:
        row=state['cases'][case];other=state['cases']['b' if case=='a' else 'a'];fixture=load(LOCAL/('fixtures-'+case+'.json'));name=state['project']+'-http-'+case
        args=['docker','create','--name',name,'--label','com.modular.qualification=G5-tenant-isolation','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',state['project']+'_runtime','--memory','768m','--pids-limit','128','--tmpfs','/tmp','--mount','type=volume,source='+row['volume']+',target=/run/secrets,volume-subpath=config,readonly','--mount','type=volume,source='+row['volume']+',target=/var/lib/modular,volume-subpath=data','-e','MP_EXPECTED_DATABASE='+row['database'],'-e','MP_EXPECTED_INVENTORY_DIGEST='+state['inventory_digest'],state['image_id']]
        if resume and case=='a':
            cid=next(r['container_id'] for r in state['containers'] if r['purpose']=='http-a');item=json.loads(subprocess.check_output(['docker','inspect',cid]))[0];assert item['State']['Running'] and item['Image']==state['image_id']
        else:
            cid=subprocess.check_output(args,timeout=30).decode().strip();state['containers'].append(dict(purpose='http-'+case,container_id=cid));save('running_http_'+case);subprocess.run(['docker','start',cid],capture_output=True,check=True,timeout=30)
        wait_ready(cid)
        data=dict(case=case,other_case='b' if case=='a' else 'a',database=row['database'],other_database=other['database'],site_id=row['site_id'],login=fixture['users']['alice']['login'],uid=fixture['users']['alice']['id'],workspace=fixture['workspaces']['A']['public_id'],password=(LOCAL/'copied-human-password').read_text(encoding='utf8').strip(),foreign_cookie=cookie)
        source=(OUTPUT/'http_inside.py').read_text(encoding='utf8');r=subprocess.run(['docker','exec','-i',cid,'/venv/bin/python','-c',source],input=json.dumps(data).encode(),capture_output=True,timeout=120)
        (LOCAL/('http-'+case+'.stderr')).write_bytes(r.stderr);(LOCAL/('http-'+case+'.stdout')).write_bytes(r.stdout)
        if r.returncode:raise RuntimeError('HTTP probe failed; inspect current worker/private diagnostics before continuation')
        report=json.loads(r.stdout);assert report['result']=='passed';cookie=subprocess.check_output(['docker','exec',cid,'/venv/bin/python','-c',"from pathlib import Path;print(Path('/tmp/ten-session-cookie').read_text(),end='')"],timeout=15).decode()
        subprocess.run(['docker','stop','--time','20',cid],check=True,capture_output=True,timeout=30);subprocess.run(['docker','network','disconnect',state['project']+'_runtime',cid],check=True,capture_output=True,timeout=30)
        item=json.loads(subprocess.check_output(['docker','inspect',cid]))[0];assert not item['State']['Running'] and not item['NetworkSettings']['Networks'] and not item['HostConfig']['PortBindings']
        assert item['Config']['Entrypoint']==['/venv/bin/python','/opt/modular/tools/start_worker.py']
        report.update(container_id=cid,source_sha256=hashlib.sha256(source.encode()).hexdigest(),default_guarded_entrypoint=True,retained_stopped_disconnected=True);reports.append(report)
        (OUTPUT/('http-'+case+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    life=load(ROOT/'.local/g5-lifecycle/operator/target.json')
    for case,row in state['cases'].items():
        reader=DockerObserver(dict(life,project=state['project'],sites=[dict(database=row['database'],site_id=row['site_id'])]))
        assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'setup'/(case+'-business.json')) and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'setup'/(case+'-schema.json'))
    save('HTTP_isolation_verified');dest.write_text(json.dumps(dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),cases=reports,business_schema_exact=True,limits=['Internal HTTP against default fixed-site workers; no public tenant selector or multi-site deployment feature.','Copied logical actor/workspace/object IDs intentionally collide; each copied site identity and session secret differs.']),indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',default_workers=2,cross_cookie_rejected=True)))


if __name__=='__main__':main()
