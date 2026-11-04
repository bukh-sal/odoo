"""Dated native findings mapped separately from Debian binary-package versions."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-native-review-02'
raw=(ROOT/'.local/g7-release-runtime-audit-01/advisories/debian-tracker.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='6df822e22f62f0425ef00b897b6baebb6ccd70830ca9ae9c3b4c5a497f3ad035'
tracker=json.loads(raw)
binding=json.loads((OUT/'binding-observation.json').read_bytes())
source=json.loads((ROOT/'docs/evidence/G7/20261104-core23-provenance-01/source-dependency-binding.json').read_bytes())
assert source['actual_python_metadata_digests_and_lock_exact'] and source['python_distributions']==77
assert binding['observations']['lxml']['libxml']==[2,14,6]
bundle=json.loads((ROOT/'docs/evidence/G7/20261103-release-runtime-audit-01/bundled-components.json').read_bytes())['roles']['application']['components']
native=json.loads((ROOT/'docs/evidence/G7/20261104-native-libraries-01/inventory.json').read_bytes())
host=json.loads((ROOT/'docs/evidence/G7/20261104-operator-python16-01/runtime-qualification.json').read_bytes())
assert host['Python']=='3.12.16' and host['stdlib']['Expat']=='expat_2.9.0'
vendor=[]
for name,url in {
 'libxslt-backport':'https://raw.githubusercontent.com/lxml/lxml/lxml-6.1.3/libxslt-1.1.43-backport1.patch',
 'libxslt-news':'https://raw.githubusercontent.com/GNOME/libxslt/v1.1.45/NEWS',
 'tiff-36849':'https://security-tracker.debian.org/tracker/CVE-2026-36849',
}.items():
 path=PRIVATE/(name+'.raw');assert not path.exists()
 with urllib.request.urlopen(url,timeout=40) as response:data=response.read()
 path.write_bytes(data);vendor.append(dict(name=name,url=url,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
tree=ast.parse((PRIVATE/'lxml-build.raw').read_bytes())
patches=[ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LIBRARY_PATCHES' for t in n.targets)]
assert patches==[{'libxslt-1.1.43':'libxslt-1.1.43-backport1.patch'}]
assert b'exsltFuncResultComp' in (PRIVATE/'libxslt-backport.raw').read_bytes()
rows=[]
def add(component,cve,roles,decision,reason,refs=None):
 rows.append(dict(component=component,cve=cve,roles=roles,decision=decision,rationale=reason,
  reviewed_on='2026-11-04',review_by='2026-11-11',
  invalidate_on=['Changed image/library/plugin/input/parser configuration','Before nonlocal/public/production deployment'],
  evidence=refs or ['binding-observation.json','../20261104-cve-dispositions-01/primary-notes.json'],
  remediation='Adopt vendor fixes or remove the affected input path before enabling it; requalify actual imports and native compatibility. Residual acceptance does not assert all transitive calls safe.'))

add('Expat2.9.0','CVE-2026-113351',['application','worker','operator16'],'excluded_selected_Python_wrapper_precondition',
 'The actual app binding has no Reset API; exact CPython3.12.16 pyexpat/ElementTree wrapper sources contain no XML_ParserReset call. Selected worker/operator use that CPython release and Expat2.9.0. This exclusion covers those supported Python wrapper paths, not trusted C extensions/ctypes directly calling Expat.')
add('Expat2.9.0','CVE-2026-115506',['application','worker','operator16'],'accepted_mitigated_input_residual',
 'Current native XLSX uses defusedxml with entities/external references forbidden; real native ordinary import and entity refusal were qualified after core22. Fixed source country XML and disabled test helpers differ from arbitrary XML. The newer Expat amplification fix is not installed; unknown transitive XML paths remain residual. Worker reference accepts JSON, and compression/body limits alone are not a proof against expansion.',
 ['binding-observation.json','../20261104-core22-maintenance-01/qualification.json','../20261104-native-libraries-01/parser-paths.json'])
add('Expat2.9.0','CVE-2026-117610',['application','worker','operator16'],'accepted_dormant_API_residual',
 'ExternalEntityParserCreate is actually exposed, so a global missing-API exclusion would be false. Supported defused XLSX rejects external entities and the worker has no XML task API; no supported workflow intentionally creates an external subparser and makes the vulnerable initial empty non-final parse. Arbitrary trusted native/Python use remains possible. The library is not claimed fixed.')
add('Expat2.9.0','CVE-2026-118370',['application','worker','operator16'],'accepted_memory_safety_residual',
 'Attribute/namespace counter overflow is separate from entity expansion. Defusedxml does not fix it. Retain potential parser memory-corruption/availability risk for the local reference, including authenticated imports; no unproved payload-size threshold or universal resource-limit protection is claimed. A vendor-fixed Expat build and actual import qualification are required before broad untrusted/public input exposure.')

xml_cases={
 'CVE-2026-0989':'Nested hostile RelaxNG include recursion; R1 does not accept arbitrary uploaded validation schemas as an execution feature. Pinned schema use differs from an untrusted schema service.',
 'CVE-2026-0990':'Self-referential URI delegation in an XML catalog; no public catalog configuration interface is supplied. Added custom resolvers/catalogs invalidate this decision.',
 'CVE-2026-0992':'Repeated downstream XML catalog traversal; no user catalog upload/execution workflow is supplied. This is not a proof that all resource resolution is safe.',
 'CVE-2026-6732':'XSD/internal-entity type confusion is relevant to libxml2.14.6 even though Debian Bookworm marks its older source not affected. No backport is established for this wheel. Uploaded XSD validation is not an R1 feature; retain a conditional memory-safety risk for native schema/parser use.',
 'CVE-2026-76781':'Malformed nextCatalog can crash catalog resolution. No browser-controlled catalog is configured; custom/native resolver additions require renewed review.',
 'CVE-2026-86137':'XML regexp character-group out-of-bounds read; no arbitrary user-supplied schema/regexp execution API is provided, but transitive native validation is not exhaustively excluded.',
 'CVE-2026-86138':'QName dictionary integer overflow can affect XML parsing. XML/HTML inputs are supported, so do not exclude this merely because DTD/entity loading is restricted. Accept potential memory-safety/availability risk in the local reference; request limits do not prove the native function fixed.',
 'CVE-2026-86139':'URI escaping integer overflow may be reached by native XML/HTML processing; no proof of the newer fix in the older bundled library exists. Retain conditional memory-safety/resource risk rather than inheriting Debian not-affected status.',
 'CVE-2026-86140':'DTD diagnostic element formatting overflow. Default/non-expanding parser use reduces some inputs but is not a universal mitigation; supported import/native XML parsing retains conditional memory-safety risk.',
 'CVE-2026-86141':'XML regexp error path can dereference NULL after failed allocation. Native validation can still fail under memory pressure; no complete allocation-failure safety guarantee is made.',
 'CVE-2026-86142':'XPointer expression overflow. R1 has no arbitrary user XPointer execution feature; a fixed XPath used by code is not the same API. Trusted custom/native XML features could enable it.',
 'CVE-2026-86143':'Negative lengths at XML output callbacks can affect serialization; no native fix is established from the version or Python wrapper. Retain potential memory-safety risk; ordinary serialization success is not adversarial proof.',
 'CVE-2026-86144':'XInclude flag propagation may lose NONET. No owned R1 plugin invokes XInclude on uploaded documents; NONET alone must not be treated as an SSRF or filesystem safety guarantee if a future feature does.',
}
known_xml={c for c in tracker['libxml2'] if c.startswith('CVE-2026')}
assert known_xml==set(xml_cases)|{'CVE-2026-11979','CVE-2026-1757','CVE-2026-6653','CVE-2026-74860'}
for cve,reason in xml_cases.items():
 add('lxml6.1.3/libxml2.14.6',cve,['application'],'accepted_local_reference_residual',reason+' Current lxml build source names a libxslt patch only; no libxml2 backport is presumed. Review before broad untrusted/public deployment.')
for cve,reason in {
 'CVE-2026-11979':'Affected xmlcatalog CLI is not the lxml Python binding or a shipped user service.',
 'CVE-2026-1757':'Affected xmllint interactive shell is not the lxml Python binding or a shipped user service.',
 'CVE-2026-6653':'Retained upstream affected range2.9.11..2.11.0 excludes the observed2.14.6; this does not exclude newer libxml2 findings.',
 'CVE-2026-74860':'Affected standalone libxml2 Python SAX wrapper is different from lxml Cython bindings; that standalone wrapper is not installed.',
}.items():add('lxml6.1.3/libxml2.14.6',cve,['application'],'excluded_specific_component_or_range',reason)
for cve in ['CVE-2025-7424','CVE-2025-11731']:
 add('lxml6.1.3/libxslt1.1.43',cve,['application'],'vendor_documented_backport',
  'Exact lxml release notes document Linux wheel patches for these two issues; the exact-tag build mapping selects libxslt-1.1.43-backport1.patch and its retained source changes the affected transformation logic. Actual wheel distribution bytes and embedded libxslt1.1.43 are bound; embedded version alone must not override the documented backport. This is vendor/source provenance, not a new exploit regression test.',
  ['binding-observation.json','../20261104-cve-dispositions-01/primary-notes.json','vendor-sources.json'])
add('lxml6.1.3/libxslt1.1.43','CVE-2025-24855',['application'],'outside_upstream_affected_range','Upstream libxslt NEWS records the fix in1.1.43, which is actually embedded. The later backport cases are separate.',['binding-observation.json','vendor-sources.json'])
for cve in ['CVE-2025-10911','CVE-2025-7425']:
 add('lxml6.1.3/libxslt1.1.43',cve,['application'],'accepted_stylesheet_input_residual',
  'No proof the specifically described document/attribute lifetime issue is covered by the two named vendor backports. R1 does not offer arbitrary uploaded XSLT execution; installed transformations use trusted code/schema inputs. Retain potential use-after-free/memory corruption if a custom native feature processes hostile stylesheets; do not infer fixed solely from libxslt version or a different CVE patch.')

codec_map={'freetype':'freetype2','lcms2':'littlecms2','libwebp':'webp','libavif':'avif','libjpeg-turbo':'libjpeg_turbo','openjpeg2':'jpg_2000','tiff':'libtiff'}
expected={'freetype':3,'lcms2':2,'libwebp':0,'libavif':0,'libjpeg-turbo':1,'openjpeg2':2,'tiff':7}
coverage=[]
for package,feature in codec_map.items():
 candidates={c:v for c,v in tracker.get(package,{}).items() if c.startswith('CVE-2026')}
 assert len(candidates)==expected[package]
 coverage.append(dict(source_component=package,actual_version=bundle['pillow_versions'][feature],matched_2026_candidates=len(candidates),scope='retained_primary_tracker_candidates_not_a_Debian_binary_version_equivalence'))
 for cve,data in candidates.items():
  decision='accepted_native_codec_input_residual'
  if cve=='CVE-2026-23865':
   decision='outside_described_upstream_range';reason='The description identifies FreeType2.13.2/2.13.3 and fix2.14.2; actual embedded2.14.3 is beyond that range. Do not extend this to the two newer FreeType findings.'
  elif package=='freetype':reason='Actual FreeType2.14.3 may contain the described variation/CID font defects. No user-supplied server font API is provided by Notes/Canvas/native record screens. Browser fonts are a different pipeline. Trusted native font-processing additions invalidate this decision; no vendor backport is presumed.'
  elif package=='lcms2':
   decision='accepted_upstream_range_revision_discrepancy';reason='Descriptions limit the Cube/ParseCube defects to versions through2.18 or before2.19, while Debian revision fix levels differ. Embedded LittleCMS is2.19. Preserve the range/revision distinction rather than claiming a Debian package backport applies to the wheel. No arbitrary LUT program upload feature is supplied; ICC/native image processing still carries residual parser risk.'
  elif package=='libjpeg-turbo':reason='The described PNG defect uses tj3LoadImage12/16, not ordinary libjpeg JPEG scanline decoding. Pillow PNG handling is separate, and R1 supplies no TurboJPEG file-loader API. Embedded3.2.0 is not claimed patched; arbitrary trusted native use of that loader remains possible.'
  elif package=='openjpeg2':reason='The described defects concern JPEG2000 encoding. Embedded OpenJPEG2.5.4 is not claimed patched. Reference record image processing does not offer a public JPEG2000 encoder parameter interface; custom native encoding/large geometry can introduce the affected paths. Retain conditional memory-safety/availability risk.'
  elif cve in {'CVE-2026-18495','CVE-2026-52490','CVE-2026-52491','CVE-2026-52492'}:
   decision='excluded_codec_CLI_component';reason='The affected tiff2pdf/tiffcrop/thumbnail/rgb2ycbcr executable is separate from the Pillow libtiff decoder; the runtime supplies no such CLI input service. This exclusion does not cover libtiff decoder findings.'
  else:reason='Actual libtiff4.7.2 is inventoried, but Debian revision fix levels alone are not proof of this wheel backport. The described PixarLog/tile/SamplesPerPixel decoding can be input dependent. Native image parsing remains a potential resource/memory-safety risk; Odoo has a50M-pixel guard only for callers enabling verify_resolution, not a blanket malformed-image defense. Retain as residual instead of claiming exhaustive decoder safety.'
  add('Pillow13.0.0/'+package+bundle['pillow_versions'][feature],cve,['application'],decision,reason,
   ['../20261103-release-runtime-audit-01/bundled-components.json','../20261104-core23-provenance-01/source-dependency-binding.json','../../../../odoo/tools/image.py','vendor-sources.json'])

node=native['roles']['host_build_node']
assert node['node']=='24.22.1' and node['ares']=='1.34.9' and node['nghttp2']=='1.70.0'
for package,count in [('c-ares',3),('nghttp2',2)]:
 candidates={c:v for c,v in tracker[package].items() if c.startswith('CVE-2026')};assert len(candidates)==count
 for cve,data in candidates.items():
  if package=='c-ares':decision='outside_described_upstream_range';reason='The retained descriptions fix these DNS callback/pointer/resource defects in c-ares1.34.7. Actual selected Node embeds1.34.9; official binary identity is independently bound. This is a numeric upstream-range comparison, not a Debian revision comparison.'
  elif cve=='CVE-2026-27135':decision='outside_described_upstream_range';reason='The retained description fixes the HTTP2 termination/assertion issue in1.68.1. Actual selected Node embeds nghttp2 1.70.0.'
  else:decision='excluded_proxy_executable_component';reason='The described request smuggling defect is in the nghttpx proxy, not Node HTTP2 library bindings. The selected build tool is Node, not an nghttpx service; no such proxy input workflow is supplied.'
  add('Node24.22.1/'+package,cve,['host_build_tooling'],decision,reason,['../20261104-native-libraries-01/inventory.json','../20261104-host-notices-01/host-notices-final.json'])
add('Node24.22.1/Brotli1.2.0','CVE-2026-111497',['host_build_tooling'],'vendor_documented_backport','The retained official October Node security bulletin identifies24.22.1 as fixed, despite the embedded Brotli1.2.0 string. Installed node.exe is byte-identical to the SHA256-verified official Windows ZIP. Do not replace this vendor-bound result with an upstream-only version flag.',['../20261104-native-libraries-01/vendor-inputs.json','../20261104-host-notices-01/host-notices-final.json'])
for cve in ['CVE-2026-22184','CVE-2026-27171','CVE-2026-85091']:
 add('native_zlib_variants',cve,['application','host_build_tooling','selected_proxy'],'accepted_variant_specific_input_residual',
  'untgz is a contrib demonstration utility, combine64 loops require the special combine API, and gz_vacate requires nonblocking gzprintf/gzwrite stalls. Python ZIP/XLSX and Node compression bindings do not provide those CLI/C-stdio workflows directly; future native callers may. App system/Pillow reports1.2.13, Pillow also reports zlib-ng2.3.3, lxml vendor history declares zlib1.3.2, Node reports1.3.2.1-motley. No universal patch equivalence between these variants is asserted. Selected proxy zlib1.3.2-r1 has an exact retained recipe/secfix backport for CVE2026-85091. Preserve conditional native compression risk rather than incorrectly marking every variant fixed.',
  ['../20261103-release-runtime-audit-01/bundled-components.json','../20261104-native-libraries-01/inventory.json','../20261104-cve-dispositions-01/primary-notes.json','../20261104-support-images-01/vendor-findings-review.json'])
add('nginx1.30.6','CVE-2009-4487',['selected_proxy'],'accepted_diagnostic_log_residual','Reference error logging is crit; access logging omits bodies/cookies/query strings. This reduces exposure but does not sanitize every arbitrary diagnostic byte. Logs must not be treated as HTML or executed as terminal controls. No patched release is claimed.',['../20261104-support-images-01/vendor-findings-review.json','../../../../docs/http-security.md'])
profile=(ROOT/'deploy/nginx-r0.conf').read_bytes()
assert all(token not in profile for token in [b'load_module',b'xslt_stylesheet',b'image_filter'])
add('selected_proxy_optional_XML_image_modules','NATIVE-PROXY-MODULE-INPUT-01',['selected_proxy'],'accepted_unconfigured_module_residual',
 'Selected image contains optional XSLT/image-filter modules and libxml2/libxslt/codec dependencies. The qualified generated reference profile neither loads dynamic modules nor configures XSLT/image-filter processing. Do not inherit application wheel backports or mark every installed proxy library fixed. XML/stylesheet/image CVEs reviewed above can require reassessment if those modules/features are enabled; current profile does not provide that input pipeline.',
 ['../../../../deploy/nginx-r0.conf','../../../../tools/http_profile.py','../20261104-production-profile-01/qualification.json','../20261104-support-images-01/inventory.json'])

# Host/operator and Node SQLite use different versions; preserve the private-SQL
# and dormant-built-in scope instead of borrowing Debian revision classifications.
sql_prior=json.loads((ROOT/'docs/evidence/G7/20261104-cve-dispositions-01/dated-dispositions.json').read_bytes())
for row in sql_prior['decisions']:
 if row['source_package']!='sqlite3':continue
 add('operator_SQLite3.53.1/Node_SQLite3.53.4',row['cve'],['operator16','host_build_tooling'],'accepted_private_SQL_or_dormant_builtin_residual',
  'The operator uses the already reviewed44 constant SQL calls on private catalog/control files, not user-supplied SQL/DB/WAL/changeset imports. Node is a build tool; R1 has no Node SQLite runtime service or imported node:sqlite workflow. Different embedded versions may already fix some findings, but no Debian revision status is transferred to them. Retain the input-boundary residual, especially for newer before3.54.0 findings.',
  ['../20261104-cve-dispositions-01/sqlite-preconditions.json','../20261104-operator-python16-01/runtime-qualification.json','../20261104-native-libraries-01/inventory.json'])

with (OUT/'vendor-sources.json').open('x',encoding='utf8') as f:json.dump(dict(utc=datetime.now(timezone.utc).isoformat(),sources=vendor,lxml_library_patch_mapping=patches[0]),f,indent=2);f.write('\n')
report=dict(result='dated_known_native_findings_and_component_mapping_recorded',utc=datetime.now(timezone.utc).isoformat(),
 decisions=rows,decision_count=len(rows),codec_candidate_coverage=coverage,node_component_inventory=node,reference_proxy_profile_sha256=hashlib.sha256(profile).hexdigest(),
 preserved_crypto_vendor_review='../20261104-support-images-01/vendor-findings-review.json',
 source_and_notice_binding='../20261104-core23-provenance-01/source-dependency-binding.json',
 limits=['Known native candidate review complements full-history Python-package/OS scans; it is not an exhaustive all-history native CVE database or certification of safe arbitrary image/font/XML input.',
 'Codec candidates enumerate every2026 record for the seven named sources in the retained tracker, including records marked Debian not-affected; Debian status is not automatically native-wheel status. No new package/image or public runtime capability was introduced.',
 'Native memory-safety/availability residuals are material release caveats with review dates and change triggers; accepted findings are not called fixed.',
 'All159 Debian OS decisions remain separate. Existing crypto/libpq/nginx affected-range/Alpine secfix reviews retain their exact image/snapshot scopes. No complete OPS03/G7 claim.'])
with (OUT/'native-dispositions.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],decisions=len(rows),codec_candidates=sum(r['matched_2026_candidates'] for r in coverage))))
