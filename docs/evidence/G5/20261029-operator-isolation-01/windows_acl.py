"""Read independent host DACLs in one native system PowerShell batch."""
from datetime import datetime,timezone
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-operator-isolation';sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import _system_directory,current_identity,protect_directory,verify_private_directory,_not_link

def main():
 dest=OUTPUT/'windows-store-ACLs.json';assert not dest.exists() and not LOCAL.exists();protect_directory(LOCAL);owner=current_identity().removeprefix('windows-sid:');private_roots=['.local/operator/control','.local/g5-manager-upgrade','.local/g5-lifecycle','.local/g5-dispatch','.local/g5-httpsecurity','.local/g5-approval-security','.local/g5-secret-scan'];items={}
 for root in private_roots:verify_private_directory(ROOT/root);items[root]='private-root'
 for root in ['.local/operator/control','.local/g5-manager-upgrade/operator','.local/g5-lifecycle/operator','.local/g5-dispatch/operator','.local/g5-approval-security']:
  for p in (ROOT/root).rglob('*'):
   if p.is_file() or p.is_dir():items[p.relative_to(ROOT).as_posix()]='private-record'
 for root in private_roots[1:5]:
  for p in (ROOT/root).iterdir():
   if p.is_file():items[p.relative_to(ROOT).as_posix()]='private-record'
 for name in ['known-values.json','known-values-initial-source-name-false-positives.json','fingerprint-key','patterns.regex','patterns-v2.regex']:
  items['.local/g5-secret-scan/'+name]='private-record'
 for folder in ['container-logs','legacy-payload-diagnostics','capture-proof']:
  for p in (ROOT/'.local/g5-secret-scan'/folder).rglob('*'):
   if p.is_file() or p.is_dir():items[p.relative_to(ROOT).as_posix()]='private-record'
 for path in ['.local/operator/trust.json','.local/operator/catalog','.local/operator/targets/g5.json']:items[path]='public-integrity-only'
 for name in items:_not_link(ROOT/name)
 inventory=LOCAL/'acl-paths.json';inventory.write_text(json.dumps([dict(path=str(ROOT/p),domain=d) for p,d in items.items()]),encoding='utf8')
 env=dict(os.environ,MP_ISOLATION_ACL_INPUT=str(inventory),PSModulePath=str(_system_directory()/'WindowsPowerShell/v1.0/Modules'))
 script="$items=Get-Content -LiteralPath $env:MP_ISOLATION_ACL_INPUT -Raw | ConvertFrom-Json; $results=@(foreach($item in $items){$a=Get-Acl -LiteralPath $item.path; [pscustomobject]@{path=$item.path;domain=$item.domain;owner=$a.GetOwner([System.Security.Principal.SecurityIdentifier]).Value;protected=$a.AreAccessRulesProtected;rules=@($a.Access | ForEach-Object {[pscustomobject]@{sid=$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value;type=$_.AccessControlType.ToString();rights=[int]$_.FileSystemRights}})}}); ConvertTo-Json -InputObject $results -Depth 6 -Compress"
 r=subprocess.run([str(_system_directory()/'WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,env=env,timeout=120);assert r.returncode==0,'Inspect private ACL inventory; do not reset existing permissions';rows=json.loads(r.stdout);allowed={owner,'S-1-5-18','S-1-5-32-544','S-1-3-4'};violations=[]
 # Owner Rights applies only to the verified private owner. Public digest
 # catalogs may be readable, but untrusted SIDs must have no mutation rights.
 write_mask=0x0002|0x0004|0x0010|0x0040|0x0100|0x10000|0x40000|0x80000
 for row in rows:
  row['path']=Path(row['path']).relative_to(ROOT).as_posix()
  if row['owner']!=owner or not row['rules']:violations.append(dict(path=row['path'],reason='owner/rules mismatch'))
  for rule in row['rules']:
   if rule['type']!='Allow' or rule['sid'] not in allowed and (row['domain']!='public-integrity-only' or rule['rights']&write_mask):violations.append(dict(path=row['path'],reason='unexpected read/write authority',sid=rule['sid']))
  if row['domain']=='private-root' and not row['protected']:violations.append(dict(path=row['path'],reason='root inherits broad ACL'))
 report=dict(result='passed' if not violations else 'failed_review_required',utc=datetime.now(timezone.utc).isoformat(),records=len(rows),private_roots=len(private_roots),owner_identity='windows-sid:'+owner,rows=rows,violations=violations,limits=['Actual Windows owner/DACL metadata, not an impersonation or global user/account change. Real foreign application UID permission test is separate Linux evidence.','Public artifact digest/trust catalogs may be readable; only privileged stores/secrets require confidentiality, all independent inputs require integrity.','SYSTEM and Administrators remain privileged OS authorities; native application UID has no host mount.'])
 (LOCAL/'acl-results.json').write_text(json.dumps(report,indent=2),encoding='utf8');dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result=report['result'],records=len(rows),violations=len(violations))))
if __name__=='__main__':main()
