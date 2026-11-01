"""Derive a dedicated hash lock from already pinned R1 packages; no installs."""
from importlib.metadata import distribution
import hashlib
import json
from pathlib import Path
import re
from packaging.requirements import Requirement

ROOT=Path(__file__).resolve().parents[2]
def main():
    source=ROOT/'deploy/requirements-r1.lock';raw=source.read_text()
    blocks={}
    for match in re.finditer(r'^([A-Za-z0-9_.-]+)==([^\s]+).*?(?=^[A-Za-z0-9_.-]+==|\Z)',raw,re.M|re.S):
        name=match[1].lower().replace('_','-')
        blocks[name]=(match[2],'\n'.join(line for line in match[0].splitlines() if line.strip() and not line.lstrip().startswith('#')))
    queue=['PyJWT','cryptography','jsonschema','rfc8785','packaging'];closure={}
    while queue:
        name=queue.pop();dist=distribution(name);name=dist.metadata['Name'].lower().replace('_','-')
        if name in closure:continue
        assert name in blocks and dist.version==blocks[name][0], 'Installed metadata must match approved pin'
        dependencies=[]
        for value in dist.requires or []:
            requirement=Requirement(value)
            if requirement.marker is None or requirement.marker.evaluate({'extra':''}):
                dependencies.append(requirement.name);queue.append(requirement.name)
        closure[name]=dict(version=dist.version,dependencies=dependencies)
    output=Path(__file__).with_name('requirements.lock');assert not output.exists()
    output.write_text('# Dedicated worker subset of deploy/requirements-r1.lock; preserve approved pins/hashes.\n# Closure verified by lock_dependencies.py; Linux wheel install and pip check required.\n'+'\n'.join(blocks[n][1] for n in sorted(closure))+'\n')
    Path(__file__).with_name('dependency-provenance.json').write_text(json.dumps(dict(source='deploy/requirements-r1.lock',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),packages=closure,linux_runtime_verification='required during independent image build'),indent=2)+'\n')
    print('Dedicated12-package approved hash subset written; Linux build/pip check still required.')
if __name__=='__main__':main()
