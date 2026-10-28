"""Reference worker JWT verification. Private issuer key never goes to worker."""
import jwt

from .contracts import ContractError, validate

ISSUER = 'modular-platform-host-v1'
AUDIENCE = 'mp-document-stats-v1'
REQUIRED = ['iss','aud','sub','jti','iat','nbf','exp','site_id','workspace_id','installation_id','endpoint_generation','methods']


def verify_worker_token(token, public_key, *, key_id, request):
    header = jwt.get_unverified_header(token)
    if set(header) != {'alg','typ','kid'} or header['alg'] != 'RS256' or header['typ'] != 'JWT' or header['kid'] != key_id:
        raise ContractError('Unsupported credential header')
    claims = jwt.decode(token, public_key, algorithms=['RS256'], issuer=ISSUER, audience=AUDIENCE, options={'require':REQUIRED, 'strict_aud':True}, leeway=0)
    validate('worker-claims', claims)
    validate('worker-request', request)
    if not (0 < claims['exp'] - claims['iat'] <= 300 and claims['nbf'] == claims['iat']):
        raise ContractError('Credential lifetime exceeds policy')
    for field in ['site_id','workspace_id','installation_id','endpoint_generation']:
        if claims[field] != request[field]:
            raise ContractError('Credential scope mismatch')
    if claims['sub'] != claims['installation_id'] or request['method'] not in claims['methods']:
        raise ContractError('Credential method or installation mismatch')
    return claims
