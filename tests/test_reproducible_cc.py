"""Actual compiler front-end mapping/argv, without invoking a compiler."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reproducible_cc',ROOT/'deploy/reproducible_cc.py')
cc=importlib.util.module_from_spec(spec);spec.loader.exec_module(cc)


class ReproducibleCompiler(unittest.TestCase):
    def test_independent_pip_roots_map_to_same_debug_namespace(self):
        args=['-Wsign-compare','-DNDEBUG','-g','-O3','-fstack-protector-strong','-c','Modules/source.c','-o','build/source.o']
        for distribution,normalized in [('PSYCOPG2','psycopg2'),('python_ldap','python-ldap'),('another-native','another-native')]:
            mapped=[]
            for nonce in ['a','b']:
                root='/tmp/pip-install-'+nonce+'123/'+distribution+'_'+nonce*32
                result=cc.compiler_arguments(args,root+'/subdirectory')
                self.assertEqual(result,[cc.COMPILER,'-ffile-prefix-map='+root+'=/usr/src/modular-native/'+normalized,*args])
                mapped.append(result[1].split('=',2)[-1])
            self.assertEqual(mapped[0],mapped[1])

    def test_existing_arguments_are_preserved_as_argv_without_shell_expansion(self):
        args=['-g','source with spaces.c','-DVALUE=$(not-a-shell)','-o','output.o']
        result=cc.compiler_arguments(args,'/tmp/pip-install-fixed/generic_'+'a'*32)
        self.assertEqual(result[0],'/usr/bin/gcc');self.assertEqual(result[2:],args)

    def test_unknown_relative_traversal_or_unpinned_root_refuses(self):
        for root in ['/source','tmp/pip-install-x/a_'+'a'*32,'/tmp/pip-build-env-x/a_'+'a'*32,
                '/tmp/pip-install-x/a','/tmp/pip-install-x/a_'+'a'*31,'/tmp/pip-install-x/a_'+'a'*32+'/../foreign',
                '/tmp//pip-install-x/a_'+'a'*32]:
            with self.subTest(root=root),self.assertRaises(ValueError):cc.compiler_arguments([],root)

    def test_main_executes_only_fixed_compiler_with_actual_cwd_mapping(self):
        root='/tmp/pip-install-owned/independent_'+'b'*32
        with patch.object(cc.os,'getcwd',return_value=root),patch.object(cc.sys,'argv',['front','-c','source.c']),patch.object(cc.os,'execv') as execute:
            cc.main()
        execute.assert_called_once_with('/usr/bin/gcc',['/usr/bin/gcc','-ffile-prefix-map='+root+'=/usr/src/modular-native/independent','-c','source.c'])


if __name__=='__main__':unittest.main()
