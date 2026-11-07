"""Record BX-03 proof and retire its one inventoried disposable realm."""
import json
import sqlite3

from background_retire import retire_site,rows
from background_site import ROOT,load,write
from background_workers import docker
from modular_platform.plans import data_digest


def main():
    local=ROOT/'.local/background-qualification/bx-03-recurrence-01'
    record=load(local/'bx03-recovery.json')
    assert record['phase']=='passed' and 'profile_adoption' in record
    evidence=ROOT/'docs/evidence/post-r1/background-execution/bx-03-recovery.json'
    assert not evidence.exists()
    public=dict(gate='BX-03',state='native_recovery_passed',operation=record['operation'],
        procedure='tests/background_recurrence_recovery.py: prepare, fault, guard, restore, resume, repair, adopt',
        original_image=record['original_target']['image_id'],failed_image=record['candidate'],
        original_database=record['original_target']['sites'][0]['database'],
        restored_database=record['restored_target']['sites'][0]['database'],
        checkpoint_tables=record['checkpoint']['tables'],
        history_guard=record['history_guard'],no_target_after_refusal=record['no_fresh_target_after_refusal'],
        receipts_before=len(record['before']['receipts']),receipts_after=len(record['final']['receipts']),
        original_receipts_digest=data_digest(record['before']['receipts']),
        restored_receipts_digest=data_digest(record['restored']['receipts']),
        preserved=['nominal receipt identity','cursor','considered high-water mark','configuration revision','outstanding job ID'],
        restored_dispatch_closed=True,technical_credentials_revoked=True,held_outstanding_job=True,
        separate_resume=True,repair=record['repair'],profile_adoption=record['profile_adoption'],
        restore_decision_digest=record['restore_digest'],resume_decision_digest=record['resume_digest'],
        limits=['Coordinated checkpoint only; changed post-checkpoint history requires independent reconciliation.',
            'No remote-effect recovery or calendar recurrence claim; fixed UTC native profile only.'])
    write(evidence,public)
    retirement=ROOT/'docs/evidence/post-r1/background-execution/bx-03-retirement.json'
    assert not retirement.exists()
    with sqlite3.connect((local/'operator/control/control.sqlite3').as_uri()+'?mode=ro',uri=True) as con:
        operations={row[0] for row in con.execute('SELECT operation_id FROM operations')}
    builds=[load(ROOT/'docs/evidence/G7'/name/'candidate-build.json') for name in
        ('bx03-recurrence-orm-fix-build-01','bx03-recurrence-recovery-build-01')]
    known={row['tag'] for row in builds}|{'modular-platform:retained-'+operation for operation in operations}
    result=dict(site=retire_site('bx-03-recurrence-01'),images=[])
    for build in builds:
        image=build['image_id']
        assert not docker('ps','-aq','--filter','ancestor='+image).strip()
        observed,=rows('image','inspect',image)
        tags=set(observed['RepoTags']);assert tags and tags<=known,tags-known
        docker('image','rm',*sorted(tags))
        result['images'].append(dict(image=image,tags=sorted(tags)))
    write(retirement,result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
