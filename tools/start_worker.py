"""Image-default entrypoint; approved maintenance uses an explicit entrypoint.

The image-owned profile cannot be downgraded by changing the inventory policy.
R0/G1 images retain their native invocation. R1 verifies its independently
provided inventory pin and bootstrap bytes before executing any SDK/native code.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import sys

ROOT=Path('/opt/modular')
CONFIG='/run/secrets/odoo_config'


def main():
    profile=(ROOT/'startup-profile').read_text().strip()
    if profile=='baseline':
        os.execv('/venv/bin/python',['/venv/bin/python','odoo-bin',*sys.argv[1:]])
        return
    if profile!='r1':raise ValueError('Unknown image startup profile')
    if sys.argv[1:]!=['-c',CONFIG]:raise ValueError('R1 startup accepts only the fixed configuration; use approved maintenance')
    database=os.environ.get('MP_EXPECTED_DATABASE','')
    pin=os.environ.get('MP_EXPECTED_INVENTORY_DIGEST','')
    if not database or not re.fullmatch('sha256:[0-9a-f]{64}',pin):
        raise ValueError('Independent database and inventory startup pins are required')
    raw=(ROOT/'distribution-inventory.json').read_bytes()
    if 'sha256:'+hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Application release inventory pin mismatch')
    inventory=json.loads(raw)
    if inventory['policy'].get('platform_sdk') is not True:raise ValueError('R1 image requires its SDK inventory')
    name='packages/platform_sdk/modular_platform/worker_start.py';guard=ROOT/name
    if guard.is_symlink() or hashlib.sha256(guard.read_bytes()).hexdigest()!=inventory['files'][name]:
        raise ValueError('Application bootstrap source differs from release inventory')
    # run_path does not import the SDK package or Odoo/plugin initializers.
    bootstrap=runpy.run_path(str(guard),run_name='verified_worker_bootstrap')
    sys.argv=['verified_worker_bootstrap',database,pin]
    bootstrap['main']()


if __name__=='__main__':main()
