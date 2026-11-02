"""Archive actual installed versions/native links and retire exact terminal helpers."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-dependency-compatibility-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import OBSERVE_RUNTIME
state=json.loads((PRIVATE/'probe-state.json').read_text())
assert state['state']=='native_primitives_passed_further_qualification_pending' and not state['deferred_source_build']
def call(label,args,raw=None):
 result=subprocess.run(args,input=raw,capture_output=True,timeout=120)
 for suffix,data in [('stdout',result.stdout),('stderr',result.stderr)]:
  with (PRIVATE/(label+'.'+suffix)).open('xb') as f:f.write(data)
 assert result.returncode==0,'Inspect '+label+'; no blind retry'
 return result.stdout
code=OBSERVE_RUNTIME.replace("print(json.dumps({'inventory'","observation={'inventory'")
# Keep the established runtime collector itself intact rather than modifying
# its source strings. Capture its single output into an in-memory stream.
code="import contextlib,io,json\ncaptured=io.StringIO()\nwith contextlib.redirect_stdout(captured):\n exec("+repr(OBSERVE_RUNTIME)+")\nobservation=json.loads(captured.getvalue())\n"
code+='''import _ldap,ldap,lxml.etree,cryptography,subprocess
from PIL import features
links=subprocess.run(['ldd',_ldap.__file__],capture_output=True,text=True,check=True).stdout
assert 'not found' not in links
print(json.dumps(dict(runtime=observation,ldap=dict(version=ldap.__version__,tls=bool(ldap.TLS_AVAIL),sasl=bool(ldap.SASL_AVAIL),linked_libraries=links),pillow_features={name:features.version(name) for name in features.get_supported()},libxml_version=lxml.etree.LIBXML_VERSION,libxslt_version=lxml.etree.LIBXSLT_VERSION)))
'''
args=['docker','run','--rm','-i','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g','--cpus','2','--tmpfs','/tmp','--mount','type=volume,source='+state['volume']+',target=/probe,readonly','--entrypoint','/probe/venv/bin/python',state['image'],'-B','-']
observed=json.loads(call('final-installed-metadata',args,code.encode()));runtime=observed['runtime']
normalize=lambda value:re.sub('[-_.]+','-',value).lower()
actual={normalize(p['name']):p for p in runtime['python_metadata']}
selection=json.loads((OUT/'candidate-selection.json').read_text());assert 'pypdf2' not in actual
for p in selection['candidates']:assert actual[normalize(p['package'])]['version']==p['version'],p['package']
assert not runtime['modified_files'] and not runtime['missing_addon_files'] and not runtime['unexpected_addon_files']
retired=[]
names=[state['copy_container'],state['install_container'],state['ldap_install_container'],*(state['project']+'-native-primitives-'+s for s in ['01','02','03'])]
for index,name in enumerate(names):
 item=json.loads(call('inspect-helper-'+str(index),['docker','inspect',name]))[0]
 assert item['Name']=='/'+name and item['Config']['Labels']['com.modular.disposable']==state['project']
 assert item['State']['Status']=='exited' and not item['State']['Running']
 expected=1 if name.endswith('native-primitives-01') else 0
 assert item['State']['ExitCode']==expected
 assert all(m['Type']=='volume' and m['Name']==state['volume'] for m in item['Mounts'])
 call('retire-helper-'+str(index),['docker','rm',item['Id']])
 gone=subprocess.run(['docker','inspect',item['Id']],capture_output=True,timeout=30);assert gone.returncode!=0 and b'No such' in gone.stderr
 retired.append(dict(name=name,id=item['Id'],exit_code=expected,removed=True))
report=dict(result='isolated_dependency_primitive_compatibility_passed',base_image=state['image'],retained_probe_volume=state['volume'],
 qualified_runtime_unchanged=True,installed_candidate_versions={p['package']:p['version'] for p in selection['candidates']},
 runtime_distributions=[{k:p[k] for k in ['name','version','digest']} for p in runtime['python_metadata']],
 ldap=observed['ldap'],pillow_features=observed['pillow_features'],libxml_version=observed['libxml_version'],libxslt_version=observed['libxslt_version'],
 native_tests=dict(tests=9,passed=True,report='native-primitives-03.json'),retired_helpers=retired,
 evidence_sha256={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['candidate-selection.json','probe-preparation.json','ldap-build.json','ldap-install.json','native-primitives-01.json','native-primitives-02.json','native-primitives-03.json']},
 limits=['Not a release image; original image lock is intentionally unchanged and does not describe this experiment.',
 'No application registry, database, native lifecycle, full acceptance, fresh release, performance or final security qualification.',
 'One isolated probe volume retained for required follow-up; no compiler image tagged, shared BuildKit cache untouched.'])
(OUT/'compatibility-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
state['state']='primitive_compatibility_qualified_helpers_retired_probe_retained';state['retired_helpers']=retired
(PRIVATE/'probe-state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(result=report['result'],candidates=len(selection['candidates']),tests=9,retired_helpers=len(retired))))
