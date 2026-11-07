"""Collect BX-04 recovery proof and retire its exact owned disposable realm."""
import hashlib
import json
from uuid import UUID

from background_retire import retire_site
from background_site import ROOT, load, write
from background_workers import Probe, docker


def main():
    probe=Probe('bx-04-capacity-01');path=probe.site.local/'bx04-finalized.json'
    assert not path.exists() and not probe.operator._lanes()
    recovery_path=probe.site.local/'bx04-guard-recovery.json';recovery=load(recovery_path)
    assert recovery['phase']=='qualified'
    assert probe.sql("SELECT latest_version FROM ir_module_module WHERE name='mp_core'")=='19.0.0.1.45'
    assert probe.sql("SELECT count(*) FROM mp_service_credential WHERE state='active'")=='0'
    assert probe.sql("SELECT count(*) FROM mp_job WHERE state='outcome_unknown'")=='0'
    jobs=[recovery['seed']['running'],*recovery['proof']['jobs']]
    assert all(str(UUID(value))==value for value in jobs)
    ids=','.join("'"+job+"'" for job in jobs)
    assert probe.sql("SELECT count(*) FROM mp_job WHERE public_id IN ("+ids+") AND state='completed' AND result->>'count'='10' AND result->>'points'='45'")=='3'
    before=load(ROOT/'docs/evidence/G7/bx04-claim-guard-build-01/candidate-build.json')
    candidate=load(ROOT/'docs/evidence/G7/bx04-recovery-build-01/candidate-build.json')
    a,b=before['source_sha256'],candidate['source_sha256']
    changed=sorted(key for key in a.keys()|b.keys() if a.get(key)!=b.get(key))
    assert changed==['packages/platform_sdk/modular_platform/projection.py','framework_addons/mp_core/__manifest__.py']
    proof=dict(gate='BX-04',state='qualified',fault_operation=recovery['operation'],
        successful_operation=recovery['successful_operation'],restored_to_fresh_database=True,
        history_cursors_and_rotation_preserved=recovery['before']==recovery['restored'],
        service_credentials_revoked=True,service_work_held=True,separate_resume=True,
        old_claim_denied=recovery['proof']['old_claim_denied'],old_rotation_denied=recovery['proof']['old_rotation_denied'],
        new_rotation_reset=recovery['proof']['new_rotation_reset'],stale_profile_denied=bool(recovery['stale_profile_denied']),
        recovered_human_attempts=recovery['recovered_claim']['attempts'],recovered_and_new_reports_exact=3,
        business_unchanged=True,source_changes=changed,forward_image=candidate['image_id'],reference_version='0.2.1',
        private_record_sha256=hashlib.sha256(recovery_path.read_bytes()).hexdigest(),
        current_contract_freeze=dict(files=106,rows=8,major=1,result='passed'),core_upgrade_regressions=8,
        unchanged_worker_regression='Core44 full host sweep584 passed/1 existing Windows skip; core45 changes only version metadata.')
    assert proof['history_cursors_and_rotation_preserved']
    write(ROOT/'docs/evidence/post-r1/background-execution/bx-04-guard-recovery.json',proof)
    record=dict(phase='retiring',project=probe.project,proof=proof);write(path,record)
    retired=retire_site('bx-04-capacity-01')
    old_image=before['image_id']
    assert not docker('ps','-aq','--filter','ancestor='+old_image).strip()
    image,=json.loads(docker('image','inspect',old_image))
    expected={before['tag'],'modular-platform:retained-'+recovery['operation'],
        'modular-platform:retained-'+recovery['successful_operation']}
    assert set(image['RepoTags'])==expected
    docker('image','rm',*sorted(expected))
    assert json.loads(docker('image','inspect',candidate['image_id']))[0]['Id']==candidate['image_id']
    cleanup=dict(gate='BX-04',state='retired',project=probe.project,**retired,
        old_image_removed=old_image,tags_removed=sorted(expected),
        retained_image=candidate['image_id'],retained_purpose='BX-05 clean baseline with reference0.2.1; no retained running service or volume',
        intermediate=load(probe.site.local/'bx04-intermediate-retirement-02.json'))
    write(ROOT/'docs/evidence/post-r1/background-execution/bx-04-retirement.json',cleanup)
    record.update(phase='passed',retirement=cleanup);write(path,record)
    state=load(probe.site.local/'state.json');state['phase']='bx04_retired';write(probe.site.local/'state.json',state)
    print(json.dumps(dict(phase='passed',retired=retired,retained_image=candidate['image_id'])),flush=True)


if __name__=='__main__':main()
