"""HTTP compatibility fence, independent of workspace/actor authorization."""
from functools import lru_cache
import hashlib
from pathlib import Path

from odoo.exceptions import AccessError
from odoo.http import request
from modular_platform.client_release import read_release,matches_release,RECOVERY_PATHS


class ClientReleaseMismatch(AccessError):
    pass


class ClientReleaseUnavailable(AccessError):
    pass


@lru_cache(maxsize=1)
def image_inventory_digest():
    return 'sha256:'+hashlib.sha256(Path('/opt/modular/distribution-inventory.json').read_bytes()).hexdigest()


def current_release(env):
    try:return read_release(env.cr,image_inventory_digest())
    except (ValueError,TypeError,OSError):raise ClientReleaseUnavailable('Release metadata unavailable') from None


def require_client_release(env):
    if not request or request.db!=env.cr.dbname:return
    if request.httprequest.path in RECOVERY_PATHS:return
    if getattr(request,'_mp_client_release_checked',False):return
    document=current_release(env)
    if not matches_release(document,request.httprequest.headers.get('X-MP-Client-Release')):
        raise ClientReleaseMismatch('Platform release changed; refresh the page')
    request._mp_client_release_checked=True
