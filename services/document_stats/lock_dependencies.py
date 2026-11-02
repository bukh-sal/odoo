"""Derive worker locks from reviewed static Linux metadata; never install.

Use --metadata <runtime observation JSON> and --output <fresh directory>.
Host-installed package versions and source metadata hooks are never used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from packaging.utils import canonicalize_name
from packaging.requirements import Requirement

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.resolution import resolve_release

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--metadata',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='Fresh directory; existing locks are never overwritten')
    args=parser.parse_args();raw_metadata=args.metadata.read_bytes();observation=json.loads(raw_metadata)
    observation=observation.get('runtime',observation);output=args.output.resolve()
    if output.exists():raise ValueError('Fresh output directory required')
    sources={};blocks={};versions={}
    for relative in ['deploy/requirements-r1.lock','deploy/build-requirements.lock']:
        raw=(ROOT/relative).read_bytes();sources[relative]=hashlib.sha256(raw).hexdigest()
        for match in re.finditer(r'^([A-Za-z0-9_.-]+)==([^\s]+).*?(?=^[A-Za-z0-9_.-]+==|\Z)',raw.decode(),re.M|re.S):
            name=canonicalize_name(match[1]);block='\n'.join(line for line in match[0].splitlines() if line.strip() and not line.lstrip().startswith('#'))
            if name in versions and versions[name]!=match[2]:raise ValueError('Conflicting exact source locks: '+name)
            if not re.findall(r'--hash=sha256:[0-9a-f]{64}',block):raise ValueError('Missing source hashes: '+name)
            versions[name]=match[2];blocks[name]=block
    environment=dict(platform_version='0.1.21',native_runtime='odoo-19',markers=observation['markers'],accepted_wheel_tags=observation['accepted_wheel_tags'],core_addons=[])
    if environment['markers']['sys_platform']!='linux':raise ValueError('Reviewed Linux target metadata required')
    # Explicit pip prevents an older untracked venv bootstrap in the image.
    roots=['pyjwt','cryptography','jsonschema','rfc8785','packaging','pip']
    solution=resolve_release([],observation['python_metadata'],environment,{},core_python=[name+'=='+versions[name] for name in roots])
    closure={}
    for item in solution['python']:
        name=canonicalize_name(item['name'])
        if name not in blocks or versions[name]!=item['version']:raise ValueError('Observed metadata differs from exact source lock: '+name)
        dependencies=[]
        for value in item.get('requires_dist',[]):
            requirement=Requirement(value)
            if requirement.marker is None or requirement.marker.evaluate({**observation['markers'],'extra':''}):dependencies.append(canonicalize_name(requirement.name))
        closure[name]=dict(version=item['version'],dependencies=sorted(set(dependencies)))
    output.mkdir(parents=True)
    lock=('# Dedicated worker subset of reviewed runtime/build locks (ADR0046).\n# Complete static target closure; includes explicit bootstrap pip.\n'+'\n'.join(blocks[name] for name in sorted(closure))+'\n').encode()
    (output/'requirements.lock').write_bytes(lock)
    provenance=dict(source='deploy/requirements-r1.lock',source_sha256=sources['deploy/requirements-r1.lock'],bootstrap_source='deploy/build-requirements.lock',bootstrap_source_sha256=sources['deploy/build-requirements.lock'],metadata_sha256=hashlib.sha256(raw_metadata).hexdigest(),target_markers=observation['markers'],packages=closure,lock_sha256=hashlib.sha256(lock).hexdigest(),linux_runtime_verification='required during independent image build; static solution is not runtime qualification')
    (output/'dependency-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(result='derived_static_worker_lock',packages=len(closure),output=str(output),lock_sha256=provenance['lock_sha256'])))
if __name__=='__main__':main()
