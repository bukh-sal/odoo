import json,subprocess,sys
from pathlib import Path
OUT=Path(__file__).parent
names=['test_core_upgrade','test_release_staging','test_external_projection','test_reference_staging','test_worker_transition','test_native_versions']
code="import sys,unittest,json;sys.path.insert(0,'tests');suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in "+repr(names)+");r=unittest.TextTestRunner(verbosity=2).run(suite);print(json.dumps(dict(tests=r.testsRun,successful=r.wasSuccessful())));raise SystemExit(not r.wasSuccessful())"
r=subprocess.run([sys.executable,'-X','utf8','-c',code],capture_output=True);(OUT/'source-tests.log').write_bytes(r.stdout+r.stderr);assert r.returncode==0
freeze=subprocess.run([sys.executable,'-X','utf8','tools/check_contract_freeze.py'],capture_output=True);assert freeze.returncode==0
(OUT/'contract-freeze.json').write_bytes(freeze.stdout)
result=json.loads(r.stdout);(OUT/'source-tests.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
