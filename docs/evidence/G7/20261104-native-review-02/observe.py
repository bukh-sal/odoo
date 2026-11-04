"""Observe current XML binding APIs and retain exact upstream wrapper/build sources."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-native-review-02'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
assert not PRIVATE.exists();protect_directory(PRIVATE)
sources={
 'pyexpat':'https://raw.githubusercontent.com/python/cpython/v3.12.16/Modules/pyexpat.c',
 'elementtree':'https://raw.githubusercontent.com/python/cpython/v3.12.16/Modules/_elementtree.c',
 'lxml-build':'https://raw.githubusercontent.com/lxml/lxml/lxml-6.1.3/buildlibxml.py',
}
vendor=[]
for name,url in sources.items():
 with urllib.request.urlopen(url,timeout=40) as response:raw=response.read()
 (PRIVATE/(name+'.raw')).write_bytes(raw)
 vendor.append(dict(name=name,url=url,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
  XML_ParserReset_occurrences=raw.count(b'XML_ParserReset') if name!='lxml-build' else None))
code="""import hashlib,inspect,json,sys,xml.parsers.expat as expat,xml.etree.ElementTree as ET
import defusedxml.ElementTree as safe,openpyxl.xml.functions as x
from lxml import etree
p=expat.ParserCreate()
def sha(path):
 with open(path,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
print(json.dumps(dict(python=sys.version.split()[0],expat=expat.EXPAT_VERSION,
 pyexpat_has_Reset=hasattr(p,'Reset'),pyexpat_has_ExternalEntityParserCreate=hasattr(p,'ExternalEntityParserCreate'),
 pyexpat_methods=sorted(name for name in dir(p) if not name.startswith('_')),
 defused_constructor=str(inspect.signature(safe.DefusedXMLParser)),
 openpyxl=dict(DEFUSEDXML=x.DEFUSEDXML,LXML=x.LXML,iterparse_module=x.iterparse.__module__),
 lxml=dict(libxml=etree.LIBXML_VERSION,libxslt=etree.LIBXSLT_VERSION,binary_sha256=sha(etree.__file__)),
 safe_source_sha256=sha(inspect.getfile(safe)),openpyxl_function_source_sha256=sha(inspect.getfile(x)),
 source_files={name:sha(module.__file__) for name,module in [('pyexpat',__import__('pyexpat')),('_elementtree',__import__('_elementtree'))]})))
"""
image='sha256:14de369e46f20616e76847cbcacbcb66d5bb791808b950aaf97bc607d31d6b93'
name='mp-g7-native-binding-review-02'
r=subprocess.run(['docker','run','--rm','--name',name,'--label','mp.disposable=native-binding-review',
 '--network','none','--log-driver','none','--read-only','--user','10001:10001','--cap-drop','ALL',
 '--security-opt','no-new-privileges','--memory','256m','--pids-limit','64','--entrypoint','/venv/bin/python',image,'-B','-c',code],capture_output=True,timeout=45)
for suffix,raw in [('stdout',r.stdout),('stderr',r.stderr)]: (PRIVATE/('binding.'+suffix)).write_bytes(raw)
assert r.returncode==0,'Inspect retained diagnostics; do not retry unchanged'
data=json.loads(r.stdout)
assert data['openpyxl']['DEFUSEDXML'] is True and data['openpyxl']['iterparse_module']=='defusedxml.common'
assert data['pyexpat_has_Reset'] is False
assert all(row['XML_ParserReset_occurrences']==0 for row in vendor if row['name']!='lxml-build')
absent=subprocess.run(['docker','inspect','--type','container',name],capture_output=True,timeout=15)
assert absent.returncode and b'no such' in absent.stderr.lower()
report=dict(result='observed_current_XML_bindings_and_primary_wrapper_sources',utc=datetime.now(timezone.utc).isoformat(),image=image,
 observations=data,primary_sources=vendor,helper_removed=True,
 limits=['No malicious parse/reset/external-subparser payload was executed. Existing native XLSX ordinary/entity-refusal qualification remains separate.',
 'No Reset API in these wrappers does not exclude arbitrary trusted C extensions/ctypes calling Expat directly.',
 'libxml/libxslt embedded version strings do not establish vendor backport status; primary lxml release/build records are reviewed separately.'])
with (OUT/'binding-observation.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report))
