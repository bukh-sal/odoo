"""Fetch exact installed Alpine source recipes as data; never execute shell."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-proxy-source-notices-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
assert not PRIVATE.exists();protect_directory(PRIVATE)
packages=json.loads((OUT/'support-notice-coverage.json').read_text())['proxy']['packages']
origins={}
for package in packages:
    if package['source_commit']:
        origins.setdefault((package['origin'],package['source_commit']),[]).append(package)
assert len(origins)==53
def fetch(item):
    (origin,commit),members=item
    assert re.fullmatch('[a-z0-9+_.-]+',origin) and re.fullmatch('[0-9a-f]{40}',commit)
    attempts=[]
    for section in ['main','community']:
        url=f'https://raw.githubusercontent.com/alpinelinux/aports/{commit}/{section}/{origin}/APKBUILD'
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'modular-platform-local-notice-audit/1'}),timeout=25) as response:
                raw=response.read(1024*1024+1)
            assert len(raw)<=1024*1024
        except urllib.error.HTTPError as error:
            attempts.append(dict(url=url,status=error.code))
            if error.code==404:continue
            return dict(origin=origin,source_commit=commit,result='fetch_failed',attempts=attempts)
        except (TimeoutError,urllib.error.URLError) as error:
            attempts.append(dict(url=url,error=type(error).__name__))
            return dict(origin=origin,source_commit=commit,result='fetch_failed',attempts=attempts)
        path=PRIVATE/(origin+'-'+commit+'.APKBUILD');path.write_bytes(raw)
        text=raw.decode('utf8');values={}
        for key in ['pkgver','pkgrel','license','url']:
            match=re.search(r'^'+key+r'=(.*)$',text,re.M)
            values[key]=match.group(1).strip().strip('"\'') if match else None
        installed={package['version'] for package in members}
        declared=values['pkgver']+'-r'+values['pkgrel'] if values['pkgver'] and values['pkgrel'] else None
        attempts.append(dict(url=url,status=200))
        return dict(origin=origin,source_commit=commit,packages=[package['name'] for package in members],
            installed_versions=sorted(installed),declared=values,declared_version=declared,
            version_matches_literal=installed=={declared},url=url,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
            private_file=path.relative_to(ROOT).as_posix(),attempts=attempts,result='recipe_preserved_as_data')
    return dict(origin=origin,source_commit=commit,result='not_found_at_exact_commit',attempts=attempts)
with ThreadPoolExecutor(max_workers=6) as pool:records=list(pool.map(fetch,sorted(origins.items())))
report=dict(result='exact_proxy_source_recipes_collected_review_pending',origins=len(records),records=records,
    packages_without_aports_commit=[p for p in packages if not p['source_commit']],
    network_requests_contain_only_public_origin_commit_paths=True,shell_executed=False,
    limits=['Exact build recipes/license declarations and source URLs only; upstream license-text supplements still required.',
            'No APKBUILD source, installer, hooks, commands or downloaded metadata is executed. Nonliteral versions require manual source review.'])
with (OUT/'proxy-source-recipes.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],origins=len(records),fetched=sum(r['result']=='recipe_preserved_as_data' for r in records),
                     literal_version_matches=sum(r.get('version_matches_literal',False) for r in records))))
