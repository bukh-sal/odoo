"""Host-side worker transport; current authority reader is supplied by the host.

This does not authorize metadata or launch runtimes. Egress policy is separately
operator-owned, never artifact/request data. Native code remains fully trusted.
"""
import copy
import http.client
import ipaddress
import json
import socket
import time
from urllib.parse import urlsplit
from uuid import uuid4
import jwt
from .contracts import validate, load_json
from .tokens import ISSUER, AUDIENCE


class WorkerDispatchError(Exception):
    def __init__(self, code, *, sent=False):
        super().__init__(code)
        self.code, self.sent = code, sent


class WorkerClient:
    """Private adapter. Reader must recheck actor/resource/binding/approval live.

    Egress maps config name to exact destination and operator-observed IPs for
    that approved image/generation. We dial a numeric IP and preserve Host;
    runtime DNS, redirects and environment proxy settings cannot select a URL.
    """
    def __init__(self, read_authorized_endpoint, load_issuer, egress, *, site_id,
                 workspace_id, installation_id, connection=http.client.HTTPConnection,
                 monotonic=time.monotonic, clock=time.time):
        self.read, self.issuer, self.egress = read_authorized_endpoint, load_issuer, copy.deepcopy(egress)
        self.scope = dict(site_id=site_id, workspace_id=workspace_id, installation_id=installation_id)
        self.connection, self.monotonic, self.clock = connection, monotonic, clock

    def endpoint(self):
        value = copy.deepcopy(self.read())
        validate('endpoint', value)
        if value['state'] != 'enabled' or value['api_version'] != '1.0' or 'analyze' not in value['allowed_methods']:
            raise WorkerDispatchError('FORBIDDEN')
        if any(value[key] != expected for key, expected in self.scope.items()):
            raise WorkerDispatchError('FORBIDDEN')
        policy = self.egress.get(value['endpoint_config'])
        if not policy or any(policy.get(key) != value[key] for key in ['destination','expected_image_digest','generation',*self.scope]):
            raise WorkerDispatchError('FORBIDDEN')
        addresses = policy.get('addresses')
        if not isinstance(addresses, list) or not 1 <= len(addresses) <= 8:
            raise WorkerDispatchError('FORBIDDEN')
        try:
            parsed = [ipaddress.IPv4Address(address) for address in addresses]
        except (ValueError, TypeError):
            raise WorkerDispatchError('FORBIDDEN') from None
        if any(ip.is_global or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved for ip in parsed):
            raise WorkerDispatchError('FORBIDDEN')
        return value, str(parsed[0])

    def analyze(self, values, *, request_id, operation_id):
        endpoint, address = self.endpoint()
        request = dict(api_version='1.0', request_id=request_id, operation_id=operation_id,
                       method='analyze', input=copy.deepcopy(values),
                       endpoint_generation=endpoint['generation'], **self.scope)
        validate('worker-request', request)
        body = json.dumps(request, ensure_ascii=False, separators=(',', ':')).encode()
        if len(body) > endpoint['payload_limit_bytes']:
            raise WorkerDispatchError('VALIDATION_FAILED')
        key_id, key = self.issuer(endpoint['issuer_key_ref'])
        now = int(self.clock())
        claims = dict(iss=ISSUER, aud=AUDIENCE, sub=self.scope['installation_id'],
                      jti=str(uuid4()), iat=now, nbf=now, exp=now+120,
                      methods=['analyze'], endpoint_generation=endpoint['generation'], **self.scope)
        validate('worker-claims', claims)
        credential = jwt.encode(claims, key, algorithm='RS256', headers={'kid':key_id})
        # Key lookup/signing is not permission to dispatch after revocation.
        current, current_address = self.endpoint()
        if current != endpoint or current_address != address:
            raise WorkerDispatchError('FORBIDDEN')
        destination = urlsplit(endpoint['destination'])
        timeout = endpoint['timeout_ms']/1000
        deadline = self.monotonic()+timeout
        connection = self.connection(address, destination.port, timeout=timeout)
        sent = False
        try:
            connection.connect()
            remaining = deadline-self.monotonic()
            if remaining <= 0:
                raise WorkerDispatchError('DEADLINE_EXCEEDED')
            connection.sock.settimeout(remaining)
            transport_socket = connection.sock
            sent = True
            connection.request('POST','/analyze',body,{'Host':destination.netloc,
                               'Content-Type':'application/json','Authorization':'Bearer '+credential})
            response = connection.getresponse()
            if response.status != 200 or response.getheader('Content-Type') != 'application/json':
                raise WorkerDispatchError('DEPENDENCY_UNAVAILABLE', sent=True)
            # Absolute deadline, not a timeout reset for every response chunk.
            chunks=[];size=0
            while not response.isclosed():
                remaining=deadline-self.monotonic()
                if remaining<=0:raise WorkerDispatchError('DEADLINE_EXCEEDED',sent=True)
                transport_socket.settimeout(remaining)
                chunk=response.read1(min(4096,65537-size))
                if not chunk:break
                chunks.append(chunk);size+=len(chunk)
                if size>65536:raise WorkerDispatchError('DEPENDENCY_UNAVAILABLE',sent=True)
            value=load_json(b''.join(chunks))
            validate('worker-response',value)
            if (value['request_id'],value['operation_id']) != (request_id,operation_id):
                raise WorkerDispatchError('DEPENDENCY_UNAVAILABLE',sent=True)
            current,current_address=self.endpoint()
            if current!=endpoint or current_address!=address:
                raise WorkerDispatchError('FORBIDDEN',sent=True)
            return value
        except WorkerDispatchError as error:
            error.sent = error.sent or sent
            raise
        except (socket.timeout,TimeoutError):
            raise WorkerDispatchError('DEADLINE_EXCEEDED',sent=sent) from None
        except (OSError,ValueError):
            raise WorkerDispatchError('DEPENDENCY_UNAVAILABLE',sent=sent) from None
        finally:connection.close()
