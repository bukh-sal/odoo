PATTERNS=['test_executor_crash_fence.py', 'test_operator_store.py', 'test_recovery.py', 'test_unchanged_recovery.py', 'test_native_uninstall.py', 'test_artifact_removal.py', 'test_platform_deploy.py', 'test_core_upgrade.py']
HOST=False
import json,sys,unittest
sys.path[:0]=['tests','packages/platform_sdk']
suite=unittest.TestSuite()
for pattern in PATTERNS:suite.addTests(unittest.defaultTestLoader.discover('tests',pattern=pattern))
if HOST:suite.addTests(unittest.defaultTestLoader.loadTestsFromName('test_operator_store.OperatorStoreTests.test_new_lock_owner_after_possible_commit_records_recovery_before_stale_state_check'))
r=unittest.TextTestRunner(verbosity=1).run(suite)
print(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped))))
sys.exit(not r.wasSuccessful())
