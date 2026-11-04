"""Remove only the compiler-verified cache created by the failed bootstrap import."""
import hashlib,importlib.util,json,marshal,shutil,struct,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-kit-01'
kit=ROOT/'.local/releases/r1-0.1.23';manifest=json.loads((kit/'kit-inventory.json').read_bytes())
expected=set(manifest['files'])|{'kit-inventory.json','SHA256SUMS'}
actual={p.relative_to(kit).as_posix() for p in kit.rglob('*') if p.is_file()}
relative='scripts/__pycache__/verify.cpython-312.pyc';assert actual-expected=={relative}
path=kit/relative;source=(kit/'scripts/verify.py').resolve();raw=path.read_bytes()
assert path.resolve().is_relative_to(kit.resolve()) and not path.is_symlink()
assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['files']['scripts/verify.py']['sha256']
assert raw[:4]==importlib.util.MAGIC_NUMBER
flags,stamp,size=struct.unpack('<III',raw[4:16]);assert flags==0 and stamp==int(source.stat().st_mtime)&0xffffffff and size==source.stat().st_size
assert marshal.loads(raw[16:])==compile(source.read_bytes(),str(source),'exec')
copy=PRIVATE/'bootstrap-import-verify.pyc';assert not copy.exists();copy.write_bytes(raw)
path.unlink();assert list(path.parent.iterdir())==[];path.parent.rmdir()
sys.path.insert(0,str(ROOT/'release'));from verify import verify
verify(kit)
report=dict(result='retired_exact_generated_bootstrap_cache',file=relative,sha256=hashlib.sha256(raw).hexdigest(),
 source_sha256=manifest['files']['scripts/verify.py']['sha256'],compiler_and_source_identity_verified=True,
 original_manifest_and_50_components_unchanged=True,operator_workdir_created=False,private_cache_copy_retained=True,
 limits=['No unknown member ignored or removed; strict kit verifier retained. No operator/app/Docker mutation.'])
with (OUT/'cache-retirement.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report))
