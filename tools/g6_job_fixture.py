"""Separate fresh F-01b integration fixture; preserve the paused primitive site."""
import argparse,hashlib,json,sys
import g6_fixture as f
from modular_platform.catalog import Catalog
from modular import configuration

ROOT=f.ROOT
f.LOCAL=LOCAL=ROOT/'.local/g6-jobs'
f.OUTPUT=OUTPUT=ROOT/'docs/evidence/G6/20261029-job-auth-01/site'
f.PROTECTED=[*f.PROTECTED,'.local/g6/operator/target.json']


def select_profile(profile):
    global LOCAL,OUTPUT
    assert profile in {'authorization','runner'}
    if profile=='runner':
        f.LOCAL=LOCAL=ROOT/'.local/g6-jobs-runner'
        f.OUTPUT=OUTPUT=ROOT/'docs/evidence/G6/20261029-job-auth-01/site-runner'
        f.PROTECTED=[*f.PROTECTED,'.local/g6-jobs/operator/target.json']


def curate(build,runtime,project):
    artifact=build['artifacts']['org.example.notes']
    assert artifact['version']=='0.2.5' and runtime['platform_version']=='0.1.8'
    assert runtime['inventory']['artifacts']['org.example.notes']==artifact
    target=LOCAL/'notes-0.2.5.mplug';assert not target.exists()
    # Read exact static archive bytes without loading native/plugin code.
    data=f.command('extract-notes-025',['docker','run','--name',project+'-extract-notes-025','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/venv/bin/python',build['image_id'],'-c',"import pathlib,sys;sys.stdout.buffer.write(pathlib.Path('/opt/modular/artifacts/org.example.notes-0.2.5.mplug').read_bytes())"])
    assert 'sha256:'+hashlib.sha256(data).hexdigest()==artifact['digest'];target.write_bytes(data)
    policy=f.load(LOCAL/'operator/trust.json');assert policy['generation']==3
    policy['generation']+=1;policy['approved_digests'].append(artifact['digest']);f.write(LOCAL/'operator/trust.json',policy)
    catalog=Catalog(LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'))
    before=catalog.snapshot();assert len(before)==7
    descriptor=catalog.add(target,expected_digest=artifact['digest']);after=catalog.snapshot()
    assert len(after)==8 and descriptor['version']=='0.2.5'
    assert not any(d['version']=='0.2.4' and d['plugin_id']=='org.example.notes' for d in after)
    f.save('isolated-curation.json',dict(result='passed',artifact=artifact,platform_version=runtime['platform_version'],catalog_entries=8,trust_generation=4,global_catalog_and_trust_unchanged=True,rejected_024_not_curated=True))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['configure','initialize','install']);parser.add_argument('--profile',choices=['authorization','runner'],default='authorization');args=parser.parse_args()
    select_profile(args.profile)
    if args.action=='configure':
        candidate='03' if args.profile=='runner' else '02'
        f.configure(build_path=ROOT/('docs/evidence/G6/20261029-job-auth-candidate-'+candidate+'/candidate-build.json'),core_version='19.0.0.1.8',hostname='g6runner.localhost' if args.profile=='runner' else 'g6jobs.localhost',port_start=18087 if args.profile=='runner' else 18086,curator=curate)
    else:getattr(f,args.action)()


if __name__=='__main__':main()
