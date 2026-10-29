"""Capture bounded host source checks; no native or deployment mutation."""
import hashlib,json,re,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
private=protect_directory(ROOT/'.local/g6-job-auth-artifacts')
assert not (OUT/'source-checks.json').exists()
modules=['tests.test_platform_compatibility','tests.test_resolution','tests.test_release_identity','tests.test_release_staging','tests.test_core_upgrade']
started=time.monotonic()
with (private/'source-checks.stdout').open('xb') as stdout,(private/'source-checks.stderr').open('xb') as stderr:
    result=subprocess.run([sys.executable,'-X','utf8','-m','unittest',*modules,'-v'],cwd=ROOT,stdout=stdout,stderr=stderr)
log=(private/'source-checks.stderr').read_text(encoding='utf8')
counts=re.findall(r'Ran (\d+) tests?',log)
record=dict(result='passed' if result.returncode==0 else 'failed',returncode=result.returncode,tests=int(counts[-1]) if counts else None,modules=modules,seconds=round(time.monotonic()-started,3),diagnostics_sha256=hashlib.sha256(log.encode()).hexdigest(),reason='Prior uncaptured source-check process is terminal; its output handle expired before the result could be recovered. This captured verification is read-only and repeats no native operation.')
(OUT/'source-checks.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print(json.dumps(record))
raise SystemExit(result.returncode)
