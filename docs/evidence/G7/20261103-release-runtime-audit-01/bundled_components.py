"""Bounded no-network immutable helpers, stdlib/upstream library introspection only."""
import hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-runtime-audit-01'
code=r"""
import json,pathlib
from cryptography.hazmat.backends.openssl.backend import backend
result=dict(cryptography_openssl=backend.openssl_version_text(),sasl_mechanism_files=[str(p) for p in pathlib.Path('/usr/lib').glob('**/sasl2/*') if p.is_file()])
try:
 from lxml import etree
 from PIL import features
 import psycopg2.extensions
 result.update(lxml_compiled=etree.LIBXML_COMPILED_VERSION,lxml_runtime=etree.LIBXML_VERSION,libxslt=etree.LIBXSLT_VERSION,pillow_codecs=features.get_supported(),pillow_versions={n:features.version(n) for n in features.get_supported()},libpq=psycopg2.extensions.libpq_version())
except ImportError:pass
print(json.dumps(result))
"""
rows={}
for role in ['application','worker']:
 data=json.loads((OUT/(role+'-index.json')).read_text())
 image=json.loads((OUT/'collection.json').read_text())['roles'][role]['image']
 name='mp-g7-release-bundled-'+role+'-01'
 args=['docker','run','--rm','--name',name,'--label','com.modular.disposable=mp-g7-release-audit','--log-driver','none','--network','none','--read-only','--user','10001:10001' if role=='application' else '10002:10002','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--pids-limit','64','--entrypoint','/venv/bin/python',image,'-B','-c',code]
 r=subprocess.run(args,capture_output=True,timeout=60)
 (PRIVATE/(role+'-bundled.stdout')).write_bytes(r.stdout);(PRIVATE/(role+'-bundled.stderr')).write_bytes(r.stderr)
 assert r.returncode==0,'Inspect retained helper diagnostics before another attempt'
 rows[role]=dict(image=image,components=json.loads(r.stdout),network='none',mounts=[],removed_on_exit=True)
with (OUT/'bundled-components.json').open('x',encoding='utf8') as f:json.dump(dict(result='actual_components_collected_review_pending',utc=datetime.now(timezone.utc).isoformat(),roles=rows,limits=['Mechanism filenames identify shipped plugins; no generic LDAP/SASL exploitability verdict.','No package/plugin initialization or deployment changes; bundled component advisories still need review.']),f,indent=2)
print(json.dumps(rows))
