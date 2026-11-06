"""Compare independent stock application and RTL compiler builds."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.deployment import inspect_image


def compiler(image):
    command = ['docker', 'run', '--rm', '--network', 'none', '--read-only',
               '--entrypoint', '/venv/bin/python', image, '-c']
    script = '''
import hashlib, json, pathlib, resource, subprocess
root = pathlib.Path('/opt/stock-rtl')
files = [pathlib.Path('/usr/local/bin/node'), pathlib.Path('/usr/local/bin/rtlcss'), *root.rglob('*')]
result = {}
for path in sorted(files):
    if path.is_symlink():
        result[str(path)] = str(path.readlink())
    elif path.is_file():
        result[str(path)] = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
config = '/opt/modular/odoo/addons/base/data/rtlcss.json'
node = subprocess.check_output(['node', '--version'], text=True).strip()
resource.setrlimit(resource.RLIMIT_AS, (671088640, resource.RLIM_INFINITY))
probe = subprocess.check_output(['rtlcss', '-c', config, '-'],
    input=b'.probe{direction:ltr;margin-left:1px}')
assert b'direction:rtl' in probe and b'margin-right:1px' in probe
print(json.dumps(dict(files=result, probe=probe.decode(),
    node=node, address_space_limit=671088640,
    rtlcss=subprocess.check_output(['rtlcss', '--version'], text=True).strip())))
'''
    return json.loads(subprocess.check_output(command + [script], timeout=75))


def translations(image):
    script = '''
import hashlib, json
from odoo.tools.translate import PoFileReader
result = {}
for addon, count in (('mp_identity', 6), ('mp_shell', 7)):
    path = '/opt/modular/addons/' + addon + '/i18n/ar.po'
    entries = list(PoFileReader(path))
    assert len(entries) == count
    assert all(row['module'] == addon and row['type'] == 'code'
        and row['comments'] == 'odoo-javascript' and row['value'] for row in entries)
    result[addon] = {'entries': count, 'sha256': hashlib.file_digest(open(path, 'rb'), 'sha256').hexdigest()}
print(json.dumps(result))
'''
    command = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp',
               '--entrypoint', '/venv/bin/python', image, '-c', script]
    return json.loads(subprocess.check_output(command, timeout=30))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first_build', type=Path)
    parser.add_argument('second_build', type=Path)
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    first = json.loads(args.first_build.read_bytes())
    second = json.loads(args.second_build.read_bytes())
    assert first['git_base'] == second['git_base'] and first['source_sha256'] == second['source_sha256']
    assert '--network=none' in second['command'] and '--no-cache' in second['command']
    assert first['dependency_base_image'] != second['dependency_base_image']
    runtimes = [inspect_image(build['image_id']) for build in (first, second)]
    keys = ('inventory_digest', 'inventory', 'python', 'architecture', 'markers',
            'python_lock_digest', 'python_metadata', 'modified_files', 'unexpected_addon_files', 'missing_addon_files')
    comparisons = {key: runtimes[0][key] == runtimes[1][key] for key in keys}
    assert all(comparisons.values())
    records = [compiler(build[key]) for build in (first, second) for key in ('dependency_base_image', 'image_id')]
    assert all(record == records[0] for record in records)
    lockfile = ROOT / 'deploy/stock-rtl/package-lock.json'
    assert records[0]['files']['/opt/stock-rtl/package-lock.json'] == hashlib.sha256(lockfile.read_bytes()).hexdigest()
    translated = [translations(build['image_id']) for build in (first, second)]
    assert translated[0] == translated[1]
    receipt = dict(result='passed_second_no_cache_build_declared_inventory_reproduction', acceptance=['BOOT-02'],
                   reference_image=first['image_id'], candidate_image=second['image_id'],
                   dependency_base=first['dependency_base_image'], inventory_digest=first['inventory_digest'],
                   comparisons=comparisons, source_commit=first['git_base'], command=second['command'],
                   independently_rebuilt_rtl_base=second['dependency_base_image'], compiler=records[0],
                   odoo_arabic_translations=translated[0])
    with args.receipt.open('x', encoding='utf-8') as output:
        json.dump(receipt, output, indent=2)
        output.write('\n')
    print(json.dumps({'result': receipt['result'], 'image': first['image_id'], 'rtl_files': len(records[0]['files'])}))


if __name__ == '__main__':
    main()
