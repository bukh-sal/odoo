"""Actual immutable-lock adoption and present-policy rejection, without DB writes."""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.artifacts import ArtifactError,ArtifactValidator,TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import protect_directory
from modular_platform.plans import check_bundle,data_digest
from modular_platform.planning_cli import prepare_document
from modular_platform.resolution import PlanningError
from modular import configuration
from qualify_staged_planning import invoke,write
from qualify_native_upgrade import sql


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    output=args.output.resolve();operator=ROOT/'.local/operator';target=operator/'targets/g5.json'
    marker=ROOT/'.local/g5/release-adoption.json';operation='86952188-580b-4de2-bab5-4ef536a29ce7'
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists() or marker.exists():raise ValueError('Fresh once-only adoption check required; reconcile any existing marker')
    config=json.loads(target.read_text());assert config['project']=='mp-r0-r1g5fd0445d406d6' and config['generation']==9 and 'published_release' not in config
    validator=configuration(operator/'trust.json');catalog=Catalog(operator/'catalog',validator,readonly=True)
    observer=DockerObserver(config);before=observer.read();old=observer.state(before,catalog.snapshot())['state']
    cache_sql="SELECT payload FROM mp_operation_profile;"
    cache_before=sql(observer,cache_sql);output.mkdir(parents=True)
    write(marker,{'state':'nominated','operation_id':operation,'evidence':str(output.relative_to(ROOT))})
    prefix=[sys.executable,'tools/modular.py','--config',str(operator/'trust.json')]
    command=prefix+['operations','--store',str(operator/'control'),'adopt-release',operation,'--deployment-config',str(target),'--catalog',str(operator/'catalog')]
    result=invoke(command);assert result['state']=='adopted' and not result['database_or_runtime_changed'];write(output/'adopted.json',result)
    adopted=json.loads(target.read_text());assert {key:value for key,value in adopted.items() if key!='published_release'}==config
    reader=DockerObserver(adopted);after=reader.read();assert after==before
    document=reader.state(after,catalog.snapshot());assert document['state']['release_digest']==old['release_digest']
    write(output/'state-pinned.json',document['state'])
    replay=invoke(command);assert replay['state']=='already_pinned';write(output/'adoption-replay.json',replay)
    # Revalidate actual immutable catalog bytes under a different LOCAL policy,
    # without replacing the live policy or refreshing an incompatible app cache.
    trust=json.loads((operator/'trust.json').read_text());new_policy=TrustPolicy(approved_digests=frozenset(trust['approved_digests']),generation=trust['generation']+1)
    revalidated=Catalog(operator/'catalog',ArtifactValidator(new_policy),readonly=True).snapshot()
    changed=reader.state(after,revalidated)['state']
    assert changed['release_digest']==document['state']['release_digest'] and changed['release_lock']==document['state']['release_lock']
    assert changed['catalog_validation_digest']!=document['state']['catalog_validation_digest']
    first=next(item for item in document['state']['installations'] if item['feature_state']=='enabled')
    request={name:first[name] for name in ('installation_id','site_id','workspace_id','plugin_id')}|{'action':'suspend'}
    document['request']={'operation_type':'suspend','requested':{},'targets':[request],
        'operation_id':str(uuid4()),'created_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    bundle=prepare_document(document,catalog.snapshot());check_bundle(bundle,document['state'])
    try:check_bundle(bundle,changed)
    except PlanningError as error:assert 'Stale plan' in str(error)
    else:raise AssertionError('Policy change did not invalidate pending plan')
    write(output/'pending-plan.json',bundle)
    probe=protect_directory(operator/'probes'/output.name);isolated=Catalog(probe/'catalog',ArtifactValidator(new_policy))
    for item in catalog.snapshot():isolated.add(catalog.path(item['digest']),expected_digest=item['digest'])
    selected=next(item['digest'] for item in adopted['published_release']['plugins'] if item['plugin_id']=='org.example.notes')
    isolated.quarantine(selected)
    try:reader.state(after,isolated.snapshot())
    except PlanningError as error:assert 'absent/untrusted' in str(error)
    else:raise AssertionError('Pinned release bypassed current quarantine')
    revoked=ArtifactValidator(TrustPolicy(approved_digests=new_policy.approved_digests-{selected},generation=new_policy.generation+1))
    try:Catalog(operator/'catalog',revoked,readonly=True).snapshot()
    except ArtifactError:pass
    else:raise AssertionError('Current revocation was bypassed')
    incompatible=subprocess.run([sys.executable,'tools/publish_profile.py','--target',str(target)],capture_output=True,timeout=90,cwd=ROOT)
    assert incompatible.returncode!=0 and b'preserve the old cache' in incompatible.stderr
    assert sql(reader,cache_sql)==cache_before
    completed=invoke(prefix+['plugin','apply',operation,'--store',str(operator/'control'),'--deployment-config',str(target),'--catalog',str(operator/'catalog')])
    assert completed['state']=='completed';write(output/'completed-operation-replay.json',{'unchanged_completed_operation':True})
    paths=list((ROOT/'packages/platform_sdk/modular_platform').glob('*.py'))+[Path(__file__),ROOT/'tools/modular.py',ROOT/'tools/publish_profile.py']
    write(output/'release-adoption.json',{'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),
        'operation_id':operation,'image_id':adopted['image_id'],'generation':adopted['generation'],
        'published_release_digest':result['release_digest'],'current_catalog_validation_digest':result['catalog_validation_digest'],
        'revalidated_catalog_digest':changed['catalog_validation_digest'],'release_identity_unchanged':True,
        'real_catalog_bytes_revalidated_under_new_policy':True,'pending_plan_stale':True,'isolated_quarantine_denied':True,
        'current_revocation_denied':True,'no_database_image_worker_traffic_or_policy_mutation':True,
        'incompatible_cache_write_denied_and_cache_preserved':True,
        'limits':['Existing image lacks the new app reader; roll out the qualified candidate with a new independently approved operation before refreshing the app profile.',
            'Alternate trust policy and quarantine used isolated validation/probe state; live trust policy unchanged.'],
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}})
    marker.write_text(json.dumps({'state':'adopted_verified','operation_id':operation,'evidence':str(output.relative_to(ROOT))},indent=2)+'\n')
    print(json.dumps({'result':'passed_subset','generation':adopted['generation'],'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
