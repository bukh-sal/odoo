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

    def test_actual_health_authenticated_duplicate_conflict_and_restart(self):
        client=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        client.request('GET','/health');response=client.getresponse();self.assertEqual(response.status,200);response.read();client.close()
        token=self.token();status,value=self.call(token=token);self.assertEqual(status,200)
        self.assertEqual(self.call(token=token),(status,value))
        self.assertEqual(self.call({**self.request,'input':{**self.request['input'],'text':'Changed'}},token)[0],409)
        self.stop();self.start();self.assertEqual(self.call(token=token),(status,value))

    def test_actual_auth_schema_and_payload_limit_denials_leave_health_available(self):
        token=self.token()
        self.assertEqual(self.call()[0],401)
        self.assertEqual(self.call(token=self.token(aud='wrong'))[0],401)
        self.assertEqual(self.call(token=token,raw=b'{"a":1,"a":2}')[0],400)
        self.assertEqual(self.call(token=token,raw=b'x'*131073)[0],400)
        self.assertEqual(self.call(token=token,path='/redirect')[0],404)
        self.assertEqual(self.call(token=token)[0],200)
