"""Real reference archive reproducibility and pre-import composition conflicts."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tomllib
import zipfile

import r1
from reference_package import assemble,toml_value,validate_reference_composition


def main():
    state=r1.setup();fixture=json.loads((r1.r0.LOCAL/'g4-fixtures.json').read_text());artifacts={};checks=[]
    sys.path.insert(0,str(r1.r0.ROOT/'packages/platform_sdk'))
    from modular_platform.contracts import ContractError
    for name in ['notes','notes_labels','canvas']:
        manifest,raw,files=assemble(r1.r0.ROOT,'plugins/'+name+'/plugin.toml');plugin=manifest['plugin']['id']
        assert assemble(r1.r0.ROOT,'plugins/'+name+'/plugin.toml')[1]==raw
        assert 'sha256:'+hashlib.sha256(raw).hexdigest()==fixture['packages'][plugin]['digest']
        artifacts[plugin]=raw
    registry=validate_reference_composition(list(artifacts.values()))
    assert registry['fields']['mp.example.note.title']=='org.example.notes' and registry['fields']['mp.example.note.x_notes_labels']=='org.example.notes_labels'
    checks.append({'name':'all3 packages reproduce exact registered outer bytes and declare distinct model/field ownership','result':'passed'})
    def altered(kind):
        raw=artifacts['org.example.notes_labels'];archive=zipfile.ZipFile(io.BytesIO(raw));files={entry.filename:archive.read(entry) for entry in archive.infolist()};prefix='org.example.notes_labels/'
        manifest=tomllib.loads(files[prefix+'plugin.toml'].decode())
        if kind=='field':
            manifest['data']['contributions'][0]['id']='mp.example.note.title'
            name=prefix+'backend/odoo_addons/mp_example_notes_labels/models.py'
            files[name]=b"raise RuntimeError('This code must never be imported by validation')\n"+files[name].replace(b'x_notes_labels=fields.Json',b'title=fields.Json')
        elif kind=='slot':manifest['ui']['contributions'][0]['slot_major']=2
        else:manifest['upgrade']['transitions'][0]['scripts'][0]['digest']='sha256:'+'0'*64
        files[prefix+'plugin.toml']=('\n'.join(json.dumps(k)+' = '+toml_value(v) for k,v in manifest.items())+'\n').encode()
        inventory=json.loads(files[prefix+'inventory.json'])
        inventory['files']={name.removeprefix(prefix):hashlib.sha256(value).hexdigest() for name,value in files.items() if name!=prefix+'inventory.json'}
        files[prefix+'inventory.json']=(json.dumps(inventory,sort_keys=True,indent=2)+'\n').encode()
        result=io.BytesIO()
        with zipfile.ZipFile(result,'w') as target:
            for name,value in files.items():target.writestr(name,value)
        return result.getvalue()
    for kind,reason in [('field','Conflicting declarative native field'),('slot','Required slot missing or incompatible'),('script','Migration script digest mismatch')]:
        try:validate_reference_composition([artifacts['org.example.notes'],altered(kind),artifacts['org.example.canvas']])
        except ContractError as error:assert str(error)==reason,str(error)
        else:raise AssertionError('Conflicting artifact was accepted')
        checks.append({'name':'actual archive '+kind+' conflict rejected before any plugin import','result':'passed','reason':reason})
    optional=validate_reference_composition([artifacts['org.example.notes'],artifacts['org.example.canvas']]);assert optional['ui_contributions']==[]
    checks.append({'name':'absent optional Labels integration does not break Notes/Canvas composition','result':'passed'})
    out=r1.r0.ROOT/state['evidence']/(r1.r0.now()+'-reference-packages.json');out.write_text(json.dumps({'state':'passed','checks':checks,'registry':registry,'limitation':'repository-owned reference assembler; hostile archive/trust validation remains G5'},indent=2)+'\n')
    print(json.dumps({'result':'passed','checks':len(checks),'evidence':str(out.relative_to(r1.r0.ROOT))}))


if __name__=='__main__':main()
