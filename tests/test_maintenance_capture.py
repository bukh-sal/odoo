"""Maintenance children keep private attached bytes but never Docker logs."""
import sys,unittest
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.native_executor import NativeExecutor

class MaintenanceCaptureTests(unittest.TestCase):
 def test_every_child_disables_daemon_log_and_preserves_scope(self):
  executor=NativeExecutor.__new__(NativeExecutor);executor.config=dict(project='mp-r0-r1capturetest',deployment_id=str(uuid4()),image_id='sha256:'+'a'*64)
  for suffix in ['checkpoint','read-config','native','metadata','assets','restore-filestore']:
   with self.subTest(suffix=suffix):
    args,name=executor._child(str(uuid4()),suffix,network=False)
    self.assertEqual(args[args.index('--log-driver')+1],'none');self.assertEqual(args[args.index('--network')+1],'none');self.assertIn('--read-only',args);self.assertIn('type=volume,source=mp-r0-r1capturetest_appconfig,target=/run/secrets,readonly',args);self.assertNotIn('--rm',args)

if __name__=='__main__':unittest.main()
