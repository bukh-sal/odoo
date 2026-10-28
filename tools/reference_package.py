"""Deterministic G4 reference artifact assembler, never a general upload validator.

Only repository-owned allowlisted examples are accepted here. G5 owns hostile
archive validation, catalog trust, immutable release planning and execution.
"""
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import tomllib
import zipfile


def toml_value(value):
    if isinstance(value,str):return json.dumps(value,ensure_ascii=False)
    if isinstance(value,bool):return str(value).lower()
    if isinstance(value,int):return str(value)
    if isinstance(value,list):return '['+', '.join(map(toml_value,value))+']'
    if isinstance(value,dict):return '{'+', '.join(json.dumps(key)+' = '+toml_value(item) for key,item in value.items())+'}'
    raise ValueError('Unsupported reference TOML value')


def assemble(source,manifest_path):
    manifest_path=(source/manifest_path).resolve()
    if not manifest_path.is_relative_to(source/'plugins'):raise ValueError('Reference manifests must be repository plugin inputs')
    manifest=tomllib.loads(manifest_path.read_text());plugin=manifest['plugin']['id'];version=manifest['plugin']['version'];addon=manifest['runtime']['addon_name']
    if plugin not in ['org.example.notes','org.example.notes_labels','org.example.canvas'] or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',version):raise ValueError('Not an allowlisted reference package')
    if addon not in ['mp_example_notes','mp_example_notes_labels','mp_example_canvas']:raise ValueError('Unsupported reference addon')
    addon_dir=source/'platform_addons'/addon
    native=ast.literal_eval((addon_dir/'__manifest__.py').read_text())
    if native['version']!='19.0.'+version:raise ValueError('Reference native/package version mismatch')
    files={'plugin.toml':manifest_path.read_bytes()}
    for path in sorted(addon_dir.rglob('*')):
        if path.is_symlink():raise ValueError('No reference source links')
        if path.is_file() and '__pycache__' not in path.parts:files['backend/odoo_addons/'+addon+'/'+path.relative_to(addon_dir).as_posix()]=path.read_bytes()
    schemas={'documents-v1':'documents','documents-v2':'documents-v2','labels-input':'documents','boards':'boards','note-detail-actions':'note-detail-actions','notes-export-v1':'notes-export'}
    needed={item['schema'] for item in manifest['services']['provides']}
    needed.update(item['context_schema'] for item in manifest['ui'].get('slots',[]));needed.update(item['input_schema'] for item in manifest['ui'].get('commands',[]))
    if manifest['data'].get('export_schema'):needed.add(manifest['data']['export_schema'])
    for name in needed:
        if name not in {'schemas/'+key+'.json' for key in schemas}:raise ValueError('Unreviewed reference schema path')
        schema=json.loads((source/'packages/contracts/v1'/(schemas[Path(name).stem]+'.schema.json')).read_text())
        if Path(name).stem=='labels-input':schema['$ref']='#/$defs/labels_input'
        files[name]=(json.dumps(schema,indent=2)+'\n').encode()
    if plugin=='org.example.canvas':files['frontend/dist/canvas.js']=(addon_dir/'static/src/page.js').read_bytes()
    for name in ['LICENSE','COPYRIGHT']:files['notices/'+name]=(source/name).read_bytes()
    provenance={'schema_version':1,'builder':'repository-reference-assembler-v1','trusted_inputs_only':True,'source_files':{name:hashlib.sha256(value).hexdigest() for name,value in sorted(files.items())},'upstream_commit':'5c7defb49e020fec8b6bb82403a2f54eb79e92e1'}
    files['provenance.json']=(json.dumps(provenance,sort_keys=True,indent=2)+'\n').encode()
    inventory={'schema_version':1,'files':{name:hashlib.sha256(value).hexdigest() for name,value in sorted(files.items())},'excluded':['inventory.json']}
    files['inventory.json']=(json.dumps(inventory,sort_keys=True,indent=2)+'\n').encode()
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,value in sorted(files.items()):
            info=zipfile.ZipInfo(plugin+'/'+name,(2000,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(stat.S_IFREG|0o444)<<16;archive.writestr(info,value)
    raw=output.getvalue()
    return manifest,raw,files


def materialize_reference(source,manifest_path,staging):
    manifest,raw,files=assemble(source,manifest_path);plugin=manifest['plugin']['id'];addon=manifest['runtime']['addon_name'];prefix=plugin+'/backend/odoo_addons/'+addon+'/'
    # Verify/extract the archive bytes, rather than installing the original tree.
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        inventory=json.loads(archive.read(plugin+'/inventory.json'))
        for name,digest in inventory['files'].items():
            data=archive.read(plugin+'/'+name)
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Reference artifact inventory mismatch')
        for entry in archive.infolist():
            if entry.filename.startswith(prefix):
                relative=entry.filename[len(prefix):]
                if not relative or any(part in ['','..','.'] for part in relative.split('/')):raise ValueError('Unsafe reference path')
                target=staging/addon/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(entry))
    descriptor={'plugin_id':plugin,'version':manifest['plugin']['version'],'addon':addon,'digest':'sha256:'+hashlib.sha256(raw).hexdigest(),'file':plugin+'-'+manifest['plugin']['version']+'.mplug'}
    return descriptor,raw,staging/addon
