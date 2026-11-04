"""Account for every retained source archive; no orphan or unchecked transport."""
import hashlib
import json
from pathlib import Path

ROOT=Path.cwd();OUT=Path(__file__).parent
def load(name):return json.loads((OUT/name).read_text())
primary=load('proxy-source-notices.json');extra=load('proxy-notice-extras.json');lib=load('libyuv-content-binding.json')
rows=[]
for source in primary['records']+extra['additional_source_archives']:
    if 'private_archive' not in source:continue
    path=ROOT/source['private_archive']
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha512').hexdigest()
    if source['origin']=='libyuv':
        assert digest==lib['raw_archive_sha512'] and lib['actual_content_sha512']==lib['recipe_content_sha512']
        method='exact_recipe_prescribed_sorted_regular_file_content_sha512'
    else:
        assert source['result'] in {'verified_primary_source_notices_preserved','verified_source_no_standalone_notice',
            'verified_additional_source_notices_preserved','verified_additional_source_no_standalone_notice'}
        assert digest==source['source_sha512'];method='exact_recipe_source_archive_sha512'
    rows.append(dict(origin=source['origin'],path=source['private_archive'],bytes=path.stat().st_size,
        actual_archive_sha512=digest,validation=method,retained_role='current_source_provenance_and_release_notice_input'))
actual={path.relative_to(ROOT).as_posix() for path in (ROOT/'.local/g7-proxy-source-notices-01/archives').iterdir()}
assert {row['path'] for row in rows}==actual and len(rows)==len(actual)==53
record=dict(result='passed_complete_retained_source_input_accounting',archives=len(rows),bytes=sum(row['bytes'] for row in rows),
    records=rows,unchecked_or_orphan_inputs=0,duplicate_notice_ZIPs_created=0,new_Docker_images_volumes_networks=0,
    retention='Verified current source inputs for provenance/release assembly. No global cache pruning or unknown data deletion. Materialize the final kit before considering exact source-transport retirement.')
with (OUT/'retained-source-inputs.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],archives=53,bytes=record['bytes'])))
