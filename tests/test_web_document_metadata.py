"""Actual bootstrap directive/native locale-data shape; installed rendering is separate."""
import ast
import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import unittest
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'framework_addons/web/views/webclient_templates.xml'

class DocumentMetadata(unittest.TestCase):
    def setUp(self):
        self.bootstrap=ElementTree.parse(SOURCE).find("./template[@id='web.webclient_bootstrap']")
        # Execute the actual native data object's attribute access, without loading Odoo.
        tree=ast.parse((ROOT/'framework_addons/base/models/res_lang.py').read_text(encoding='utf-8'))
        node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LangData')
        ns={'ReadonlyDict':dict,'Any':Any}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'native-LangData','exec'),ns)
        self.LangData=ns['LangData']

    def test_actual_directive_uses_server_locale_and_retains_unrelated_attributes(self):
        expr=self.bootstrap.find(".//t[@t-set='html_data']").get('t-value')
        for code,direction,expected in [('en_US','ltr','en-US'),('ar_001','rtl','ar-001')]:
            with self.subTest(code=code):
                rows={'en_US':self.LangData(id=1,code='en_US',direction='ltr'),
                      'ar_001':self.LangData(id=3,code='ar_001',direction='rtl')}
                calls=[]
                def get_data(**kw):
                    calls.append(kw);return rows[kw['code']]
                attrs={'style':'height: 100%;','data-existing':'kept','lang':'old','dir':'old'}
                info={'user_context':{'lang':code,'unrelated':'kept'}};before=copy.deepcopy(info)
                request=SimpleNamespace(env={'res.lang':SimpleNamespace(_get_data=get_data)},
                    httprequest=SimpleNamespace(args={'lang':'untrusted-url-value'}))
                result=eval(compile(ast.parse(expr,mode='eval'),'actual-bootstrap-directive','eval'),
                    {'dict':dict,'html_data':attrs,'session_info':info,'request':request})
                self.assertEqual(result,{**attrs,'lang':expected,'dir':direction})
                self.assertEqual(calls,[{'code':code}]);self.assertEqual(info,before)
                self.assertEqual(attrs['lang'],'old')

    def test_authenticated_viewport_does_not_disable_user_scaling(self):
        viewport=self.bootstrap.find(".//meta[@name='viewport']")
        self.assertEqual(viewport.get('content'),'width=device-width, initial-scale=1')

    def test_exact_guard_hashes_bind_only_the_two_reviewed_template_changes(self):
        from modular_platform.release_staging import WEB_BOOTSTRAP_VIEW_PATH,WEB_BOOTSTRAP_VIEW_BEFORE,WEB_BOOTSTRAP_VIEW_AFTER
        source=SOURCE.read_bytes();prefix,body=source.split(b'    <template id="web.webclient_bootstrap">',1)
        lines=[line for line in body.splitlines(keepends=True) if b't-set="html_data"' in line and b"session_info['user_context']" in line]
        self.assertEqual(len(lines),1)
        original=prefix+b'    <template id="web.webclient_bootstrap">'+body.replace(lines[0],b'',1).replace(
            b'content="width=device-width, initial-scale=1"/>',b'content="width=device-width, initial-scale=1, user-scalable=no"/>',1)
        self.assertEqual(WEB_BOOTSTRAP_VIEW_PATH,'addons/web/views/webclient_templates.xml')
        self.assertEqual(hashlib.sha256(source).hexdigest(),WEB_BOOTSTRAP_VIEW_AFTER)
        self.assertEqual(hashlib.sha256(original).hexdigest(),WEB_BOOTSTRAP_VIEW_BEFORE)

if __name__=='__main__':unittest.main()
