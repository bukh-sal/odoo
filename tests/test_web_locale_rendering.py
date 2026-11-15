"""Actual native rendering/asset-selection/request-merge methods; external boundaries fake."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
HTTP=ROOT/'framework_addons/web/models/ir_http.py'
CURRENT_RENDERING='''    def webclient_rendering_context(self):
        session_info = self.session_info()
        language = session_info.get('user_context', {}).get('lang')
        if language:
            # session_info refreshes the session; assets read the current env.
            request.update_context(lang=language)
        return {
            'color_scheme': self.color_scheme(),
            'session_info': session_info,
        }'''
PREVIOUS_RENDERING='''    def webclient_rendering_context(self):
        return {
            'color_scheme': self.color_scheme(),
            'session_info': self.session_info(),
        }'''

def before_locale_fix(source):
    if source.count(CURRENT_RENDERING)!=1:raise AssertionError('Exact reviewed method body required')
    return source.replace(CURRENT_RENDERING,PREVIOUS_RENDERING,1)

def method(path,name,namespace=None,source=None):
    tree=ast.parse(source if source is not None else path.read_text(encoding='utf-8'))
    matches=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(matches)!=1:raise AssertionError('One actual native method required')
    node=matches[0];node.decorator_list=[]
    ns=dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(path),'exec'),ns)
    return ns[name]

class LanguageEnvironment:
    def __init__(self,context,user_language):
        self.context=context;self.user=SimpleNamespace(lang=user_language)
        self.lang=context.get('lang')
    def __getitem__(self,name):
        if name=='res.lang':
            model=SimpleNamespace()
            model.sudo=lambda:model
            model._get_data=lambda code:SimpleNamespace(direction={'en_US':'ltr','ar_001':'rtl'}[code])
            return model
        if name=='ir.asset':return SimpleNamespace(_get_asset_params=lambda:{'site_id':'bound-site'})
        raise AssertionError('Unexpected model access')

class LocaleRendering(unittest.TestCase):
    def witness(self,old,new,*,source=None,debug=None,include_language=True):
        scope=object();context={'lang':old,'workspace':'original','trusted_scope':scope,'uid':6}
        info={'user_context':{'lang':new} if include_language else {},'actor':'original','release':'original'}
        request=SimpleNamespace(env=LanguageEnvironment(context,new),session=SimpleNamespace(context=dict(info['user_context'])))
        updates=[]
        def update_env(**kwargs):
            self.assertEqual(set(kwargs),{'context'})
            updates.append(kwargs['context'])
            request.env=LanguageEnvironment(kwargs['context'],new)
        request.update_env=update_env
        actual_update=method(ROOT/'engine/odoo/http.py','update_context')
        request.update_context=lambda **kw:actual_update(request,**kw)
        reader=SimpleNamespace(session_info=lambda:info,color_scheme=lambda:'dark')
        result=method(HTTP,'webclient_rendering_context',{'request':request},source)(reader)
        calls=[]
        assets=SimpleNamespace(env=request.env)
        def capture(bundle,**kw):calls.append({'bundle':bundle,**kw});return kw['rtl']
        assets._generate_asset_links_cache=capture;assets._generate_asset_links=capture
        rtl=method(ROOT/'framework_addons/base/models/ir_qweb.py','_get_asset_links')(assets,'web.assets_web',debug=debug)
        self.assertIs(result['session_info'],info)
        self.assertEqual(result['color_scheme'],'dark')
        self.assertEqual({k:v for k,v in request.env.context.items() if k!='lang'},
                         {k:v for k,v in context.items() if k!='lang'})
        self.assertIs(request.env.context['trusted_scope'],scope)
        self.assertEqual(context['lang'],old)
        self.assertEqual(calls[0]['assets_params'],{'site_id':'bound-site'})
        return rtl,request.env.context,updates

    def test_actual_first_render_selects_current_locale_assets_in_both_directions(self):
        for old,new in [('en_US','ar_001'),('ar_001','en_US')]:
            for debug in (None,'assets'):
                with self.subTest(old=old,new=new,debug=debug):
                    rtl,context,updates=self.witness(old,new,debug=debug)
                    self.assertEqual(rtl,new=='ar_001')
                    self.assertEqual(context['lang'],new)
                    self.assertEqual(len(updates),1)

    def test_missing_user_locale_preserves_existing_context_without_invention(self):
        rtl,context,updates=self.witness('en_US','ar_001',include_language=False)
        self.assertFalse(rtl);self.assertEqual(context['lang'],'en_US');self.assertEqual(updates,[])

    def test_exact_previous_reader_reproduces_the_installed_one_request_lag(self):
        previous=before_locale_fix(HTTP.read_text(encoding='utf-8'))
        for old,new in [('en_US','ar_001'),('ar_001','en_US')]:
            with self.subTest(old=old,new=new):
                rtl,context,updates=self.witness(old,new,source=previous)
                self.assertEqual(rtl,old=='ar_001');self.assertNotEqual(rtl,new=='ar_001')
                self.assertEqual(context['lang'],old);self.assertEqual(updates,[])

    def test_exact_reader_pair_preserves_all_other_native_methods(self):
        import hashlib
        from modular_platform.release_staging import WEB_LOCALE_READER_BEFORE,WEB_LOCALE_READER_AFTER,WEB_APPEARANCE_READER_AFTER
        source=HTTP.read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),WEB_LOCALE_READER_AFTER)
        previous=before_locale_fix(source.decode()).encode()
        self.assertEqual(hashlib.sha256(previous).hexdigest(),WEB_LOCALE_READER_BEFORE)
        self.assertEqual(WEB_LOCALE_READER_BEFORE,WEB_APPEARANCE_READER_AFTER)

if __name__=='__main__':unittest.main()
