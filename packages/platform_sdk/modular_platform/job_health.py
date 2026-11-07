"""Local liveness evidence from an authenticated native worker process."""

import json
import os
from pathlib import Path
import time
from uuid import uuid4


PATH = Path('/tmp/mp-job-health.json')
MAX_AGE_SECONDS = 10


def publish(*, database, site_id, release_digest, inventory_digest, pool, state):
    value = dict(protocol=1, database=database, site_id=site_id, release_digest=release_digest,
                 inventory_digest=inventory_digest, pool=pool, state=state,
                 pid=os.getpid(), updated_at=time.time())
    temporary = PATH.with_name('mp-job-health-'+uuid4().hex+'.tmp')
    with temporary.open('x', encoding='utf8') as stream:
        json.dump(value, stream)
    os.replace(temporary, PATH)


def check():
    if PATH.is_symlink() or PATH.stat().st_size > 4096:
        raise ValueError('Bounded worker health record required')
    value = json.loads(PATH.read_bytes())
    if (value['protocol'] != 1 or value['state'] not in {'idle', 'running'}
            or not 0 <= time.time()-value['updated_at'] <= MAX_AGE_SECONDS
            or value['database'] != os.environ['MP_EXPECTED_DATABASE']
            or value['inventory_digest'] != os.environ['MP_EXPECTED_INVENTORY_DIGEST']
            or value['site_id'] != os.environ.get('MP_EXPECTED_SITE_ID', value['site_id'])
            or value['release_digest'] != os.environ.get('MP_EXPECTED_RELEASE_DIGEST', value['release_digest'])):
        raise ValueError('Worker is unavailable or differs from its pins')
    os.kill(value['pid'], 0)
    return value


if __name__ == '__main__':
    try:
        value = check()
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit(1) from None
    print(json.dumps(value, sort_keys=True))
