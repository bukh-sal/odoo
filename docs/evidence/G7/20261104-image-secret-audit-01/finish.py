"""Close current release secret audit with history delta/new evidence/new logs."""
import base64,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import Scanner,save_report
def load(path):return json.loads(path.read_bytes())
values={k:base64.b64decode(v) for k,v in load(PRIVATE/'known-values.json').items()}
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
records=['repository-triage','image-triage','assets-logs-triage','retained-command-logs-after']
for name in records:
 record=load(OUT/(name+'.json'));assert record.get('known_generated_findings',record.get('known_secret_findings'))==0
 assert record.get('unreviewed_findings',record.get('generic_findings',0))==0
base=load(OUT/'repository-triage.json')['source_head'];head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()
objects={}
for line in subprocess.check_output(['git','rev-list','--objects',base+'..'+head]).decode().splitlines():
 parts=line.split(' ',1)
 if len(parts)==2:objects[parts[0]]=parts[1]
checked=subprocess.run(['git','cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],input=''.join(k+'\n' for k in objects).encode(),capture_output=True,check=True).stdout
delta=[];findings=[]
for line in checked.decode().splitlines():
 oid,kind,size=line.split()
 if kind!='blob':continue
 raw=subprocess.check_output(['git','cat-file','blob',oid]);assert len(raw)==int(size)
 hits=scanner.inspect_bytes(raw,'new-git-history/'+objects[oid]);findings+=hits
 delta.append(dict(oid=oid,path=objects[oid],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
assert not findings,'Inspect only redacted findings before completion'
pending=subprocess.check_output(['git','diff','--name-only','-z'])+subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'])
pending_rows=[]
for name in sorted(set(p.decode() for p in pending.split(b'\0') if p)):
 path=ROOT/name
 if not path.is_file():continue
 hits=scanner.inspect_file(path,name);assert not hits,'New evidence requires exact review'
 pending_rows.append(dict(path=name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
cutoff=(OUT/'retained-command-logs-after.json').stat().st_mtime_ns;paths=[]
for directory in (ROOT/'.local').iterdir():
 if not directory.is_dir() or directory==PRIVATE or not directory.name.startswith(('g6-','g7-')):continue
 for parent,dirs,files in os.walk(directory):
  dirs[:]=[d for d in dirs if d not in ['profile','node_modules','filestore','data','pgdata','history-blobs','image-files','finding-files','served-assets']]
  for name in files:
   path=Path(parent)/name
   if name.endswith(('.stdout','.stderr','.log')) and path.stat().st_mtime_ns>=cutoff:paths.append(path)
findings=scanner.scan_paths(paths,PRIVATE/'patterns.regex',root=ROOT);assert not findings,'Changed command logs require exact review'
fresh=load(ROOT/'.local/g7-fresh-release-01/target21/operator/target.json');old=load(ROOT/'.local/g6-events/operator/target.json')
ids=[fresh['worker_id'],old['worker_id'],'mp-disposable-document-stats-g7qual-document-stats-1','mp-disposable-document-stats-07-document-stats-1',fresh['project']+'-db-1',fresh['project']+'-edge-1',old['project']+'-db-1',old['project']+'-edge-1']
cache=PRIVATE/'final-current-logs';cache.mkdir();logs=[]
for index,ident in enumerate(ids):
 item=json.loads(subprocess.check_output(['docker','inspect',ident]))[0];assert item['State']['Running']
 r=subprocess.run(['docker','logs',item['Id']],capture_output=True,timeout=30);assert r.returncode==0
 raw=r.stdout+b'\n'+r.stderr;path=cache/str(index);path.write_bytes(raw)
 assert not scanner.inspect_file(path,'final-container-log/'+item['Name'])
 logs.append(dict(id=item['Id'],name=item['Name'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
export=(PRIVATE/'images.tar').resolve();assert export.parent==PRIVATE.resolve() and export.stat().st_size==load(OUT/'image-layers.json')['export_bytes']
export_digest=hashlib.sha256(export.read_bytes()).hexdigest();export_bytes=export.stat().st_size;export.unlink();assert not export.exists()
assert not (PRIVATE/'current-member').exists()
report=dict(result='passed_current_SEC03_release_secret_audit',acceptance=['SEC-03'],source_head=head,prior_complete_history_head=base,history_delta_blobs=delta,pending_evidence_scanned=pending_rows,new_or_changed_command_log_files=len(paths),final_current_container_logs=logs,known_values=len(values),known_generated_findings=0,unreviewed_findings=0,phase_records_sha256={n:hashlib.sha256((OUT/(n+'.json')).read_bytes()).hexdigest() for n in records},image_layers=44,image_regular_files=27080,curated_archives=19,served_static_assets=2,retained_log_files_after_export_separation=5922,secret_export_relocation='secret-export-relocation.json',cleanup=dict(image_export_removed=True,bytes_removed=export_bytes,export_sha256=export_digest,exact_finding_bytes_and_inventory_retained=True,current_checkpoint_images_volumes_networks_untouched=True),limits=['Known-value/structural audit with exact reviewed fixtures/format constants/documentation; not a universal secret detector or vulnerability-free/native sandbox claim.','Four explicit config/backup stdout transports were secret-bearing and moved byte-for-byte to owner-protected secret stores; original positive findings retained, no retroactive clean result.','Private credentials/configuration/issuer/backup/secret audit stores are excluded from public release. Later source, evidence or log changes require scoped re-scan; this record does not predict future bytes.'])
save_report(OUT/'qualification.json',report)
print(json.dumps(dict(result=report['result'],history_delta_blobs=len(delta),pending_files=len(pending_rows),changed_private_logs=len(paths),current_container_logs=len(logs),image_export_bytes_removed=export_bytes)))
