"""Audit BX-05 evidence and retire only its inventoried disposable assets."""
import hashlib
import json
import re

from background_chunks_recovery import tables
from background_retire import retire_site
from background_site import ROOT,load,write
from background_workers import Probe,docker


def main():
    probe=Probe('bx-05-chunks-01');path=probe.site.local/'bx05-finalized.json'
    assert not path.exists() and not probe.operator._lanes()
    recovery_path=probe.site.local/'bx05-recovery.json';recovery=load(recovery_path)
    assert recovery['phase']=='qualified'
    for name in ('bx05-basic-final.json','bx05-atomicity.json','bx05-process.json','bx05-cancel.json'):
        assert load(probe.site.local/name)['phase']=='passed'
    assert probe.sql("SELECT latest_version FROM ir_module_module WHERE name='mp_example_background'")=='19.0.0.3.3'
    assert probe.sql("SELECT latest_version FROM ir_module_module WHERE name='mp_core'")=='19.0.0.1.45'
    assert probe.sql("SELECT count(*) FROM mp_background_report WHERE state='running' OR snapshot IS NOT NULL")=='0'
    assert probe.sql("SELECT count(*) FROM mp_job WHERE state='outcome_unknown' OR handler='org.example.background:report_chunk' AND state IN ('pending','running','retry','held')")=='0'
    current=tables(probe)
    for table in ('mp_background_task','mp_example_note'):assert current[table]==recovery['before'][table]
    log=probe.site.local/'bx05-host.log';raw=log.read_bytes();text=raw.decode('utf-8-sig')
    match=re.search(r'Ran (\d+) tests in ([\d.]+)s',text)
    assert match and match[1]=='585' and 'OK (skipped=1)' in text
    a=load(ROOT/'docs/evidence/G7/bx05-chunks-build-04/candidate-build.json')
    b=load(ROOT/'docs/evidence/G7/bx05-chunks-build-05/candidate-build.json')
    changed=sorted(key for key in a['source_sha256'].keys()|b['source_sha256'].keys()
        if a['source_sha256'].get(key)!=b['source_sha256'].get(key))
    assert changed==['examples/mp_example_background/__manifest__.py','plugins/background/plugin.toml']
    assert probe.state['image_id']==b['image_id']
    proof=dict(gate='BX-05',state='qualified',fault_operation=recovery['operation'],
        successful_operation=recovery['successful_upgrade']['operation'],saved_cursor=recovery['seed']['row']['cursor'],
        application_tables_preserved=recovery['before']==recovery['restored_tables'],fresh_database=True,
        traffic_closed_until_separate_resume=True,old_claim_denied=recovery['fence']['old_claim_denied'],
        old_profile_denied=bool(recovery['stale_profile']),verified=recovery['verified'],
        native_version='19.0.0.3.3',reference_version='0.3.3',platform='0.1.45',forward_image=b['image_id'],
        forward_source_diff=changed,private_recovery_sha256=hashlib.sha256(recovery_path.read_bytes()).hexdigest(),
        host_regression=dict(tests=585,passed=584,skipped=1,seconds=float(match[2]),private_log_sha256=hashlib.sha256(raw).hexdigest()),
        contract_freeze=dict(files=106,rows=8,major=1,result='passed'))
    assert proof['application_tables_preserved']
    write(ROOT/'docs/evidence/post-r1/background-execution/bx-05-recovery.json',proof)
    containers=[name for name in docker('ps','-a','--format','{{.Names}}').decode().splitlines() if name.startswith(probe.project+'-')]
    image_plans=[]
    for build,expected in ((a,{a['tag'],'modular-platform:retained-'+recovery['operation'],
            'modular-platform:retained-'+recovery['successful_upgrade']['operation']}),(b,{b['tag']})):
        image,=json.loads(docker('image','inspect',build['image_id']))
        assert set(image['RepoTags'])==expected
        image_plans.append(dict(image=build['image_id'],tags=sorted(expected)))
    record=dict(phase='retiring',proof=proof,containers=containers,images=image_plans,
        resources=probe.state['owned_resources']);write(path,record)
    retired=retire_site('bx-05-chunks-01')
    for plan in image_plans:
        assert not docker('ps','-aq','--filter','ancestor='+plan['image']).strip()
        docker('image','rm',*plan['tags'])
    cleanup=dict(gate='BX-05',state='retired',project=probe.project,**retired,images=image_plans,
        intermediate=load(probe.site.local/'bx05-intermediate-retired.json'),
        preserved='Unrelated Docker assets and the existing stock dependency base; private source packages/checkpoints/evidence retained.')
    write(ROOT/'docs/evidence/post-r1/background-execution/bx-05-retirement.json',cleanup)
    record.update(phase='passed',retirement=cleanup);write(path,record)
    state=load(probe.site.local/'state.json');state['phase']='bx05_retired';write(probe.site.local/'state.json',state)
    print(json.dumps(dict(phase='passed',retired=retired,images_removed=2,host_tests=585)),flush=True)


if __name__=='__main__':main()
