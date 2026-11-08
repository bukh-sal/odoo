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
import sys
import tomllib
import zipfile


def toml_value(value):
    if isinstance(value,str):return json.dumps(value,ensure_ascii=False)
    if isinstance(value,bool):return str(value).lower()
    if isinstance(value,int):return str(value)
    if isinstance(value,list):return '['+', '.join(map(toml_value,value))+']'
    if isinstance(value,dict):return '{'+', '.join(json.dumps(key)+' = '+toml_value(item) for key,item in value.items())+'}'
    raise ValueError('Unsupported reference TOML value')


def _finish_archive(source,manifest,files):
    from package_archive import finish_archive
    files=dict(files)
    for name in ['LICENSE','COPYRIGHT']:files['notices/'+name]=(source/name).read_bytes()
    return finish_archive(manifest,files,builder='repository-reference-assembler-v1',
                          provenance_extra={'upstream_commit':'5c7defb49e020fec8b6bb82403a2f54eb79e92e1'})


def assemble(source,manifest_path):
    manifest_path=(source/manifest_path).resolve()
    if not manifest_path.is_relative_to(source/'plugins'):raise ValueError('Reference manifests must be repository plugin inputs')
    sys.path.insert(0,str(source/'packages/platform_sdk'))
    from modular_platform.contracts import normalize_manifest
    manifest=normalize_manifest(tomllib.loads(manifest_path.read_text()));plugin=manifest['plugin']['id'];version=manifest['plugin']['version']
    if manifest['runtime']['kind']=='external_service':
        if plugin!='org.example.document_stats' or manifest_path!=source/'plugins/document_stats/plugin.toml':raise ValueError('Unsupported external reference package')
        if manifest['services']['provides']!=[dict(id='org.example.document_stats.analysis',api_version='1.0',schema='schemas/stats-v1.json',methods=['analyze'])]:raise ValueError('Explicit reference worker contract required')
        schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$defs':{name:json.loads((source/'packages/contracts/v1'/('worker-'+name+'.schema.json')).read_text()) for name in ['request','response']}}
        return _finish_archive(source,manifest,{'plugin.toml':manifest_path.read_bytes(),'schemas/stats-v1.json':(json.dumps(schema,indent=2)+'\n').encode()})
    addon=manifest['runtime']['addon_name']
    if plugin not in ['org.example.notes','org.example.notes_labels','org.example.canvas','org.example.notes_stats','org.example.background'] or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',version):raise ValueError('Not an allowlisted reference package')
    if addon not in ['mp_example_notes','mp_example_notes_labels','mp_example_canvas','mp_example_notes_stats','mp_example_background']:raise ValueError('Unsupported reference addon')
    from source_layout import addon_source
    addon_dir=addon_source(source,addon)
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
        if (plugin,name) in {('org.example.notes_stats','schemas/analysis-v1.json'),
                            ('org.example.background','schemas/authority-v1.json')}:
            path=manifest_path.parent/name
            if path.is_symlink():raise ValueError('No reference schema links')
            files[name]=path.read_bytes()
            continue
        if name not in {'schemas/'+key+'.json' for key in schemas}:raise ValueError('Unreviewed reference schema path')
        schema=json.loads((source/'packages/contracts/v1'/(schemas[Path(name).stem]+'.schema.json')).read_text())
        if Path(name).stem=='labels-input':schema['$ref']='#/$defs/labels_input'
        files[name]=(json.dumps(schema,indent=2)+'\n').encode()
    if plugin=='org.example.canvas':files['frontend/dist/canvas.js']=(addon_dir/'static/src/page.js').read_bytes()
    return _finish_archive(source,manifest,files)


def materialize_reference(source,manifest_path,staging):
    manifest,raw,files=assemble(source,manifest_path)
    if manifest['runtime']['kind']!='native':raise ValueError('External metadata cannot materialize a native addon')
    plugin=manifest['plugin']['id'];addon=manifest['runtime']['addon_name'];prefix=plugin+'/backend/odoo_addons/'+addon+'/'
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


def validate_reference_composition(artifacts):
    # Historical authoring entry point; the ownership checks are generic.
    from package_composition import validate_composition
    return validate_composition(artifacts)
