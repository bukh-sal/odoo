"""One isolated native rollback diagnostic, no application source patch."""
import json,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;LOCAL=ROOT/'.local/g7-production-profile-01'
s=json.loads((LOCAL/'state.json').read_text());fixture=json.loads((LOCAL/'fixtures.json').read_text());project=s['project']
code="""import json,traceback
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
fixture=FIXTURE
env.cr.rollback()
try:
 actor=scoped_environment(api.Environment(env.cr,fixture['users']['alice']['id'],{}),fixture['workspaces']['A']['public_id'])
 note=actor['mp.example.note'].create({'title':'SEC02_owned_native_rollback','body':'Owned temporary CSRF acceptance fixture'})
 print('DIAGNOSTIC='+json.dumps(dict(result='native_create_succeeded_rolled_back',id=note.id)))
except Exception as error:
 print('DIAGNOSTIC='+json.dumps(dict(type=type(error).__name__,message=str(error),frames=[dict(file=f.filename.split('/')[-1],line=f.lineno,function=f.name) for f in traceback.extract_tb(error.__traceback__)])))
finally:env.cr.rollback()
""".replace('FIXTURE',repr(fixture))
args=['docker','run','--rm','-i','--name','mp-g7-http-native-create-diagnostic','--label','com.modular.disposable='+project,'--log-driver','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',project+'_runtime','--memory','1024m','--tmpfs','/tmp','--mount','type=volume,source='+project+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+project+'_filestore,target=/var/lib/modular','--entrypoint','/venv/bin/python',s['image_id'],'odoo-bin','shell','-c','/run/secrets/odoo_config','-d',s['active_db'],'--no-http','--workers=0','--max-cron-threads=0']
r=subprocess.run(args,input=code.encode(),capture_output=True,timeout=120);(LOCAL/'native-create-diagnostic.stdout').write_bytes(r.stdout);(LOCAL/'native-create-diagnostic.stderr').write_bytes(r.stderr);assert r.returncode==0
result=json.loads(next(line.removeprefix('DIAGNOSTIC=') for line in r.stdout.decode().splitlines() if line.startswith('DIAGNOSTIC=')))
(OUT/'native-create-diagnostic.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
