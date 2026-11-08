"""Finite adoption delivery audit; emits counts/locations, never credential values."""
import argparse
import configparser
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'release')]
from secret_scan import Scanner
from verify import verify, digest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit', required=True, type=Path)
    p.add_argument('--workdir', required=True, type=Path)
    p.add_argument('--credential-root', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args(); manifest = verify(a.kit); assert not a.output.exists()
    setup = json.loads((a.workdir/'operator-setup.json').read_text(encoding='utf8'))
    assert setup['source_commit'] == manifest['source_commit']
    source = Path(setup['source']); known = {}; configs = 0
    for index, path in enumerate(a.credential_root.rglob('account-passwords.json')):
        values = json.loads(path.read_text(encoding='utf8'))
        for actor, value in values.items():
            assert isinstance(value, str) and len(value) >= 16
            known['account-file-'+str(index)+'/'+actor] = value.encode()
        configs += 1
    for index, path in enumerate(a.credential_root.rglob('odoo.conf')):
        config = configparser.ConfigParser(interpolation=None); config.read(path, encoding='utf8')
        if not config.has_section('options'): continue
        for key in ('db_password', 'admin_passwd'):
            value = config.get('options', key, fallback='')
            if len(value) >= 16: known['native-config-'+str(index)+'/'+key] = value.encode()
    assert known
    scanner = Scanner(secrets.token_bytes(32), known)
    # Full substrate contains deliberate credential test literals. Scope this
    # pass to actual generated adoption credentials and their encoded variants.
    scanner.generic = {}
    findings = []; files = 0
    with zipfile.ZipFile(a.kit/'source.zip') as archive:
        assert archive.comment.decode() == manifest['source_commit']
        for member in archive.infolist():
            if member.is_dir(): continue
            name = member.filename
            assert not any(part in {'.local', '.git'} for part in Path(name).parts)
            assert name not in {'account-passwords.json', 'odoo.conf', '.env'}
            path = source/name
            assert path.is_file() and path.read_bytes() == archive.read(member)
            findings += scanner.inspect_file(path, 'source/'+name); files += 1
    members = 0
    for path in sorted((a.kit/'releases').rglob('*.mplug')):
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir(): continue
                findings += scanner.inspect_bytes(archive.read(member), 'release/'+path.name+'/'+member.filename)
                members += 1
    generic = Scanner(secrets.token_bytes(32), {})
    history_blobs = 0; current_files = 0
    for repo in sorted((a.workdir/'independent apps').iterdir()):
        if repo.name.endswith('-baseline'): continue
        assert not subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain']).strip()
        names = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z']).split(b'\0')
        for raw in names:
            if not raw: continue
            name = raw.decode(); path = repo/name
            findings += generic.inspect_file(path, 'app/'+repo.name+'/'+name)
            findings += scanner.inspect_file(path, 'app/'+repo.name+'/'+name); current_files += 1
        objects = subprocess.check_output(['git', '-C', str(repo), 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype)']).decode().splitlines()
        for row in objects:
            sha, kind = row.split()
            if kind != 'blob': continue
            raw = subprocess.check_output(['git', '-C', str(repo), 'cat-file', 'blob', sha])
            findings += generic.inspect_bytes(raw, 'app-history/'+repo.name+'/'+sha)
            findings += scanner.inspect_bytes(raw, 'app-history/'+repo.name+'/'+sha); history_blobs += 1
    result = dict(result='passed' if not findings else 'failed', kit_manifest='sha256:'+digest(a.kit/'kit-inventory.json'),
        source_commit=manifest['source_commit'], source_files=files, archive_members=members,
        current_app_files=current_files, app_history_blobs=history_blobs,
        generated_credential_values=len(known), account_files=configs, findings=findings,
        bounds=['Known generated adoption credentials plus encoded variants checked against delivered source/selected archives/app history',
                'Generic structural credential patterns additionally checked against current app files and all bundled app Git blobs',
                'Not a claim to detect every unknown secret or audit the whole original substrate Git history',
                'Final image retains sealed foundation bytes;selected app source/archives and derived inventory/policy are the qualified delta;no live database/config/filestore is exported'])
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k!='findings'}))
    assert not findings, 'Inspect redacted findings before proceeding'


if __name__ == '__main__':
    main()
