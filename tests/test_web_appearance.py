"""Actual native rendering methods without importing or initializing Odoo."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'framework_addons/web/models/ir_http.py'

def native_method(name,request):
    tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
    owner=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='IrHttp')
    method=next(node for node in owner.body if isinstance(node,ast.FunctionDef) and node.name==name)
    namespace={'request':request}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(SOURCE),'exec'),namespace)
    return namespace[name]

class NativeAppearance(unittest.TestCase):
    def test_exact_dark_preference_reaches_the_actual_native_rendering_context(self):
        cookies={'color_scheme':'dark','unrelated':'unchanged'}
        request=SimpleNamespace(httprequest=SimpleNamespace(cookies=cookies))
        info={'current_actor':'kept','current_release':'kept'}
        reader=native_method('color_scheme',request)
        actor=SimpleNamespace(session_info=lambda:info)
        actor.color_scheme=lambda:reader(actor)
        context=native_method('webclient_rendering_context',request)(actor)
        self.assertEqual(context['color_scheme'],'dark')
        self.assertIs(context['session_info'],info)
        self.assertEqual(cookies,{'color_scheme':'dark','unrelated':'unchanged'})

    def test_missing_light_or_unknown_preference_stays_light_without_mutation(self):
        for value in (None,'light','DARK','../bundle','https://other.invalid','dark\x00'):
            with self.subTest(value=value):
                cookies={} if value is None else {'color_scheme':value}
                before=dict(cookies)
                request=SimpleNamespace(httprequest=SimpleNamespace(cookies=cookies))
                self.assertEqual(native_method('color_scheme',request)(object()),'light')
                self.assertEqual(cookies,before)

if __name__=='__main__':unittest.main()
