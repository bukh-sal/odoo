"""Try canonical Alpine repositories for the exact absent mirror commit only."""
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-proxy-source-notices-01'
record=json.loads((OUT/'proxy-source-recipes.json').read_text())
row=next(row for row in record['records'] if row['origin']=='expat')
assert row['result']=='not_found_at_exact_commit';commit=row['source_commit']
urls=[f'https://gitlab.alpinelinux.org/alpine/aports/-/raw/{commit}/main/expat/APKBUILD',
      f'https://git.alpinelinux.org/aports/plain/main/expat/APKBUILD?id={commit}']
attempts=[];found=None
for n,url in enumerate(urls):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'modular-platform-local-notice-audit/1'}),timeout=25) as response:
            raw=response.read(1024*1024+1);status=response.status;final=response.geturl()
        assert len(raw)<=1024*1024
        path=PRIVATE/f'expat-canonical-{n}.raw';assert not path.exists();path.write_bytes(raw)
        valid=b'pkgname=expat\n' in raw and b'pkgver=2.10.0\n' in raw and b'pkgrel=0\n' in raw
        attempts.append(dict(url=url,final_url=final,status=status,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),recipe=valid))
        if valid:found=dict(url=url,sha256=hashlib.sha256(raw).hexdigest(),private_file=path.relative_to(ROOT).as_posix());break
    except urllib.error.HTTPError as error:attempts.append(dict(url=url,status=error.code))
    except (TimeoutError,urllib.error.URLError) as error:attempts.append(dict(url=url,error=type(error).__name__))
result=dict(result='exact_expat_canonical_recipe_preserved' if found else 'exact_expat_canonical_recipe_unavailable',
            source_commit=commit,found=found,attempts=attempts,moving_revision_used=False,shell_executed=False)
with (OUT/'expat-canonical-recipe.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],attempts=len(attempts))))
