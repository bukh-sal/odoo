"""Complete per-package notice/source mapping and exact companion-byte verification."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path.cwd();OUT=Path(__file__).parent
def load(path):return json.loads(path.read_bytes())
def sha(raw):return hashlib.sha256(raw).hexdigest()
support=load(OUT/'support-notice-coverage.json');packages=support['proxy']['packages']
primary=load(OUT/'proxy-source-notices.json');recipes=load(OUT/'proxy-source-recipes.json')
extras=load(OUT/'proxy-notice-extras.json');inline=load(OUT/'proxy-inline-notices.json')
libyuv=load(OUT/'libyuv-content-binding.json');expat=load(OUT/'expat-upstream-notice.json')
assert all(row['result']=='verified_source_file' for row in inline['source_files'])
origins={}
for package in packages:origins.setdefault(package['origin'],[]).append(package)
assert len(origins)==59
rows=[];blob_paths=set()
for origin,members in sorted(origins.items()):
    if not members[0]['source_commit']:
        path='usr/share/licenses/'+origin+'/COPYRIGHT'
        notice=next(row for row in support['proxy']['shipped_documents'] if row['path']==path)
        rows.append(dict(origin=origin,packages=[row['name'] for row in members],
            disposition='actual_image_notice_preserved',notice_archive='.local/g7-image-secret-audit-01/proxy-documentation.zip',
            notices=[notice]));continue
    recipe=next(row for row in recipes['records'] if row['origin']==origin)
    source=next(row for row in primary['records'] if row['origin']==origin)
    row=dict(origin=origin,packages=[row['name'] for row in members],installed_versions=sorted({p['version'] for p in members}),
             declared_licenses=sorted({p['license'] for p in members}),Alpine_source_commit=members[0]['source_commit'],notices=[])
    if recipe['result']=='recipe_preserved_as_data':
        assert sha((ROOT/recipe['private_file']).read_bytes())==recipe['sha256'] and recipe['version_matches_literal']
        row['recipe']=dict(url=recipe['url'],sha256=recipe['sha256'],private_file=recipe['private_file'])
    if source['result']=='verified_primary_source_notices_preserved':
        row.update(disposition='checksum_verified_primary_source_notices',source_archive=source['source_archive'],
                   source_url=source['source_url'],source_sha512=source['source_sha512'],notices=source['notices'])
    elif origin=='libyuv':
        row.update(disposition='recipe_prescribed_source_content_digest',source_commit=libyuv['source_commit'],
                   source_content_sha512=libyuv['actual_content_sha512'],notices=libyuv['notices'])
    elif origin=='expat':
        row.update(disposition='exact_upstream_release_notice_packaging_recipe_transport_unavailable',
            upstream_commit=expat['upstream_commit'],notices=[expat['notice']],
            limitation=expat['unresolved_recipe_transport'])
    elif origin=='ca-certificates':
        row.update(disposition='checksum_verified_source_embedded_attribution',source_archive=source['source_archive'],
                   source_url=source['source_url'],source_sha512=source['source_sha512'])
    elif origin in {'alpine-base','alpine-baselayout','alpine-keys'}:
        preserved=next(value for value in inline['origins'] if value['origin']==origin)
        assert preserved['result'] in {'declared_source_files_verified','recipe_contains_generated_release_metadata_only'}
        row.update(disposition='furnished_recipe_metadata_source_and_embedded_attribution_no_standalone_notice',
            source_files=[value for value in inline['source_files'] if value['origin']==origin],
            note=preserved['note'])
    else:raise AssertionError((origin,source['result']))
    row['notices'].extend(value for value in inline['preserved_inline_attribution_sources'] if value['origin']==origin)
    row['additional_sources']=[value for value in extras['additional_source_archives'] if value['origin']==origin]
    for extra in row['additional_sources']:
        assert extra['result'] in {'verified_additional_source_notices_preserved','verified_additional_source_no_standalone_notice'}
        row['notices'].extend(extra['notices'])
    row['notices'].extend(value for value in extras['referenced_license_files'] if value['origin']==origin)
    for notice in row['notices']:
        path=ROOT/notice['path'];raw=path.read_bytes();assert sha(raw)==notice['sha256'] and len(raw)==notice['bytes']
        blob_paths.add(notice['path'])
    if origin=='gcc':assert any(notice['member'].endswith('COPYING.RUNTIME') for notice in row['notices'])
    if origin=='freetype':assert any(notice['member'].endswith('FTL.TXT') for notice in row['notices'])
    rows.append(row)
actual={path.relative_to(ROOT).as_posix() for path in (ROOT/'third_party/alpine-notices/texts').iterdir()}
assert actual==blob_paths,'Unindexed notice bytes must be reviewed rather than silently shipped'
with zipfile.ZipFile(ROOT/'.local/g7-image-secret-audit-01/proxy-documentation.zip') as z:
    for row in rows:
        if row['disposition']=='actual_image_notice_preserved':
            for notice in row['notices']:assert sha(z.read(notice['path']))==notice['sha256']
index=dict(schema_version=1,result='selected_proxy_all_package_notice_dispositions_recorded',
    image=support['proxy']['image'],packages=packages,origins=rows,packages_with_explicit_disposition=71,
    source_origins=59,unique_notice_texts=len(blob_paths),
    source_evidence=[path.name for path in [OUT/'support-notice-coverage.json',OUT/'proxy-source-recipes.json',
        OUT/'proxy-source-notices.json',OUT/'libyuv-content-binding.json',OUT/'proxy-notice-extras.json',
        OUT/'proxy-inline-notices.json',OUT/'expat-upstream-notice.json']],
    limits=['Preserves actual furnished declarations/attribution and explicitly records no-standalone-notice cases. No fabricated permission statement.',
            'Expat upstream release notice is exact; unavailable Alpine packaging recipe is a recorded transport limitation, not reproduced source.',
            'No legal compatibility opinion, final vulnerability clearance or complete OPS03/G7 claim.'])
path=ROOT/'third_party/alpine-notices/index.json';assert not path.exists();path.write_text(json.dumps(index,indent=2)+'\n',encoding='utf8')
with (OUT/'proxy-notice-index.json').open('x',encoding='utf8') as stream:
    json.dump(dict(result=index['result'],index=path.relative_to(ROOT).as_posix(),sha256=sha(path.read_bytes()),
        packages=71,origins=59,unique_notice_texts=len(blob_paths),all_preserved_bytes_verified=True,limits=index['limits']),stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=index['result'],packages=71,origins=59,unique_notice_texts=len(blob_paths))))
