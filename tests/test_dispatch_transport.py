"""Large private helper envelopes use stdin, within Windows argv limits."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/platform_sdk'))
from modular_platform.dispatch_operator import BOOTSTRAP


class TransportTests(unittest.TestCase):
    def invoke(self,body):
        return subprocess.run([sys.executable,'-c',BOOTSTRAP],input=json.dumps(body).encode(),capture_output=True,timeout=15)

    def test_source_larger_than_windows_argv_limit_reaches_fixed_helper(self):
        script="import json,sys; data=json.load(sys.stdin); print(json.dumps(dict(source_size=len(LIFECYCLE_SOURCE),authority_size=len(RECURRENCE_AUTHORITY_SOURCE),request=data)))"
        body=dict(lifecycle='x'*100000,authority='y'*10000,script=script,request={'action':'observe'})
        result=self.invoke(body)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertEqual(json.loads(result.stdout),dict(source_size=100000,authority_size=10000,request={'action':'observe'}))
        self.assertLess(len(BOOTSTRAP),2000)

    def test_unknown_envelope_and_oversized_input_do_not_execute_script(self):
        body=dict(lifecycle='',authority='',script="print('unexpected execution')",request={})
        for invalid in (dict(body,unknown=True),dict(body,request='not an object'),dict(body,lifecycle='x'*2097153)):
            with self.subTest(keys=list(invalid)):
                result=self.invoke(invalid)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(result.stdout,b'')


if __name__=='__main__':unittest.main()
