"""OS-owned publication of sanitized, untrusted app planning metadata."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular_platform.projection import public_profile

WRITER='''import configparser,json,sys
import psycopg2
from psycopg2.extras import Json
payload=json.load(sys.stdin)
config=configparser.ConfigParser();config.read('/run/secrets/odoo_config');options=config['options']
connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],password=options['db_password'],dbname=options['db_name'],connect_timeout=10)
with connection:
 with connection.cursor() as cursor:
  cursor.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'");site=cursor.fetchone()[0]
  assert site in payload['configuration']['site_ids'],'Public profile must match the current site'
  cursor.execute("INSERT INTO mp_operation_profile(site_public_id,payload,create_uid,write_uid,create_date,write_date) VALUES (%s,%s,1,1,timezone('UTC',now()),timezone('UTC',now())) ON CONFLICT(site_public_id) DO UPDATE SET payload=EXCLUDED.payload,write_uid=1,write_date=timezone('UTC',now())",[site,Json(payload)])
connection.close()
print(json.dumps({'profile_published':True,'site_id':site}))
'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,default=ROOT/'.local/operator/targets/g5.json');args=parser.parse_args()
    store=OperatorStore(ROOT/'.local/operator/control');configuration=json.loads(args.target.read_text())
    if store.policy['deployments'].get(configuration['deployment_id'])!=sorted(site['site_id'] for site in configuration['sites']):raise RuntimeError('Target is not independently authorized')
    trust=json.loads((ROOT/'.local/operator/trust.json').read_text());validator=ArtifactValidator(TrustPolicy(approved_digests=frozenset(trust['approved_digests']),generation=trust['generation']))
    observer=DockerObserver(configuration);observation=observer.read();catalog=Catalog(ROOT/'.local/operator/catalog',validator,readonly=True).snapshot()
    observer.state(observation,catalog) # Independent byte/metadata/solution checks before publishing.
    profile=public_profile(configuration,observation,catalog,datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    raw=json.dumps(profile).encode()
    if len(raw)>16*1024*1024:raise RuntimeError('Public profile size limit')
    result=subprocess.run(['docker','exec','-i',observer._container('app'),'/venv/bin/python','-c',WRITER],input=raw,capture_output=True,timeout=30)
    if result.returncode:raise RuntimeError('Public metadata write failed; inspect target state')
    print(result.stdout.decode().strip())


if __name__=='__main__':main()
