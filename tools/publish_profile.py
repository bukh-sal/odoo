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

from modular_platform.profile_channel import publish_profile
from modular_platform.operator_os import OperationLocks
from modular import configuration as artifact_configuration


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,default=ROOT/'.local/operator/targets/g5.json');args=parser.parse_args()
    store=OperatorStore(ROOT/'.local/operator/control');configuration=json.loads(args.target.read_text())
    if store.policy['deployments'].get(configuration['deployment_id'])!=sorted(site['site_id'] for site in configuration['sites']):raise RuntimeError('Target is not independently authorized')
    validator=artifact_configuration(ROOT/'.local/operator/trust.json')
    with OperationLocks(store.root/'locks',configuration['deployment_id'],[site['site_id'] for site in configuration['sites']]):
        if json.loads(args.target.read_text())!=configuration:raise RuntimeError('Target changed before profile publication')
        store._authorize_plan({'deployment_id':configuration['deployment_id'],'site_ids':[site['site_id'] for site in configuration['sites']],
            'policy_version':configuration['policy_version'],'operator_authorization_generation':configuration['operator_authorization_generation']})
        print(json.dumps(publish_profile(DockerObserver(configuration),Catalog(ROOT/'.local/operator/catalog',validator,readonly=True))))



if __name__=='__main__':main()
