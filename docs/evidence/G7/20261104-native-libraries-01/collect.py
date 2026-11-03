"""Actual stdlib/native component identities without plugin/config mounts."""
import hashlib,json,platform,pyexpat,sqlite3,ssl,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-native-libraries-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
assert not PRIVATE.exists();protect_directory(PRIVATE)
roles={}
code="import json,platform,pyexpat,sqlite3,ssl,zlib;print(json.dumps(dict(python=platform.python_version(),expat=pyexpat.EXPAT_VERSION,sqlite=sqlite3.sqlite_version,openssl=ssl.OPENSSL_VERSION,zlib=zlib.ZLIB_RUNTIME_VERSION)))"
collection=json.loads((ROOT/'docs/evidence/G7/20261103-release-runtime-audit-01/collection.json').read_text())
for role in ['application','worker']:
 image=collection['roles'][role]['image'];args=['docker','run','--rm','--name','mp-g7-native-library-'+role,'--label','com.modular.disposable=mp-g7-native-libraries','--log-driver','none','--network','none','--read-only','--user','10001:10001' if role=='application' else '10002:10002','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/venv/bin/python',image,'-B','-c',code]
 r=subprocess.run(args,capture_output=True,timeout=45);(PRIVATE/(role+'.stdout')).write_bytes(r.stdout);(PRIVATE/(role+'.stderr')).write_bytes(r.stderr);assert r.returncode==0
 roles[role]=dict(image_id=image,components=json.loads(r.stdout),no_mounts=True,network='none',collector_removed=True)
roles['isolated_operator']=dict(python=platform.python_version(),expat=pyexpat.EXPAT_VERSION,sqlite=sqlite3.sqlite_version,openssl=ssl.OPENSSL_VERSION)
node=subprocess.run([r'C:\Program Files\nodejs\node.exe','-p','JSON.stringify(process.versions)'],capture_output=True,timeout=15);assert node.returncode==0;roles['host_build_node']=json.loads(node.stdout)
record=dict(result='actual_native_components_collected_advisory_review_pending',utc=datetime.now(timezone.utc).isoformat(),roles=roles,deployment_mutations=0,images_built=0,limits=['Exact actual native component versions, not a security verdict. Bundled libraries may differ from OS package and Python distribution versions.','No plugin imports/config/DB/issuer mounts or runtime restarts.'])
with (OUT/'inventory.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(roles))
