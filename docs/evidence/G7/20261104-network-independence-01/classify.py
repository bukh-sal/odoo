"""Refine broad domain candidates and explicitly classify each runtime family."""
import hashlib,json,subprocess,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
def load(p):return json.loads(p.read_bytes())
candidate=load(OUT/'retained-reference-candidates.json');reference=ROOT/'.local/release-kit-rehearsal/private/reference';target=load(reference/'operator/target.json')
script=r'''
import configparser,hashlib,json,pathlib,re,sys
root=pathlib.Path('/opt/modular');candidate=json.load(sys.stdin)
assert 'sha256:'+hashlib.sha256((root/'distribution-inventory.json').read_bytes()).hexdigest()==candidate['inventory_digest']
pattern=re.compile(r'(?i)(?<![a-z0-9_.-])(?:[a-z0-9_-]+\.)*(?:odoo\.(?:com|net)|openerp\.(?:com|net))(?![a-z0-9_-]|\.[a-z0-9_-])')
records=[];false=[];publisher=[]
for record in candidate['records']:
 p=root/record['path'];data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==record['source_sha256'];lines=data.decode('utf8').splitlines();matches=[]
 for old in record['matches']:
  domains=sorted(set(m.group(0).lower() for m in pattern.finditer(lines[old['line']-1])))
  if domains:matches.append(dict(line=old['line'],domains=domains))
  else:false.append(dict(path=record['path'],line=old['line'],reason='broad substring matched a non-host identifier or partial domain'))
 if matches:records.append(dict(record,matches=matches))
# Inspect all inventory Python/XML/JS text for the update option's consumers.
inventory=json.loads((root/'distribution-inventory.json').read_bytes())
for name in inventory['files']:
 p=root/name
 if p.suffix not in {'.py','.xml','.js'}:continue
 text=p.read_text(encoding='utf8',errors='strict')
 if 'publisher_warranty' in text:publisher.append(dict(path=name,occurrences=text.count('publisher_warranty')))
config=configparser.ConfigParser(interpolation=None);config.read('/run/secrets/odoo_config')
print(json.dumps(dict(records=records,excluded_false_positive_matches=false,publisher_warranty_mentions=publisher,selected_nonsecret_settings={name:config.get('options',name,fallback=None) for name in ['max_cron_threads','list_db','proxy_mode']})))
'''
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));from modular_platform.operator_os import protect_directory
private=protect_directory(ROOT/'.local/g7-network-independence-01')
if (private/'classifier.stdout').exists():
 assert (private/'classifier.stderr').read_bytes()==b''
 response=load(private/'classifier.stdout')
else:
 completed=subprocess.run(['docker','exec','-i',target['worker_id'],'/venv/bin/python','-c',script],input=json.dumps(candidate).encode(),capture_output=True,timeout=60)
 for suffix,data in [('stdout',completed.stdout),('stderr',completed.stderr)]:
  with (private/('classifier.'+suffix)).open('xb') as f:f.write(data)
 assert completed.returncode==0,'Read-only classifier failed; inspect private diagnostics'
 response=json.loads(completed.stdout)
decisions={
 'addons/auth_totp/views/templates.xml':('user_facing_documentation_link','Optional Learn More anchor on 2FA form. Local TOTP authentication needs no Odoo service; preserve source/link, no automatic fetch.'),
 'addons/web/controllers/session.py':('optional_account_integration','Authenticated account route returns an OAuth URL; it does not contact Odoo server-side. Platform root omits stock account menu. Explicit use could disclose database UUID/name/base URL to account service; not needed or invoked by reference workflows.'),
 'addons/web/models/ir_http.py':('optional_support_link_metadata','Session support_url points to buy page. Preserve inherited metadata; not a bootstrap call. Platform root supplies its own navigation; any support-link use is explicit optional navigation.'),
 'addons/web/static/lib/hoot/ui/hoot_test_result.js':('developer_test_documentation','Hoot failure documentation link, not a production service dependency. Test library bytes preserved; no Hoot runner in reference pages.'),
 'addons/web/static/src/core/install_scoped_app/install_scoped_app.xml':('branding_attribution_link','Upstream PWA vendor anchor. Platform reference root does not invoke the stock scoped-app installer. Attribution/source preserved.'),
 'addons/web/static/src/public/database_manager.qweb.html':('optional_database_manager_privacy_link','Stock create-database privacy notice. Public database-manager routes are denied at ingress and list_db=False; supported independent bootstrap does not use this UI. Notice/source preserved.'),
 'addons/web/static/src/views/widgets/documentation_link/documentation_link.js':('user_facing_documentation_link','Documentation widget constructs a versioned anchor when a view declares it. No automatic service request; reference Notes views do not require an external document.'),
 'addons/web/static/src/webclient/settings_form_view/fields/upgrade_dialog.js':('optional_commercial_integration','Explicit stock upgrade-confirm opens Enterprise purchase URL with user count. Platform Settings/curated lifecycle do not host this stock upsell flow; no Enterprise code acquired or installed.'),
 'addons/web/static/src/webclient/settings_form_view/fields/upgrade_dialog.xml':('optional_commercial_integration','Stock promotional dialog includes editions anchor and YouTube iframe. Platform Settings does not mount this dialog. Do not describe arbitrary stock upsell use as network independent.'),
 'addons/web/static/src/webclient/settings_form_view/widgets/res_config_edition.xml':('branding_attribution_link','Upstream Community/copyright/LGPL attribution. Preserve source/notices; platform appearance does not claim inherited code as original.'),
 'addons/web/static/src/webclient/user_menu/user_menu_items.js':('optional_account_integration','User-click account command opens account URL. Platform Shell omits stock UserMenu; existing Odoo dialog/command/action infrastructure remains reused. No account login needed.'),
 'addons/web/views/webclient_templates.xml':('branding_attribution_link','Stock login/portal Powered by Odoo anchor and local logo preserved. Browser may follow anchor only by user choice; local image is served same-origin. Platform app has its own branding/layout.'),
 'odoo/addons/base/data/ir_module_module.xml':('optional_catalog_metadata','Stock commercial/app website metadata retained. Referenced ERP/Enterprise implementations absent from the selected distribution. Platform manager resolves only curated local artifacts.'),
 'odoo/addons/base/models/ir_mail_server.py':('optional_mail_test_address','Help example plus noreply@odoo.com SMTP test recipient. No mail configuration/test is performed by reference apps; internal-only app cannot send external mail. Not a telemetry implementation.'),
 'odoo/addons/base/models/ir_qweb.py':('developer_documentation','QWeb module documentation URL, no executable fetch.'),
 'odoo/addons/base/models/res_users.py':('user_facing_documentation_link','Deployment HTTPS advice in an error message, no service request.'),
 'odoo/addons/base/views/ir_module_views.xml':('optional_catalog_or_purchase_link','Stock Apps/Themes actions and upgrade buttons are explicit external links. Platform catalog/lifecycle has its own routes and independent approvals; it does not use the upstream app store.'),
 'odoo/addons/base/views/res_company_views.xml':('example_placeholder','Website field placeholder, no automatic fetch. Reference application has no company website integration.'),
 'odoo/addons/base/views/res_partner_views.xml':('example_placeholder','Contact website field examples, no automatic fetch.'),
 'odoo/http.py':('developer_documentation','HTTP/CSRF documentation and a DNS doctest example. The example is not executed on startup or ordinary requests.'),
 'odoo/release.py':('source_attribution_metadata','Upstream product website/author email retained as release attribution, not a phone-home request.'),
 'odoo/service/common.py':('legacy_about_text','Legacy about endpoint text; inherited RPC ingress excluded. No external request.'),
 'odoo/tools/config.py':('inactive_update_configuration_default','publisher_warranty_url is a parser default. Actual retained Python/XML/JS scan finds this option declaration and five config-manager test fixtures, no active warranty consumer/module. cron threads0. No automatic publisher-warranty/update/telemetry client found in retained scope; not a universal absence claim.'),
 'odoo/tools/mail.py':('developer_documentation','From-address rewrite examples in docstring, not mail sent by reference applications.')}
runtime={r['path'] for r in response['records'] if r['review_group']=='runtime_source'};assert runtime==set(decisions),runtime^set(decisions)
assert response['publisher_warranty_mentions']==[dict(path='odoo/addons/base/tests/test_configmanager.py',occurrences=5),dict(path='odoo/tools/config.py',occurrences=1)]
assert response['selected_nonsecret_settings']['max_cron_threads']=='0' and response['selected_nonsecret_settings']['list_db'].lower()=='false'
for record in response['records']:
 if record['review_group']=='runtime_source':record['classification'],record['decision']=decisions[record['path']]
 elif record['review_group']=='test':record['classification']='test_or_developer_fixture';record['decision']='Retained upstream test content, not a required production integration. Tests may deliberately use network examples; reference runtime does not run them.'
 else:record['classification']='inherited_translation_content';record['decision']='Translated upstream link/branding/help/product strings. Preserve provenance; no blanket claim about arbitrary translated HTML. Actual required reference flows are separately observed with foreign page requests blocked.'
excluded={'iap','iap_mail','web_enterprise','web_unsplash','base_import_module'};assert not excluded&set(candidate['native_addons'])
report=dict(result='classified_current_retained_Odoo_product_ties',utc=datetime.now(timezone.utc).isoformat(),inventory_digest=candidate['inventory_digest'],all_inventory_files_verified=candidate['all_inventory_files_verified'],runtime_source_families_reviewed=len(runtime),reference_files_by_group=dict(Counter(r['review_group'] for r in response['records'])),classifications=dict(Counter(r['classification'] for r in response['records'])),excluded_optional_addons=sorted(excluded),runtime_technical_Odoo_service_requirements_found=0,**response,limits=['Finite retained-source/domain/consumer scan plus explicit source review; not proof of arbitrary plugins, future integrations, arbitrary domains or obfuscated/generated code.','Deliberate product independence uses selected addon exclusions, platform navigation/settings/catalog and internal app/DB/worker networks. Required upstream attribution/notices remain.','Build-time package/provenance downloads, optional user-followed links, SMTP/PWA/account/upsell integrations and browser/OS background services are separate network uses.','Earlier broad candidate scanner matched odoo.Command/odoo.netsvc identifiers. Corrected host boundaries filter these exact false positives without hiding actual URL families.','Final current browser/native-form/Labels/workspace/RTL coverage and operator-source-kit release closure remain separate G7 work.'])
with (OUT/'reviewed-product-ties.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],runtime_families=len(runtime),groups=report['reference_files_by_group'],false_positive_matches_removed=len(response['excluded_false_positive_matches']),runtime_technical_Odoo_requirements=0)))
