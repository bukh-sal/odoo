"""Exact-content triage; fail on any finding outside the reviewed identities."""
from datetime import datetime,timezone
import collections,hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-secret-scan';sys.path[:0]=[str(ROOT/'tools'),str(OUTPUT)]
from tree import context
from secret_scan import RULES,save_report
BASE='5c7defb49e020fec8b6bb82403a2f54eb79e92e1'
SPECIAL={
 'addons/account_peppol/tools/private_key.pem':'Public upstream Peppol tool sample key; exact pinned source, excluded from curated runtime; not the private TLS identity.',
 'addons/iot_box_image/overwrite_after_init/etc/ssl/private/nginx-cert.key':'Public upstream IoT image sample key; excluded from curated runtime, not current TLS identity.',
 'addons/l10n_it_edi/data/pkey.key':'Public upstream Italian EDI sample key; excluded from curated runtime and never configured for this platform.',
 'addons/api_doc/static/src/utils/doc_code_gen.js':'Documentation code generator placeholder, not a generated platform credential; excluded runtime.',
 'addons/iot_box_image/overwrite_before_init/etc/init_image.sh':'Upstream image bootstrap default comment explicitly replaces it on first start; excluded runtime and never executed here.',
 'addons/mail/static/lib/odoo_sfu/odoo_sfu.js':'Public upstream SFU fallback ICE parameter literal, not an account/API credential; excluded curated runtime.',
 'addons/portal/static/src/xml/portal_chatter.xml':'Template URL expression concatenates current attachment token; expression is not a credential value.',
 'addons/auth_password_policy/static/src/password_field.xml':'Owl password state binding expression, not a credential value.',
 'addons/auth_password_policy_signup/static/src/public/components/password_meter/password_meter.xml':'Owl password state binding expression, not a credential value.',
 'odoo/http.py':'Documentation form template calls request.csrf_token(); no issued token literal.'}

def own_reason(name,data,match):
 if name=='deploy/init-db.sh':
  assert match==b"PASSWORD :'app_password'";return 'psql variable reference populated from private secret file at runtime; no password literal.'
 if name=='docs/evidence/G5/20261029-http-security-02/preflight.py':
  assert b'INTENTIONALLY_DIFFERENT_CONFIG_VALUE' in match;return 'Explicit negative preflight specimen; never applied to a live database or configuration.'
 if name=='tests/test_artifacts.py':
  assert match.startswith(b'-----BEGIN ') or b'PRIVATE_VALUE' in match
  return 'Reviewed package rejection specimen: incomplete PEM marker or synthetic credential/invalid-domain URL; never an actual account.'
 raise AssertionError('Unreviewed project source identity: '+name)

def main():
 scanner=context();records=[];baseline={};source_reports=['tracked-tree','implementation-history','image-layers'];image_inv=json.loads((LOCAL/'image-inventory.json').read_text());image_map={x['location']:k for k,x in image_inv.items()}
 def reviewed_source(name,data,f):
  match=re.compile(RULES[f['rule']]).match(data,f['offset']);assert match and scanner.fingerprint(match.group())==f['fingerprint'];raw=match.group()
  if name.startswith(('addons/','odoo/')):
   if name not in baseline:baseline[name]=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)
   assert data==baseline[name],'Upstream file changed: '+name
   if name in SPECIAL:return SPECIAL[name]
   if '/tests/' in name or '/static/tests/' in name:return 'Exact public upstream automated-test specimen (test user/password, fake token, parser URL or test TLS key); not used to initialize current platform accounts.'
   if f['rule']=='HTML-session-token' or b'csrf_token' in raw or b'access_token' in raw:
    assert b'request.csrf_token' in data or b't-esc="access_token' in data;return 'Unrendered QWeb/JavaScript template expression; a per-request token is evaluated at runtime, no issued token literal.'
   raise AssertionError('Upstream match requires review: '+name)
  return own_reason(name,data,raw)
 for report_name in source_reports:
  report=json.loads((OUTPUT/(report_name+'.json')).read_text());assert report['known_secret_findings']==0
  for f in report['findings']:
   name=f['location'];provenance=None
   if report_name=='tracked-tree':data=(ROOT/name).read_bytes();reason=reviewed_source(name,data,f);provenance='pinned-upstream' if name.startswith(('addons/','odoo/')) else 'project-reviewed-specimen'
   elif report_name=='implementation-history':
    data=(LOCAL/'history-blobs'/f['git_blob']).read_bytes();reason=reviewed_source(name.removeprefix('git-history/'),data,f);provenance='exact-git-blob'
   else:
    item=image_inv[image_map[name]];data=(LOCAL/'image-files'/image_map[name]).read_bytes();assert hashlib.sha256(data).hexdigest()==item['sha256']
    if '/opt/modular/' in name:
     source=name.split('/opt/modular/',1)[1];reason=reviewed_source(source,data,f);provenance='image-layer-exact-pinned-upstream'
    else:
     path=name.split('/',4)[-1];provenance='pinned-vendor-image-layer'
     if path in ['usr/lib/x86_64-linux-gnu/libgnutls.so.30.34.3','usr/lib/file/magic.mgc'] or '/cryptography/hazmat/primitives/serialization/' in path:reason='PEM begin/end format recognition string in library/parser or compiled equivalent; no configured private identity.'
     elif '/gevent/tests/' in path or '/slapdtest/certs/' in path:reason='Bundled vendor automated-test TLS specimen in pinned dependency layer; never configured as a platform TLS identity; active private TLS key is different.'
     elif path=='etc/ssl/private/ssl-cert-snakeoil.key':reason='Debian vendor snakeoil certificate key inherited from the pinned base layer, not generated by this project and never configured by platform HTTP/TLS profiles. Actual private edge key is different and independently scanned.'
     elif '/urllib3/util/' in path or path=='usr/share/perl/5.36.0/HTTP/Tiny.pm' or path=='usr/local/lib/python3.12/urllib/request.py':reason='Vendor documentation URL/proxy password example (including compiled docstring); not a configured connection or runtime credential.'
     else:raise AssertionError('Unreviewed image file: '+path)
   records.append(dict(report=report_name,**f,file_sha256=hashlib.sha256(data).hexdigest(),provenance=provenance,disposition='cleared_reviewed_public_fixture_or_expression',reason=reason))
 result=dict(result='passed_reviewed_identities',utc=datetime.now(timezone.utc).isoformat(),reviewed_findings=len(records),upstream_files_verified=len(baseline),counts=dict(collections.Counter(r['report'] for r in records)),records=records,limits=['This is an exact-file SHA256/offset/fingerprint clearance, not an ignore rule for future files or directory names.','Public upstream/vendor specimens are not project credentials. No claim that native code or arbitrary plugin logs are sandboxed.','No upstream source/license changes or Git history rewriting. Runtime sample accounts were separately disabled/rotated by qualified SEC02/04 preflight.'])
 save_report(OUTPUT/'triage-source-image.json',result);print(json.dumps({k:result[k] for k in ['result','reviewed_findings','upstream_files_verified','counts']}))
if __name__=='__main__':main()
