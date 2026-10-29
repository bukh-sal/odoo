"""Read all unique layers of operated release images; never run extracted code."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-secret-scan'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(OUTPUT)]
from secret_scan import save_report
from tree import context


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'image-layers.json';assert not dest.exists();cache=LOCAL/'image-files';cache.mkdir();archive=LOCAL/'operated-images.tar';assert not archive.exists();images=set()
    for name in ['.local/operator/targets/g5.json','.local/g5-manager-upgrade/operator/target.json','.local/g5-lifecycle/operator/target.json','.local/g5-dispatch/operator/target.json','.local/g5-httpsecurity/operator/target.json']:images.add(load(ROOT/name)['image_id'])
    # Edge and DB vendor images have no generated credentials baked into them;
    # scan their actual layers too, rather than inferring this from tags.
    images.update(['nginx:stable-alpine@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951','postgres:16-bookworm@sha256:d81f7b51697014367236d07ec58b54153fc28f828b72bf247fe5c7487520bcb0'])
    started=time.monotonic();print(json.dumps(dict(state='saving_exact_images_for_private_audit',images=len(images))),flush=True)
    r=subprocess.run(['docker','image','save','--output',str(archive),*sorted(images)],capture_output=True,timeout=600)
    if r.returncode:(LOCAL/'image-save.stderr').write_bytes(r.stderr);raise RuntimeError('Inspect the exact export before continuation; do not blindly restart')
    files=[];mapping={};layers=[]
    def record(stream,size,location):
        if size>512*1024*1024:raise RuntimeError('Unexpected huge layer member; explicit review required')
        path=cache/('%08d'%len(files));digest=hashlib.sha256();remaining=size
        with path.open('xb') as target:
            while remaining:
                raw=stream.read(min(4*1024*1024,remaining));assert raw;target.write(raw);digest.update(raw);remaining-=len(raw)
        files.append(path);mapping[path.name]=dict(location=location,size=size,sha256=digest.hexdigest())
    with tarfile.open(archive,'r:*') as outer:
        for member in outer:
            if not member.isfile():continue
            stream=outer.extractfile(member);head=stream.read(512);stream.seek(0)
            layer=member.name.endswith('/layer.tar') or member.name.startswith('blobs/') and (head[:2]==b'\x1f\x8b' or head[257:262]==b'ustar')
            if layer:
                layers.append(member.name)
                with tarfile.open(fileobj=stream,mode='r|*') as inner:
                    for entry in inner:
                        if entry.isfile():record(inner.extractfile(entry),entry.size,'image-layer/'+member.name+'/'+entry.name)
                print(json.dumps(dict(state='layer_materialized_safely',layers=len(layers),files=len(files))),flush=True)
            else:record(stream,member.size,'image-metadata/'+member.name)
    (LOCAL/'image-inventory.json').write_text(json.dumps(mapping,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(state='scanning_all_materialized_image_members',files=len(files))),flush=True)
    scanner=context();findings=scanner.scan_paths(files,LOCAL/'patterns-v2.regex',root=cache)
    for finding in findings:finding['location']=scanner.redact_location(mapping[finding['location']]['location'])
    value=dict(result='scanned_triage_required',utc=datetime.now(timezone.utc).isoformat(),images=sorted(images),unique_layers=len(layers),files=len(files),bytes=sum(r['size'] for r in mapping.values()),export_bytes=archive.stat().st_size,elapsed_seconds=round(time.monotonic()-started,3),known_secret_findings=sum(f['rule']=='known-generated-secret' for f in findings),generic_findings=sum(f['rule']!='known-generated-secret' for f in findings),findings=findings,inventory_sha256=hashlib.sha256((LOCAL/'image-inventory.json').read_bytes()).hexdigest(),limits=['Every exported regular file in every unique layer, including files hidden/deleted by later layers; no archive-selected filesystem paths used or code imported.','Package ZIP payloads and served browser assets are separately decompressed/scanned; links and empty whiteout markers do not supply file bytes.','Raw exported images/audit cache remain owner-protected outside Git/build context.'])
    save_report(dest,value);print(json.dumps({k:value[k] for k in ['result','unique_layers','files','elapsed_seconds','known_secret_findings','generic_findings']}),flush=True)


if __name__=='__main__':main()
