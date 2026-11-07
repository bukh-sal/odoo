"""Static retained-addon ownership/reference audit; does not import addon code."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    policy = json.loads((ROOT / 'deploy/distribution-r1-foundation.json').read_bytes())
    selected = set(policy['addons'])
    modules = {}
    for folder in ('addons', 'odoo/addons', 'platform_addons'):
        for path in sorted((ROOT / folder).glob('*/__manifest__.py')):
            manifest = ast.literal_eval(path.read_text(encoding='utf8'))
            name = path.parent.name
            assert name not in modules
            if folder == 'odoo/addons' and name != 'base' or name == 'mp_feas':
                disposition, target = 'test', 'tests/addons/' + name
            elif name not in selected:
                disposition, target = 'remove', None
            elif name in ('maintenance', 'mp_aurora_tasks'):
                disposition, target = 'application', 'applications/' + name
            elif name.startswith('mp_example_'):
                disposition, target = 'example', 'examples/' + name
            else:
                disposition, target = 'framework', 'framework_addons/' + name
            if name == 'iap':
                disposition, target = 'extract_then_remove', None
            modules[name] = dict(source=path.parent.relative_to(ROOT).as_posix(), target=target,
                disposition=disposition, shipped=name in selected,
                manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                depends=manifest.get('depends', []), auto_install=manifest.get('auto_install', False),
                license=manifest.get('license', 'unspecified'))
    references = []
    scan_roots = [ROOT / 'odoo'] + [ROOT / row['source'] for name, row in modules.items()
                  if row['shipped'] and not row['source'].startswith('odoo/')]
    visited = set()
    for folder in scan_roots:
        for path in folder.rglob('*'):
            if (not path.is_file() or path.suffix not in {'.py', '.js', '.xml', '.scss'}
                    or '__pycache__' in path.parts or path in visited):
                continue
            visited.add(path)
            relative = path.relative_to(ROOT).as_posix()
            data = path.read_text(encoding='utf8', errors='replace')
            for kind, pattern in (
                ('python_addon', r'odoo\.addons\.([a-zA-Z0-9_]+)'),
                ('javascript_addon', r'@([a-zA-Z0-9_]+)/'),
                ('asset', r'[\"\x27]([a-zA-Z0-9_]+)/static/'),
                ('xml_reference', r'(?:ref|inherit_id)=[\"\x27]([a-zA-Z0-9_]+)\.'),
            ):
                for match in re.finditer(pattern, data):
                    name = match.group(1)
                    if name in modules and name not in selected:
                        references.append(dict(path=relative, line=data.count('\n', 0, match.start()) + 1,
                            kind=kind, target=name, test='/tests/' in relative or '/test_' in relative,
                            disposition=modules[name]['disposition']))
    result = dict(result='audited_not_yet_pruned', utc=datetime.now(timezone.utc).isoformat(),
        source_roots=dict(engine='engine/odoo', launcher='engine/odoo-bin'),
        modules=modules, references_to_unshipped=references,
        counts={kind: sum(row['disposition'] == kind for row in modules.values())
                for kind in ('framework', 'application', 'example', 'test', 'remove', 'extract_then_remove')},
        limitations=['Static references require classification; optional model hooks and dynamic lookups need native tests.',
                    'Framework mail conversation models/widgets are services; full app entry points/gateway polling must be optional.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(result=result['result'], counts=result['counts'], references=len(references))))


if __name__ == '__main__':
    main()
