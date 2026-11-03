"""Host-only build of the locked proxy from retained APK inputs.

Use the APK archive accompanying the local R1 release kit. Docker verifies the
normal Alpine signatures during the offline install; this tool verifies the
complete input set before invoking Docker. No credentials or runtime volumes.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def context_bytes(archive_path):
    lock_path = ROOT / 'deploy/proxy-packages.lock.json'
    lock = json.loads(lock_path.read_text(encoding='utf8'))
    recipe = (ROOT / 'deploy/proxy.Dockerfile').read_bytes()
    if hashlib.sha256(recipe).hexdigest() != lock['recipe_sha256']:
        raise ValueError('Proxy recipe differs from the reviewed package lock')
    if archive_path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Proxy APK archive exceeds the bounded input size')
    expected = {row['file']: row for row in lock['packages']}
    if len(expected) != len(lock['packages']):
        raise ValueError('Duplicate APK name in lock')
    payloads = {}
    with tarfile.open(archive_path, 'r:') as archive:
        for member in archive:
            if member.isdir() and member.name in ('.', './'):
                continue
            name = member.name.removeprefix('./')
            if (not member.isfile() or name not in expected or name in payloads
                    or member.size != expected[name]['bytes']):
                raise ValueError('Unexpected, duplicate or incorrectly sized APK input')
            data = archive.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != expected[name]['sha256']:
                raise ValueError('APK bytes differ from the reviewed package lock')
            payloads[name] = data
    if payloads.keys() != expected.keys():
        raise ValueError('APK archive is incomplete')
    files = {'Dockerfile': recipe, 'proxy-packages.lock.json': lock_path.read_bytes()}
    sums = []
    for row in lock['packages']:
        files['apks/' + row['file']] = payloads[row['file']]
        sums.append(row['sha256'] + '  ' + row['file'])
    files['SHA256SUMS'] = ('\n'.join(sums) + '\n').encode()
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode='w') as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    return result.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New project-owned build record directory')
    parser.add_argument('--tag', default='modular-platform-proxy:r1-local')
    parser.add_argument('--prepare-only', action='store_true',
                        help='Validate inputs and write context without creating an image')
    args = parser.parse_args()
    if not args.tag.startswith('modular-platform-proxy:'):
        parser.error('Use a project-owned modular-platform-proxy tag')
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error('Build output must be a new directory inside this project')
    if not args.prepare_only:
        existing = subprocess.run(['docker', 'image', 'inspect', args.tag],
                                  capture_output=True)
        if existing.returncode == 0:
            parser.error('Existing image tag retained; select a new project-owned tag')
    context = context_bytes(args.apk_archive.resolve())
    output.mkdir(parents=True)
    (output / 'context.tar').write_bytes(context)
    record = {'context_sha256': hashlib.sha256(context).hexdigest(),
              'package_lock_sha256': hashlib.sha256(
                  (ROOT / 'deploy/proxy-packages.lock.json').read_bytes()).hexdigest(),
              'network': 'none', 'tag': args.tag, 'result': 'prepared_only'}
    if not args.prepare_only:
        command = ['docker', 'build', '--network', 'none', '--pull=false',
                   '--label', 'com.modular.disposable=mp-r1-proxy-build',
                   '--tag', args.tag, '-']
        with (output / 'build.stdout').open('xb') as stdout, (output / 'build.stderr').open('xb') as stderr:
            result = subprocess.run(command, input=context, stdout=stdout, stderr=stderr)
        if result.returncode:
            record.update(result='build_failed', exit_code=result.returncode)
            (output / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
            raise RuntimeError('Proxy build failed; inspect retained logs before retrying')
        meta = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.tag]))[0]
        record.update(result='built_requires_inventory_and_ingress_qualification', image_id=meta['Id'])
    (output / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
