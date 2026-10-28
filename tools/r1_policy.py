"""Bounded policy/session fault fixtures for the known disposable R1 site."""
import argparse
import json
from datetime import datetime,timezone

import r1


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['revoke_alice_a','restore_alice_a','admin_alice_a','expire_alice_sessions']);args=parser.parse_args()
    state=r1.setup();fixture=json.loads((r1.r0.LOCAL/'fixtures.json').read_text())
    prefix=f"assert env.cr.dbname == {fixture['database']!r}\n"
    if args.action=='expire_alice_sessions':
        code=prefix+f"""from pathlib import Path
actor=env['res.users'].browse({fixture['users']['alice']['id']!r})
assert actor.login == 'r1_alice'
actor.write({{'password':Path('/run/mp-bootstrap/password').read_text().strip()}})
env.cr.commit()
env.registry.signal_changes()
print('MP_R1_RESULT=synthetic-session-authority-refreshed-with-same-login-credential')
"""
    else:
        values={'state':'revoked'} if args.action=='revoke_alice_a' else {'state':'active','role':'administrator' if args.action=='admin_alice_a' else 'editor'}
        code=prefix+f"""row=env['mp.membership'].browse({fixture['memberships']['aliceA']!r})
assert row.principal_id.user_id.login == 'r1_alice'
assert row.workspace_id.public_id == {fixture['workspaces']['A']['public_id']!r}
row.write({values!r})
env.cr.commit()
env.registry.signal_changes()
print('MP_R1_RESULT=known-fixture-policy-committed')
"""
    log=r1.shell(state,'r1-policy-'+args.action,code)
    report={'action':args.action,'commit_observed_by_utc':datetime.now(timezone.utc).isoformat(),'log':str(log.relative_to(r1.r0.ROOT))}
    out=r1.r0.ROOT/state['evidence']/(r1.r0.now()+'-policy.json');out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
