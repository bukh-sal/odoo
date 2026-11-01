"""Pure reference computation with bounded deduplication, never text storage.

This is trusted R1 development code, not hostile-code containment. Restarting
may recompute the deterministic result; no external non-idempotent effect is
claimed. The host must freshly authorize any result before applying it.
"""
from collections import OrderedDict
import hashlib
import json
from threading import Lock
import time

from modular_platform.tokens import verify_worker_token


class WorkerError(Exception):
    def __init__(self, code, status):
        super().__init__(code)
        self.code, self.status = code, status


class Engine:
    def __init__(self, public_key, key_id, *, site_id, workspace_id,
                 installation_id, endpoint_generation, capacity=1024,
                 retention=600, clock=time.monotonic):
        if type(capacity) is not int or not 1 <= capacity <= 1024:
            raise ValueError('Bounded cache capacity required')
        if type(retention) is not int or not 1 <= retention <= 600:
            raise ValueError('Bounded cache retention required')
        self.public_key, self.key_id = public_key, key_id
        self.scope = dict(site_id=site_id, workspace_id=workspace_id,
                          installation_id=installation_id,
                          endpoint_generation=endpoint_generation)
        self.capacity, self.retention, self.clock = capacity, retention, clock
        self.cache, self.lock = OrderedDict(), Lock()
        self.computations = 0

    def analyze(self, token, request):
        # Authenticate retries as strictly as new work. No signing material,
        # cookies, main database connection or native ORM enters this process.
        try:
            verify_worker_token(token, self.public_key, key_id=self.key_id, request=request)
        except Exception:
            raise WorkerError('UNAUTHENTICATED', 401) from None
        if any(request[key] != value for key, value in self.scope.items()):
            raise WorkerError('FORBIDDEN', 403)
        digest = hashlib.sha256(json.dumps(request['input'], sort_keys=True,
                                           ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
        key = request['operation_id']
        with self.lock:
            now = self.clock()
            for expired in [k for k, v in self.cache.items() if v[0] <= now]:
                del self.cache[expired]
            saved = self.cache.get(key)
            if saved:
                if saved[1] != digest:
                    raise WorkerError('CONFLICT', 409)
                data = dict(saved[2])
            else:
                text = request['input']['text']
                data = dict(characters=len(text), words=len(text.split()), lines=len(text.splitlines()))
                self.computations += 1
                if len(self.cache) >= self.capacity:
                    self.cache.popitem(last=False)
                self.cache[key] = (now + self.retention, digest, dict(data))
        return dict(api_version='1.0', request_id=request['request_id'],
                    operation_id=key, data=data)
