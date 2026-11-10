"""Real isolated worker process; only public verification material is provisioned."""
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from tests.test_document_stats_engine import WorkerEngineTests


DENIAL = {'error': {'code': 'VALIDATION_FAILED'}}


def read_oversized_denial(response):
    """Validate a direct oversized-request denial after its HTTP400 status.

    The status must have arrived before any body read. Only a connection abort/
    reset while reading the (already-denied) body is tolerated; unknown errors,
    timeouts, malformed/delivered bodies and pre-status failures propagate.
    """
    if response.status != 400:
        raise AssertionError('expected HTTP400 before body read, got %r' % (response.status,))
    try:
        body = response.read()
    except (ConnectionAbortedError, ConnectionResetError):
        return None
    value = json.loads(body)
    if value != DENIAL:
        raise AssertionError('unexpected worker denial body')
    return value


def oversized_denial_exchange(client):
    return read_oversized_denial(client.getresponse())


class _FakeResponse:
    def __init__(self, *, status=400, body=None, error=None):
        self.status, self.body, self.error = status, body, error

    def read(self):
        if self.error is not None:
            raise self.error
        return self.body


class _FakeClient:
    def __init__(self, *, response=None, error=None):
        self.response, self.error = response, error

    def getresponse(self):
        if self.error is not None:
            raise self.error
        return self.response


class OversizedDenialGuardTests(unittest.TestCase):
    def test_post_status_connection_close_is_tolerated(self):
        for error in (ConnectionAbortedError('closed'), ConnectionResetError('reset')):
            with self.subTest(error=type(error).__name__):
                self.assertIsNone(read_oversized_denial(_FakeResponse(error=error)))

    def test_pre_status_failure_is_not_tolerated(self):
        with self.assertRaises(ConnectionAbortedError):
            oversized_denial_exchange(_FakeClient(error=ConnectionAbortedError('before status')))

    def test_unknown_body_errors_are_not_tolerated(self):
        for error in (OSError('unexpected'), TimeoutError('unexpected')):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)):
                    read_oversized_denial(_FakeResponse(error=error))

    def test_delivered_body_must_be_the_expected_json_denial(self):
        for body in (b'', b'not-json', json.dumps({'error': {'code': 'OTHER'}}).encode()):
            with self.subTest(body=body[:20]):
                with self.assertRaises((ValueError, AssertionError)):
                    read_oversized_denial(_FakeResponse(body=body))

    def test_expected_status_and_body_pass(self):
        self.assertEqual(read_oversized_denial(_FakeResponse(body=json.dumps(DENIAL).encode())), DENIAL)
        with self.assertRaises(AssertionError):
            read_oversized_denial(_FakeResponse(status=403, body=json.dumps(DENIAL).encode()))


class WorkerProcessTests(WorkerEngineTests):
    # Engine cases execute separately; this class supplies signed fixture helpers.
    test_frozen_request_response_and_unicode = None
    test_concurrent_duplicate_with_new_transport_ids_computes_once = None
    test_changed_input_conflicts_without_retaining_text = None
    test_retry_still_rejects_expired_wrong_audience_and_forged_scope = None
    test_capacity_expiry_and_restart_recompute_same_pure_result = None

    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory(prefix='mp-disposable-worker-')
        self.directory = Path(self.temp.name)
        self.config = self.directory/'config.json'
        public = self.directory/'public.pem';public.write_bytes(self.public)
        self.config.write_text(json.dumps(dict(public_key_file=str(public),key_id='ephemeral-test',**self.scope)))
        self.process = None
        self.logs = []
        self.start()

    def start(self):
        log = self.directory/('process-'+str(len(self.logs))+'.log');self.logs.append(log)
        self.stream = log.open('wb')
        env = {key:os.environ[key] for key in ['SYSTEMROOT','WINDIR','PATH'] if key in os.environ}
        root = Path(__file__).resolve().parents[1]
        env.update(PYTHONPATH=str(root/'packages/platform_sdk')+os.pathsep+str(root),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
        self.process = subprocess.Popen([sys.executable,'-X','utf8','-m','services.document_stats.server','--config',str(self.config),'--port','0'],cwd=root,env=env,stdout=self.stream,stderr=self.stream)
        deadline = time.monotonic()+10
        while time.monotonic()<deadline:
            lines=log.read_text().splitlines()
            if lines:
                ready=json.loads(lines[0]);self.port=ready['port'];return
            if self.process.poll() is not None:raise AssertionError('Worker exited before readiness; inspect owned test log')
            time.sleep(.02)
        raise AssertionError('Worker readiness timed out')

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.kill();self.process.wait(timeout=10)
        self.stream.close()

    def tearDown(self):
        self.stop()
        for log in self.logs:
            text=log.read_text();self.assertNotIn('Hello world',text);self.assertNotIn('Bearer',text);self.assertNotIn('eyJ',text)
        self.temp.cleanup()

    def call(self, body=None, token=None, *, path='/analyze', raw=None):
        client=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        try:
            data=raw if raw is not None else json.dumps(body or self.request).encode()
            client.request('POST',path,data,{'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
            response=client.getresponse();return response.status,json.loads(response.read())
        finally:client.close()

    def wait_for_worker_event(self, needle, timeout=2):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            text=self.logs[-1].read_text()
            if needle in text:return text
            time.sleep(.01)
        self.fail('owned worker log missing expected event')

    def test_actual_health_authenticated_duplicate_conflict_and_restart(self):
        client=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        client.request('GET','/health');response=client.getresponse();self.assertEqual(response.status,200);response.read();client.close()
        token=self.token();status,value=self.call(token=token);self.assertEqual(status,200)
        self.assertEqual(self.call(token=token),(status,value))
        self.assertEqual(self.call({**self.request,'input':{**self.request['input'],'text':'Changed'}},token)[0],409)
        self.stop();self.start();self.assertEqual(self.call(token=token),(status,value))

    def test_actual_auth_schema_and_route_denials_leave_health_available(self):
        token=self.token()
        self.assertEqual(self.call()[0],401)
        self.assertEqual(self.call(token=self.token(aud='wrong'))[0],401)
        self.assertEqual(self.call(token=token,raw=b'{"a":1,"a":2}')[0],400)
        self.assertEqual(self.call(token=token,path='/redirect')[0],404)
        self.assertEqual(self.call(token=token)[0],200)

    def test_actual_oversized_payload_denial_isolated_with_health_and_valid_analyze(self):
        token=self.token()
        client=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        try:
            client.request('POST','/analyze',b'x'*131073,{'Content-Type':'application/json','Authorization':'Bearer '+token})
            denial=oversized_denial_exchange(client)
        finally:
            client.close()
        self.assertIn(denial,(None,DENIAL))
        log=self.wait_for_worker_event('"event": "request", "status": 400')
        self.assertEqual(log.count('"event": "request", "status": 400'),1)
        health=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        try:
            health.request('GET','/health');response=health.getresponse();self.assertEqual(response.status,200);response.read()
        finally:
            health.close()
        status,value=self.call(token=token)
        self.assertEqual(status,200)
        self.assertEqual(value['data'],dict(characters=11,words=2,lines=1))


if __name__ == '__main__':
    unittest.main()
