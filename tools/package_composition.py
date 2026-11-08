"""Declarative ownership checks shared by examples and owned applications."""
import ast
import hashlib
import io
import tomllib
import zipfile
from packaging.specifiers import SpecifierSet
from packaging.version import Version


def validate_composition(artifacts):
    """Detect declarative model/field ownership conflicts without importing code.

    Static declarations supplement review; arbitrary dynamic trusted Python remains fully trusted.
    """
    from modular_platform.contracts import normalize_manifest,resolve_ui,ContractError
    parsed=[];owners={};models={}
    for raw in artifacts:
        archive=zipfile.ZipFile(io.BytesIO(raw));roots={name.split('/')[0] for name in archive.namelist()};assert len(roots)==1
        root=next(iter(roots));manifest=normalize_manifest(tomllib.loads(archive.read(root+'/plugin.toml').decode()));parsed.append((manifest,archive))
        for transition in manifest['upgrade']['transitions']:
            for script in transition['scripts']:
                path=root+'/backend/odoo_addons/'+manifest['runtime']['addon_name']+'/'+script['path']
                if path not in archive.namelist() or 'sha256:'+hashlib.sha256(archive.read(path)).hexdigest()!=script['digest']:
                    raise ContractError('Migration script digest mismatch')
    registry=resolve_ui([manifest for manifest,archive in parsed])
    for manifest,archive in parsed:
        if manifest['runtime']['kind']!='native':continue
        plugin=manifest['plugin']['id'];own=set(manifest['data']['models']);targets=set(manifest['data']['extension_targets'])
        declared={item['id'] for item in manifest['data']['contributions'] if item['kind']=='field'}
        prefix=plugin+'/backend/odoo_addons/'+manifest['runtime']['addon_name']+'/'
        for path in archive.namelist():
            if not path.startswith(prefix) or not path.endswith('.py'):continue
            for cls in (node for node in ast.walk(ast.parse(archive.read(path))) if isinstance(node,ast.ClassDef)):
                assignments={target.id:node.value for node in cls.body if isinstance(node,ast.Assign) for target in node.targets if isinstance(target,ast.Name)}
                values={}
                for key in ['_name','_inherit']:
                    if key in assignments:
                        try:values[key]=ast.literal_eval(assignments[key])
                        except (ValueError,TypeError):pass
                model=values.get('_name') or values.get('_inherit')
                if not isinstance(model,str):continue
                fields=[name for name,value in assignments.items() if isinstance(value,ast.Call) and isinstance(value.func,ast.Attribute) and isinstance(value.func.value,ast.Name) and value.func.value.id=='fields']
                if not fields:continue
                if '_name' in values:
                    if model not in own:raise ContractError('Undeclared native model')
                    if model in models and models[model]!=plugin:raise ContractError('Conflicting native model')
                    models[model]=plugin
                elif model not in targets:raise ContractError('Undeclared native extension target')
                for field in fields:
                    ident=model+'.'+field
                    if '_name' not in values and ident not in declared:raise ContractError('Undeclared native extension field')
                    if field in {'id','create_uid','write_uid','create_date','write_date','workspace_id'}:raise ContractError('Reserved native field override')
                    if ident in owners and owners[ident]!=plugin:raise ContractError('Conflicting declarative native field')
                    owners[ident]=plugin
        archive.close()
    return {'models':models,'fields':owners,'ui_contributions':[item['id'] for item in registry['contributions']]}


def validate_dependencies(package_manifests,native_manifests,framework_addons):
    """Bind native application edges to declared package/version dependencies."""
    from modular_platform.contracts import ContractError
    from modular_platform.resolution import dependency_order
    packages={item['plugin']['id']:item for item in package_manifests}
    if len(packages)!=len(package_manifests):raise ContractError('Duplicate application identity')
    addons={item['runtime']['addon_name']:ident for ident,item in packages.items()
            if item['runtime']['kind']=='native'}
    for ident,manifest in packages.items():
        required=manifest['dependencies']['plugins']
        for provider,specifier in required.items():
            if provider not in packages or Version(packages[provider]['plugin']['version']) not in SpecifierSet(specifier):
                raise ContractError('Missing or incompatible application package dependency')
        if manifest['runtime']['kind']!='native':continue
        for dependency in native_manifests[manifest['runtime']['addon_name']]['depends']:
            if dependency in addons:
                if addons[dependency] not in required:
                    raise ContractError('Native application dependency lacks a declared package edge')
            elif dependency not in framework_addons:
                raise ContractError('Native application dependency must be framework or packaged application')
    dependency_order({ident:list(item['dependencies']['plugins']) for ident,item in packages.items()})
