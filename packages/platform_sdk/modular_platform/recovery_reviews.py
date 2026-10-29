"""OS-owned, expiring exact-hash recovery reviews outside the restored DB."""
import copy
from datetime import datetime, timedelta, timezone
import re
from uuid import UUID, uuid4

from .contracts import load_json
from .operator_os import OperatorError, current_identity, protect_directory, verify_private_directory
from .operator_store import _write_new
from .plans import data_digest


def _utc(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)


def _stamp(value):
    return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def _parse(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',value):
        raise OperatorError('Canonical UTC recovery review timestamps required')
    return datetime.fromisoformat(value.replace('Z','+00:00'))


class RecoveryReviews:
    def __init__(self,store):
        self.store=store
        self.root=store.root/'recovery-reviews'

    def issue(self,payload,*,now=None):
        if 'review' in payload or payload.get('action') not in ('restore_to_fresh_database','resume_verified_restore','resume_unchanged_release'):
            raise OperatorError('Exact restore/resume recovery proposal required')
        policy=self.store._policy()
        issued=_utc(now)
        decision=copy.deepcopy(payload)
        decision['review']={'review_id':str(uuid4()),'issued_at':_stamp(issued),
            'expires_at':_stamp(issued+timedelta(seconds=policy['maximum_start_lifetime'])),
            'policy_version':policy['policy_version'],'operator_authorization_generation':policy['authorization_generation']}
        protect_directory(self.root)
        _write_new(self.root/(decision['review']['review_id']+'.json'),
            {'decision':decision,'decision_hash':data_digest(decision),'operator_identity':current_identity()})
        return decision

    def _record(self,decision,exact_hash):
        review=decision.get('review')
        if not isinstance(review,dict) or set(review)!={'review_id','issued_at','expires_at','policy_version','operator_authorization_generation'}:
            raise OperatorError('Independent bounded recovery review required')
        value=review['review_id']
        if not isinstance(value,str) or str(UUID(value))!=value:
            raise OperatorError('Canonical recovery review identity required')
        verify_private_directory(self.root)
        path=self.root/(value+'.json');self.store._regular(path)
        record=load_json(path.read_bytes())
        if (data_digest(decision)!=exact_hash or record['decision_hash']!=exact_hash or record['decision']!=decision
                or record['operator_identity']!=current_identity()):
            raise OperatorError('Exact reviewed recovery hash and authenticated operator required')
        return review

    def verify(self,decision,*,exact_hash,current_payload,now=None):
        policy,review=self.check_reserved(decision,exact_hash=exact_hash)
        issued,expires=_parse(review['issued_at']),_parse(review['expires_at'])
        if (not issued<=_utc(now)<expires or not 0<(expires-issued).total_seconds()<=policy['maximum_start_lifetime']):
            raise OperatorError('Recovery review unavailable: expired, future or excessive start lifetime')
        payload=copy.deepcopy(decision);payload.pop('review')
        if payload!=current_payload:
            raise OperatorError('Recovery target, checkpoint, authority or actual state changed since review')

    def check_reserved(self,decision,*,exact_hash):
        """Safe-boundary recheck after start: expiry is only a start deadline."""
        policy=self.store._policy();review=self._record(decision,exact_hash)
        revoked=self.root/(review['review_id']+'.revoked.json')
        if revoked.exists():
            self.store._regular(revoked)
            raise OperatorError('Independent recovery review is revoked')
        if (type(review['policy_version']) is not int or type(review['operator_authorization_generation']) is not int
                or review['policy_version']!=policy['policy_version']
                or review['operator_authorization_generation']!=policy['authorization_generation']):
            raise OperatorError('Recovery policy or independent operator authority changed')
        return policy,review

    def revoke(self,decision,*,exact_hash):
        self.store._policy()
        review=self._record(decision,exact_hash)
        path=self.root/(review['review_id']+'.revoked.json')
        if path.exists():
            self.store._regular(path)
            return
        _write_new(path,{'review_id':review['review_id'],'operation_id':decision['operation_id'],
            'decision_hash':exact_hash,'revoked_at':_stamp(_utc()),'operator_identity':current_identity()})
