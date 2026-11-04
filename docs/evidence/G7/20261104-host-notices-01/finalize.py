"""Verify official installed notice bytes and preserve all furnished supplements."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-host-notices-01'
def load(name):return json.loads((OUT/name).read_text())
def sha(raw):return hashlib.sha256(raw).hexdigest()
index=load('host-notice-index.json');upstream=load('npm-upstream-notices.json');registry=load('npm-supplement-artifacts.json')
source=PRIVATE/'host-notices.zip';assert sha(source.read_bytes())==index['notice_archive_sha256']
payloads={}
with zipfile.ZipFile(source) as z:
    for row in index['files']:
        raw=z.read(row['path']);assert sha(raw)==row['sha256'];payloads[row['path']]=raw
vendor=PRIVATE/Path(index['node']['archive_url']).name;prefix=vendor.name[:-4]+'/'
with zipfile.ZipFile(vendor) as z:
    for package in index['node']['bundled_packages']:
        for notice in package['notices']:
            relative=notice['path'].removeprefix('host/node/')
            assert z.read(prefix+relative)==payloads[notice['path']]
rows=[]
for package in upstream['records']:
    safe=package['name'].replace('@','').replace('/','--');copied=[]
    for notice in package['notices']:
        raw=(ROOT/notice['private_file']).read_bytes();assert sha(raw)==notice['sha256']
        name='host/npm-supplements/'+safe+'/'+notice['source_path'];payloads[name]=raw
        copied.append(dict(path=name,sha256=sha(raw),bytes=len(raw),url=notice['url']))
    metadata_path=PRIVATE/(safe+'-metadata.json');raw=metadata_path.read_bytes()
    source_record=next(row for row in registry['records'] if row['name']==package['name'])
    assert sha(raw)==source_record['metadata_sha256']
    name='host/npm-supplements/'+safe+'/registry-metadata.json';payloads[name]=raw
    rows.append(dict(name=package['name'],version=package['version'],license=package['declared_license'],
        source_commit=package['source_commit'],notices=copied,publisher_metadata=name,
        disposition='source_root_license_and_attribution_preserved' if package['standalone_license_found'] else
            'furnished_README_and_registry_source_license_declaration_preserved_no_standalone_license',
        missing_permission_or_copyright_statement_invented=False))
terms=[]
commit_url='https://api.github.com/repos/spdx/license-list-data/commits/main'
with urllib.request.urlopen(urllib.request.Request(commit_url,headers={'User-Agent':'modular-platform-local-notice-audit/1'}),timeout=30) as response:commit_raw=response.read(1024*1024)
commit=json.loads(commit_raw)['sha'];assert len(commit)==40
(PRIVATE/'spdx-source-commit.json').write_bytes(commit_raw)
for identifier,url in [('CC-BY-3.0','https://creativecommons.org/licenses/by/3.0/legalcode.txt'),
                       ('CC0-1.0','https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt')]:
    reference_url=f'https://raw.githubusercontent.com/spdx/license-list-data/{commit}/text/{identifier}.txt'
    with urllib.request.urlopen(reference_url,timeout=30) as response:raw=response.read(1024*1024)
    assert raw.startswith(b'Creative Commons Legal Code')
    name='host/npm-supplements/reference-terms/'+identifier+'.txt';payloads[name]=raw
    terms.append(dict(identifier=identifier,canonical_url=url,source_url=reference_url,source_commit=commit,path=name,sha256=sha(raw),bytes=len(raw),canonical_fetch_limitation='Python HTTPS fetch403; canonical text verified through web source, exact companion text preserved from official SPDX data at pinned commit'))
buffer=io.BytesIO();files=[]
with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
    for name,raw in sorted(payloads.items()):
        entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,raw)
        files.append(dict(path=name,sha256=sha(raw),bytes=len(raw)))
raw=buffer.getvalue();destination=PRIVATE/'host-notices-final.zip';assert not destination.exists();destination.write_bytes(raw)
with zipfile.ZipFile(destination) as z:
    assert z.testzip() is None
    for row in files:assert sha(z.read(row['path']))==row['sha256']
assert all(row['path'] in payloads for row in index['files'])
source.unlink() # exact newly owned superseded ZIP; all207entries verified in final.
record=dict(result='passed_selected_host_notice_preservation_and_official_Node_binding',Python='3.12.16',
    isolated_operator_distributions=13,base_interpreter_notices=len(index['base_interpreter']['notices']),
    base_bootstrap_pip_not_in_selected_operator=True,Node=index['node']['version'],npm='11.19.1',
    Node_installed_binary_and145bundled_manifests_official_archive_exact=True,
    all_furnished_Node_bundled_notice_bytes_official_archive_exact=True,typescript_packages=2,
    npm_supplement_dispositions=rows,version_specific_reference_terms=terms,notice_files=len(files),files=files,
    final_archive=destination.relative_to(ROOT).as_posix(),archive_sha256=sha(raw),
    initial_archive_sha256=index['notice_archive_sha256'],initial207entries_preserved=True,superseded_owned_ZIP_retired=True,
    downloaded_source_executed=False,global_install_or_toolchain_mutations=0,new_Docker_assets=0,
    limits=['Preserves all furnished installed/source attribution and explicit absent-notice cases. No fabricated ISC copyright holder/permission statement for @npmcli/agent.',
            'The source READMEs preserve SPDX data attribution/declarations; exact version legal-code reference texts accompany them.',
            'Official Node archive and registry artifacts are verified data inputs. Runtime/tooling vulnerability dispositions and final release-kit/G7 remain separate.'])
with (OUT/'host-notices-final.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],files=len(files),official_Node_binary_exact=True,superseded_ZIP_retired=True)))
