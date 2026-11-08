"""Package the qualified AP-03 app set and independent sources; never deploy."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'release'), str(ROOT/'tools'), str(ROOT/'packages/platform_sdk')]
from application_package import assemble_application
from modular_platform.deployment import inspect_image
from modular_platform.operator_os import protect_directory
from verify import verify, digest

FOUNDATION = '396054faa70542a167ac5cd5e309579270e030cfbe4bb22c155b08c7bd215404'
SOURCES = {
    'aurora-tasks': ('db32b467fb46156254e481900c0461430888b703', 'dev.aurora.tasks', '0.2.3'),
    'aurora-projects': ('1d801d6084b0004b4c7573f92b9447bd68406ef1', 'dev.aurora.projects', '0.1.1'),
    'aurora-projects-tasks': ('a79ed6049b21151bdafdb42966059d1da2852298', 'dev.aurora.projects_tasks', '0.1.1'),
}


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], timeout=180)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--foundation-kit', required=True, type=Path)
    p.add_argument('--inputs', required=True, type=Path, help='Reviewed application-adoption apps/artifacts/releases directory')
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args(); foundation = a.foundation_kit.resolve(); verify(foundation)
    assert digest(foundation/'kit-inventory.json') == FOUNDATION
    assert not git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'Commit tracked source before packaging'
    head = git(ROOT, 'rev-parse', 'HEAD').decode().strip()
    inputs = a.inputs.resolve(); output = a.output.absolute()
    assert not output.exists() and output.resolve().is_relative_to(ROOT/'.local/releases')
    decision = json.loads((ROOT/'docs/evidence/post-r1/application-adoption/ap03-release-decision.json').read_bytes())
    assert decision['result'] == 'passed' and decision['checks'] == ['AP-K', 'AP-L']
    target = inspect_image(decision['final_image']); assert target['inventory_digest'] == decision['final_inventory']
    baseline_receipt = json.loads((ROOT/'docs/evidence/post-r1/application-adoption/ap03-projects-tasks-010-01-image.json').read_bytes())
    baseline = inspect_image(baseline_receipt['image_id'])
    assert target['platform_version'] == baseline['platform_version'] == '0.1.49'
    # Verify independent source/bytes before creating a delivery directory.
    for name, (commit, plugin, version) in SOURCES.items():
        source = inputs/'apps'/name
        assert source.resolve().is_relative_to(inputs) and not source.is_symlink() and not source.is_junction()
        assert git(source, 'rev-parse', 'HEAD').decode().strip() == commit
        assert not git(source, 'status', '--porcelain').strip()
        manifest, raw, _ = assemble_application(source, 'application.toml')
        assert manifest['plugin']['id'] == plugin and manifest['plugin']['version'] == version
        assert 'sha256:'+hashlib.sha256(raw).hexdigest() == target['inventory']['artifacts'][plugin]['digest']
        assert raw == (inputs/'artifacts'/(plugin+'-'+version+'.mplug')).read_bytes()
    protect_directory(output)
    def copy(source, name):
        source = Path(source); destination = output/name
        assert source.is_file() and not source.is_symlink() and not source.is_junction()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as src, destination.open('xb') as dst:
            shutil.copyfileobj(src, dst)
        assert digest(source) == digest(destination)
    def write(name, value):
        destination = output/name; destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('x', encoding='utf8', newline='\n') as stream:
            stream.write(json.dumps(value, indent=2, sort_keys=True)+'\n')
    for folder in ('toolchain', 'notices'):
        for source in (foundation/folder).rglob('*'):
            if source.is_file(): copy(source, source.relative_to(foundation).as_posix())
    for name in ('verify.py', 'setup_operator.py'):
        copy(ROOT/'release'/name, 'scripts/'+name)
    subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=zip', '--output', str(output/'source.zip'), head], check=True, timeout=180)
    with zipfile.ZipFile(output/'source.zip') as archive:
        assert archive.comment.decode() == head
        assert not any('/.local/' in '/'+name or name.startswith('.git/') for name in archive.namelist())
    source_rows = {}
    for name, (commit, plugin, version) in SOURCES.items():
        path = output/'applications'/name; path.mkdir(parents=True)
        git(inputs/'apps'/name, 'bundle', 'create', str(path/'source.bundle'), '--all')
        source_rows[name] = dict(commit=commit, plugin_id=plugin, version=version, bundle='applications/'+name+'/source.bundle')
    recipes = {}
    for name in ('projects-0.1.0', 'projects-tasks-0.1.0', 'projects-tasks-0.1.1-fixed'):
        recipe_root = inputs/'releases'/name; recipe = tomllib.loads((recipe_root/'release.toml').read_text(encoding='utf8'))
        assert recipe['foundation']['kit_manifest'] == 'sha256:'+FOUNDATION
        copy(recipe_root/'release.toml', 'releases/'+name+'/release.toml')
        for row in recipe['applications']:
            path = Path(row['artifact'])
            assert not path.is_absolute() and '..' not in path.parts
            artifact = recipe_root/path; assert 'sha256:'+digest(artifact) == row['digest']
            copy(artifact, 'releases/'+name+'/'+path.as_posix())
        recipes[name] = 'releases/'+name+'/release.toml'
    final_artifacts = target['inventory']['artifacts']
    for plugin, row in sorted(final_artifacts.items()):
        destination = output/'plugins'/row['file']; destination.parent.mkdir(parents=True, exist_ok=True)
        raw = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', '/bin/cat', decision['final_image'], '/opt/modular/artifacts/'+row['file']], timeout=30)
        assert 'sha256:'+hashlib.sha256(raw).hexdigest() == row['digest']
        with destination.open('xb') as stream: stream.write(raw)
    write('plugins/curated-trust.json', dict(schema_version=1, mode='curated', generation=1,
        allow_unsigned_development=False, approved_digests=sorted(r['digest'] for r in final_artifacts.values())))
    original_images = json.loads((foundation/'images.json').read_bytes())
    images = dict(images={k:v for k,v in original_images['images'].items() if k in ('postgres','proxy')},
                  application_inventory_digest=target['inventory_digest'])
    images['images'].update(application=dict(image_id=decision['final_image']), recovery_baseline=dict(image_id=baseline_receipt['image_id']))
    write('images.json', images)
    subprocess.run(['docker', 'image', 'save', '--output', str(output/'images.tar'), *[r['image_id'] for r in images['images'].values()]], check=True, timeout=240)
    write('application-sources.json', source_rows)
    write('release-recipes.json', recipes)
    copy(ROOT/'docs/evidence/post-r1/application-adoption/ap03-release-decision.json', 'qualification/ap03-release-decision.json')
    write('foundation-prerequisite.json', dict(kit_manifest='sha256:'+FOUNDATION,
        requirement='Original sealed core49 kit is needed only to recompose images; no mutation or duplication of its inventory',
        current_host_operator='Use this kit source: it includes ADR0079 native-job recovery correction',
        recovery_baseline='Historical0.1.0integration has known debug-error disclosure;use final0.1.1 for new application work'))
    files = {p.relative_to(output).as_posix(): dict(bytes=p.stat().st_size, sha256=digest(p)) for p in output.rglob('*') if p.is_file()}
    manifest = dict(format='modular-platform-local-kit-1', stage='qualified_local_application_set_ap03', source_commit=head,
        created_utc=datetime.now(timezone.utc).isoformat(), platform_version='0.1.49', files=files,
        qualification='AP03 app set qualified;AP04 clean workflow/final delivery is a separate decision bound to these exact checksums')
    write('kit-inventory.json', manifest)
    checksums = dict((name,row['sha256']) for name,row in files.items()); checksums['kit-inventory.json'] = digest(output/'kit-inventory.json')
    (output/'SHA256SUMS').write_text(''.join(value+'  '+name+'\n' for name,value in sorted(checksums.items())), encoding='utf8', newline='\n')
    verify(output)
    print(json.dumps(dict(result='assembled_verified_application_set_not_deployed', source_commit=head,
        manifest='sha256:'+digest(output/'kit-inventory.json'), files=len(files), image_id=decision['final_image'])))


if __name__ == '__main__':
    main()
