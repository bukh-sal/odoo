"""Validate operator-selected build/reproduction inputs before kit assembly."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

COMPARISONS=('inventory_digest','inventory','python','architecture','markers',
             'python_lock_digest','python_metadata','modified_files',
             'unexpected_addon_files','missing_addon_files')


def load_application_inputs(root, reproduction_path, build_path):
    root=Path(root).resolve()
    documents=[]
    for path in [Path(reproduction_path),Path(build_path)]:
        if path.stat().st_size>4*1024*1024:raise ValueError('Oversized release input receipt')
        raw=path.read_bytes()
        def pairs(items):
            result={}
            for key,value in items:
                if key in result:raise ValueError('Duplicate release input field')
                result[key]=value
            return result
        document=json.loads(raw,object_pairs_hook=pairs)
        if not isinstance(document,dict):raise ValueError('Release input receipt must be an object')
        documents.append((document,raw))
    (reproduction,repro_raw),(build,build_raw)=documents
    if (reproduction.get('result')!='passed_second_no_cache_build_declared_inventory_reproduction'
            or 'BOOT-02' not in reproduction.get('acceptance',[])
            or any(reproduction.get('comparisons',{}).get(key) is not True for key in COMPARISONS)):
        raise ValueError('Complete passed application reproduction required')
    for key in ['reference_image','candidate_image','dependency_base','inventory_digest']:
        if not isinstance(reproduction.get(key),str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',reproduction[key]):
            raise ValueError('Immutable application reproduction identity required')
    if (build.get('state')!='built' or build.get('result')!='built_not_deployed'
            or build.get('image_id')!=reproduction['reference_image']
            or build.get('inventory_digest')!=reproduction['inventory_digest']
            or build.get('dependency_base_image')!=reproduction['dependency_base']):
        raise ValueError('Build/reproduction identities disagree')
    source=build.get('source_sha256')
    if not isinstance(source,dict) or not source:raise ValueError('Recorded build source inputs required')
    expected={path.relative_to(root).as_posix()
              for directory in ['platform_addons','plugins','packages/contracts','packages/platform_sdk','deploy','tools']
              for path in (root/directory).rglob('*')
              if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc'}
    expected.update(['.dockerignore','LICENSE','COPYRIGHT'])
    if set(source)!=expected:raise ValueError('Checkout/build source input set differs')
    for name,value in source.items():
        if not isinstance(name,str):raise ValueError('Invalid build source path')
        pure=PurePosixPath(name)
        if (pure.is_absolute() or '..' in pure.parts or '\\' in name or ':' in name
                or pure.as_posix()!=name or not isinstance(value,str)
                or not re.fullmatch(r'[0-9a-f]{64}',value)):
            raise ValueError('Invalid build source identity')
        path=root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Linked build source input')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=value:
            raise ValueError('Checkout differs from selected build input: '+name)
    return dict(reproduction=reproduction,build=build,reproduction_bytes=repro_raw,build_bytes=build_raw,
                reproduction_sha256=hashlib.sha256(repro_raw).hexdigest(),
                build_sha256=hashlib.sha256(build_raw).hexdigest(),source_files_verified=len(source))
