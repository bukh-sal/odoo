"""Qualify real UI evidence and exact preservation; no G7/release claim."""
import hashlib,json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import lifecycle as d
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
ROOT,OUT,base,f,j=d.ROOT,d.OUT,d.base,d.f,d.j
state,native=d.context();assert not (OUT/'qualification.json').exists()
for number in range(1,6):
    process=f.load(j.LOCAL/f'headless-ui-0{number}/process.json')
    assert process['state']=='stopped' and process['exit']['code']==0
for number in [4,5]:
    directory=j.LOCAL/f'headless-ui-0{number}'
    assert f.load(directory/'node-phase.json')['state']=='complete'
    assert f.load(directory/'operator.json')['state']=='recovery_completed'
    result=f.load(directory/'lifecycle-result.json')
    assert result['exception_count']==0 and result['explicit_post_recovery_result_verified'] and result['native_list_usable_during_outage']
assert f.load(j.LOCAL/'headless-ui-04/lifecycle-result.json')['navigation_retirement_verified']
assert f.load(j.LOCAL/'headless-ui-04/lifecycle-result.json')['timeout_degraded_notification_verified']
assert f.load(j.LOCAL/'headless-ui-05/lifecycle-result.json')['crash_degraded_notification_verified']

before=f.load(j.LOCAL/'headless-ui-02/data-before.json');after=base.snapshot(state,'headless-final-preservation')
extra={'bd1f0a33-a8fb-452b-85d0-b077b0d1669b'}
for number in [4,5]:extra.update(f.load(j.LOCAL/f'headless-ui-0{number}/operator.json')['jobs'])
assert len(extra)==6 and len(after['mp_job'])==36
for table,rows in before.items():
    actual=[r for r in after[table] if r['public_id'] not in extra] if table=='mp_job' else after[table]
    assert actual==rows,table
assert all(r['state'] in ('completed','dead_letter','cancelled') for r in after['mp_job'])
new={r['public_id']:r for r in after['mp_job'] if r['public_id'] in extra}
first=new['bd1f0a33-a8fb-452b-85d0-b077b0d1669b'];assert first['state']=='dead_letter' and first['attempts']==0 and first['error_code']=='DEADLINE_EXCEEDED'
assert sum(r['state']=='completed' for r in new.values())==3 and sum(r['state']=='dead_letter' for r in new.values())==3
assert all(r['payload']['input']['expected_revision'] in (1,2) for r in new.values())
worker=base.worker(native,'headless-final-worker');assert worker==f.load(j.LOCAL/'headless-ui-05/worker-after.json')
original=f.load(j.LOCAL/'headless-ui-02/worker-before.json')
assert all(worker[k]==v for k,v in original.items() if k not in ('started_at','networks'))
for network,values in original['networks'].items():
    for key in ['NetworkID','IPAddress','GlobalIPv6Address']:assert worker['networks'][network][key]==values[key]
adapter=ReferenceDispatchMaintenance(native);dispatch=adapter.inspect()
assert dispatch['control']['generation']==117 and dispatch['control']['state']=='enabled'
assert adapter.policy_for(dispatch)['profile']=='r1-reference-stateless-v1'
assert all(dispatch.get(k)==0 for k in ['active_credentials','api_keys','uncertain_jobs'])
runtime=native.observer.read()['runtime'];assert runtime['inventory_digest']==state['inventory_digest']
source=f.load(OUT.parent/'20261102-notes-stats-ui-source-01/source-checks.json')
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source['source_sha256'].items())
backend=f.load(OUT.parent/'20261102-current-backend-audit-01/coverage.json')
for p,h in backend['source_sha256'].items():
    assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
    assert runtime['inventory']['files'][p.replace('platform_addons/','addons/',1)]==h

screens={'navigation-clean.png':4,'outage-degraded.png':4,'outage-native-list.png':4,'recovered-result.png':4,
         'crash-degraded.png':5,'crash-recovered-result.png':5}
for name,number in screens.items():
    assert not (OUT/name).exists();shutil.copyfile(j.LOCAL/f'headless-ui-0{number}'/name,OUT/name)
for number in [4,5]:
    name='timeout-UI.json' if number==4 else 'crash-UI.json';assert not (OUT/name).exists()
    shutil.copyfile(j.LOCAL/f'headless-ui-0{number}/lifecycle-result.json',OUT/name)
attempts=dict(result='diagnosed_test_fixture_and_readiness_observations',
    first_healthy_attempt='Wrong existing title selected. Actual UI queued one job. Browser closed; its original pending deadline expired. One guarded runner pass terminalized it with zero attempts/no remote effect.',
    correction='Read immutable Note IDs/titles from baseline. Corrected original Note displayed its real cached result; later fresh real jobs verified navigation, both outages and recovery.',
    timeout_recovery='Unpause completed once; immediate observer refused not-yet-healthy worker. Fresh Docker healthy heartbeat/source inspection discriminated readiness; separate attest reused same current image/key/config/publication without another unpause.',
    all_production_sources_unchanged=True,personal_browser_used=False)
f.save('attempts.json',attempts)
proofs=['healthy-result.json','timeout-UI.json','crash-UI.json','navigation-job.json','outage-job.json','recovery-job.json','crash-05-job.json','recovery-05-job.json','attempt01-runner.json']
records={p:hashlib.sha256((OUT/p).read_bytes()).hexdigest() for p in proofs}
records.update({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.png')})
f.save('qualification.json',dict(result='passed_SVC02_actual_native_UI_timeout_crash_navigation_and_recovery',utc=datetime.now(timezone.utc).isoformat(),
    acceptance=['SVC-02'],spec_sections=['14.6','22.4','22.5','23'],native_generation=24,dispatch_generation=117,
    image=state['image_id'],inventory=state['inventory_digest'],worker_container=worker['container_id'],worker_image=worker['image'],
    actual_headless_Edge_with_fresh_protected_profiles=True,personal_browser_used=False,all_five_owned_browsers_exited_zero=True,
    real_native_list_form_and_existing_slot_Odoo_notifications=True,cached_revision2_statistics50_7_1_visible=True,
    actual_post_navigation_computation_no_late_notice=True,actual_paused_worker_timeout_degraded_UI=True,
    actual_SIGKILL137_worker_crash_degraded_UI=True,native_Notes_list_usable_during_both_outages=True,
    explicit_post_recovery_real_results_visible=True,uncaught_UI_exceptions=0,
    original30job_outcomes_and_other16tables_all30Notes_exact=True,additional_UI_jobs=6,terminal_jobs=36,
    new_job_states=dict(completed=3,dead_letter=3),first_wrong_fixture_job_never_dispatched=True,
    current_worker_config9_key19_publication11_and_scope_exact=True,worker_start_timestamp_changed_only_for_explicit_crash_restart=True,
    no_new_images_volumes_or_plugin_features=True,source_sha256=source['source_sha256'],records=records,
    screenshots_visually_reviewed=True,
    limits=['Real browser DOM/events/native views and Odoo notifications; no function replacement or fake worker results.',
            'This proves G6 UI behavior, not UI09 keyboard/contrast/zoom/RTL or complete G7 qualification.',
            'UI cancellation retires polling/notifications; the already accepted read-only durable job may finish. No cancellation rollback claim.',
            'Cleanup and final G6 evidence audit must finish before gate-G6 is marked passed.']))
f.phase(state,'g6_UI_SVC02_verified_pending_gate_audit');f.guard(state)
print('SVC02 actual UI qualified: timeout+crash/native survival/navigation/recovery; old30jobs+other16tables exact,36terminaljobs,current worker healthy/pub11')
