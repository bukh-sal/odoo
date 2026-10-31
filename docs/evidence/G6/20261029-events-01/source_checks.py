"""Capture changed source/archive/CLI checks before an immutable event build."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
parser=argparse.ArgumentParser();parser.add_argument('--correction',action='store_true');parser.add_argument('--reference-only',action='store_true');args=parser.parse_args()
label='source-checks-reference' if args.reference_only else 'source-checks-corrected' if args.correction else 'source-checks'
private=protect_directory(ROOT/'.local/g6-event-planning');assert not (OUT/(label+'.json')).exists()
modules=['tests.test_resolution.Resolution.test_actual_three_reference_artifacts_resolve_without_import'] if args.reference_only else ['tests.test_artifacts','tests.test_resolution.Resolution.test_actual_three_reference_artifacts_resolve_without_import','tests.test_planning_cli'] if args.correction else ['tests.test_artifacts','tests.test_resolution','tests.test_planning_cli','tests.test_platform_compatibility','tests.test_event_contracts','tests.test_durable_validation']
with (private/(label+'.stdout')).open('xb') as stdout,(private/(label+'.stderr')).open('xb') as stderr:
    result=subprocess.run([sys.executable,'-X','utf8','-m','unittest',*modules,'-v'],cwd=ROOT,stdout=stdout,stderr=stderr)
raw=(private/(label+'.stderr')).read_bytes();counts=re.findall(r'Ran (\d+) tests?',raw.decode('utf8'))
record=dict(result='passed' if result.returncode==0 else 'failed',returncode=result.returncode,tests=int(counts[-1]) if counts else None,modules=modules,diagnostics_sha256=hashlib.sha256(raw).hexdigest(),limits='Source/archive/CLI checks only. New event storage/native API/hooks/projection still require actual PostgreSQL/Odoo/HTTP/browser qualification before EVT acceptance.')
(OUT/(label+'.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record));raise SystemExit(result.returncode)
