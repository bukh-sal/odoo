"""Public release compatibility metadata; tokens confer no authority."""
import hmac
import re

from .contracts import validate
from .plans import data_digest

PARAMETERS=('mp.site_id','mp.release_generation','mp.release_digest','mp.active_inventory_digest')
RECOVERY_PATHS=frozenset({'/api/v1/session','/api/v1/workspaces','/api/v1/client-release'})


def read_release(cursor,inventory_digest):
    cursor.execute('SELECT key,value FROM ir_config_parameter WHERE key=ANY(%s)',[list(PARAMETERS)])
    values=dict(cursor.fetchall())
    generation=values.get('mp.release_generation','')
    if not isinstance(generation,str) or not re.fullmatch(r'[1-9][0-9]{0,15}',generation):
        raise ValueError('Published release generation unavailable')
    document={'protocol':1,'site_id':values.get('mp.site_id'),'generation':int(generation),
        'release_digest':values.get('mp.release_digest'),'inventory_digest':values.get('mp.active_inventory_digest')}
    if document['inventory_digest']!=inventory_digest:raise ValueError('Running release inventory mismatch')
    document['token']=data_digest(document)
    validate('client-release',document)
    return document


def matches_release(document,token):
    return isinstance(token,str) and bool(re.fullmatch(r'sha256:[0-9a-f]{64}',token)) and hmac.compare_digest(document['token'],token)


def protected_gateway(path):
    return path.startswith('/api/v1/') and path not in RECOVERY_PATHS
