"""Build one reviewed hash-pinned LDAP source archive outside pure planning.

Only a tiny explicit tar context is sent to Docker. Export the wheel, not a
compiler image; no application database, authority, or executable mount.
"""
import hashlib,io,json,subprocess,tarfile,urllib.request
from pathlib import Path

ROOT=Path.cwd();OUT=Path(__file__).parent
PRIVATE=ROOT/'.local/g7-dependency-compatibility-01'
selection=json.loads((OUT/'candidate-selection.json').read_text())
prepared=json.loads((OUT/'probe-preparation.json').read_text())
candidate=next(p for p in selection['candidates'] if p['package']=='python-ldap')
assert candidate['version']=='3.4.8' and len(candidate['source_archives'])==1
source=candidate['source_archives'][0]
assert source['url'].startswith('https://files.pythonhosted.org/packages/')
with urllib.request.urlopen(source['url'],timeout=45) as response:raw=response.read()
assert len(raw)==source['size'] and hashlib.sha256(raw).hexdigest()==source['digests']['sha256']
source_path=PRIVATE/source['filename']
if source_path.exists():assert source_path.read_bytes()==raw
else:source_path.write_bytes(raw)
# Review static build declarations first. Do not invoke metadata build hooks.
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
 declarations={m.name:archive.extractfile(m).read().decode() for m in archive.getmembers()
               if m.isfile() and m.name.endswith(('/pyproject.toml','/setup.cfg','/setup.py','/LICENCE','/LICENSE','/CHANGES'))}
assert declarations and any(name.endswith('/pyproject.toml') for name in declarations)
if '--review-source-only' in __import__('sys').argv:
 print(json.dumps(declarations,indent=2));raise SystemExit(0)
(PRIVATE/'ldap-source-declarations.json').write_text(json.dumps(declarations,indent=2)+'\n',encoding='utf8')
# This exact upstream package is an explicitly trusted build input. Its code
# runs only in the disposable compiler, with network disabled for wheel build.
tools=[w for w in prepared['wheels'] if w['package'] in {'pip','setuptools','wheel'}]
assert len(tools)==3
lock=''.join(w['package']+'=='+w['version']+' --hash=sha256:'+w['digests']['sha256']+'\n' for w in tools)
base='python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753'
dockerfile='''# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM BASE AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261027T000000Z/ bookworm main\\ndeb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/20261027T000000Z/ bookworm-security main\\n' > /etc/apt/sources.list && rm /etc/apt/sources.list.d/debian.sources && apt-get update && apt-get install -y --no-install-recommends build-essential libldap2-dev libsasl2-dev libpq-dev libssl-dev libffi-dev && rm -rf /var/lib/apt/lists/*
COPY inputs /inputs
RUN --network=none python -m venv /build-venv && /build-venv/bin/python -m pip install --no-index --no-deps --find-links /inputs --require-hashes -r /inputs/build.lock && /build-venv/bin/python -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir /wheels /inputs/SOURCE
FROM scratch AS artifacts
COPY --from=builder /wheels/ /
'''.replace('BASE',base).replace('SOURCE',source['filename'])
(OUT/'Dockerfile.ldap-probe').write_text(dockerfile,encoding='utf8')
context=io.BytesIO()
with tarfile.open(fileobj=context,mode='w') as archive:
 def add(name,data):
  info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;archive.addfile(info,io.BytesIO(data))
 add('Dockerfile',dockerfile.encode());add('inputs/build.lock',lock.encode());add('inputs/'+source['filename'],raw)
 for w in tools:
  data=(PRIVATE/'wheels'/w['filename']).read_bytes();assert hashlib.sha256(data).hexdigest()==w['digests']['sha256'];add('inputs/'+w['filename'],data)
destination=PRIVATE/'ldap-wheels';assert not destination.exists()
with (PRIVATE/'ldap-build.stdout').open('xb') as out,(PRIVATE/'ldap-build.stderr').open('xb') as err:
 result=subprocess.run(['docker','buildx','build','--progress=plain','--network=default','--output','type=local,dest='+str(destination),'--metadata-file',str(PRIVATE/'ldap-build-metadata.json'),'-'],input=context.getvalue(),stdout=out,stderr=err,timeout=900)
assert result.returncode==0,'Inspect exact compiler logs; do not blindly repeat build'
wheels=list(destination.glob('*.whl'));assert len(wheels)==1 and wheels[0].name.startswith('python_ldap-3.4.8-')
report=dict(result='source_wheel_built_not_deployed',source=source,base_image=base,build_tools=tools,
 dockerfile_sha256=hashlib.sha256(dockerfile.encode()).hexdigest(),context_sha256=hashlib.sha256(context.getvalue()).hexdigest(),
 wheel=dict(filename=wheels[0].name,size=wheels[0].stat().st_size,sha256=hashlib.sha256(wheels[0].read_bytes()).hexdigest()),
 no_final_image_tag_or_service_created=True,source_build_network_disabled=True,original_runtime_unchanged=True,
 limits=['APT acquisition uses network to the pinned Debian snapshot; source compilation itself has no network.',
 'BuildKit compiler cache remains reusable; no global/shared cache prune. Wheel import/native linked-library probes remain.'])
(OUT/'ldap-build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report['wheel']))
