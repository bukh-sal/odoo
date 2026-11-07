"""Check owned source CLI/discovery in the pinned native environment, no DB."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--attempt', default='01')
    args = parser.parse_args()
    assert re.fullmatch('sha256:[a-f0-9]{64}', args.image)
    assert not args.output.exists()
    assert re.fullmatch('[0-9]{2}', args.attempt)
    private=ROOT/'.local/addon-cleanup'/('source-probe-'+args.attempt)
    assert not private.exists(), 'Read existing diagnostics before a new attempt'
    private.mkdir()
    def run(arguments, label):
        result=subprocess.run(arguments,capture_output=True,timeout=120)
        (private/(label+'.stdout')).write_bytes(result.stdout)
        (private/(label+'.stderr')).write_bytes(result.stderr)
        assert result.returncode==0, 'Inspect private source-probe '+label+' diagnostic'
        return result
    mounts = []
    for name in ('engine', 'framework_addons', 'applications', 'examples', 'packages/platform_sdk'):
        source = (ROOT / name).resolve()
        assert source.is_relative_to(ROOT) and source.is_dir()
        mounts += ['--mount', 'type=bind,source=' + str(source) + ',target=/workspace/' + name + ',readonly']
    command = ['docker', 'run', '--rm', '--name', 'mp-ar03-source-probe', '--label',
        'com.modular.disposable=mp-ar03-source-probe', '--network', 'none', '--read-only',
        '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--tmpfs', '/tmp', '--workdir', '/tmp', '--env',
        'PYTHONPATH=/workspace/engine:/workspace/packages/platform_sdk', *mounts,
        '--entrypoint', '/venv/bin/python', args.image]
    help_result = run(command + ['/workspace/engine/odoo-bin', '--config=/dev/null', '--help'], 'help')
    assert b'--addons-path' in help_result.stdout
    code = '''
import json,hashlib
from pathlib import Path
import odoo.init
import odoo.addons
from odoo.tools import config
from odoo.modules.module import initialize_sys_path,get_module_path
from modular_platform.native_versions import TARGET_SHA256
config.parse_config(['--config=/dev/null','--data-dir=/tmp/source-data'])
initialize_sys_path()
assert config.root_path == '/workspace/engine/odoo', config.root_path
assert config.owned_source_root == '/workspace'
expected={'base':'framework_addons/base','web':'framework_addons/web',
          'mp_aurora_tasks':'applications/mp_aurora_tasks','maintenance':'applications/maintenance',
          'mp_example_canvas':'examples/mp_example_canvas'}
for name,path in expected.items():
    assert get_module_path(name) == '/workspace/'+path,(name,get_module_path(name))
for name in ['iap','account','sale','rpc','test_orm','mp_feas']:
    assert not get_module_path(name,display_warning=False),name
assert hashlib.sha256(Path(config.root_path,'tools/parse_version.py').read_bytes()).hexdigest()==TARGET_SHA256
print('MP_AR_SOURCE='+json.dumps(dict(roots=expected,test_and_retired_addons_not_discovered=True,
    owned_engine_parser=True,source_root=config.owned_source_root)))
'''
    result = run(command + ['-c', code], 'discovery')
    rows = [json.loads(line.split('=', 1)[1]) for line in result.stdout.decode().splitlines()
            if line.startswith('MP_AR_SOURCE=')]
    assert len(rows) == 1
    record = dict(result='passed', image=args.image, source_cli_help=True,
                  help_sha256=hashlib.sha256(help_result.stdout).hexdigest(), **rows[0],
                  network='none',database_created=False,source_mounts_readonly=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
