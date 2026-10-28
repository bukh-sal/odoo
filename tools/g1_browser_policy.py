"""Commit one known disposable fixture policy change for browser revocation proof."""
import argparse
import json
from datetime import datetime, timezone

import g1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace', choices=['A', 'B'])
    parser.add_argument('policy', choices=['editor', 'viewer', 'revoked'])
    args = parser.parse_args()
    state = g1.setup()
    fixture = json.loads((g1.r0.LOCAL / 'fixtures.json').read_text())
    row = fixture['memberships']['alice' + args.workspace]
    values = {'state': 'revoked'} if args.policy == 'revoked' else {'state': 'active', 'role': args.policy}
    code = f"""assert env.cr.dbname == {fixture['database']!r}
record=env['mp.membership'].browse({row!r})
assert record.principal_id.user_id.login == 'g1_alice'
assert record.workspace_id.public_id == {fixture['workspaces'][args.workspace]['public_id']!r}
record.write({values!r})
env.cr.commit()
print('MP_G1_RESULT=known-fixture-policy-committed')
"""
    log = g1.shell(state, 'g1-browser-policy-' + args.workspace + '-' + args.policy, code)
    result = {'workspace': args.workspace, 'policy': args.policy, 'commit_observed_by_utc': datetime.now(timezone.utc).isoformat(), 'evidence': str(log.relative_to(g1.r0.ROOT))}
    out = g1.r0.ROOT / state['evidence'] / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-browser-policy.json')
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
