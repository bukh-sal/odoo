"""Catalog and independent operator authority have separate explicit CLI paths."""
import contextlib,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import modular

class CurrentInstallCLI(unittest.TestCase):
    def invoke(self,operator_store=False,reader_error=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'target.json';target.write_text('{}')
            catalog=root/'catalog';control=root/'independent-control'
            args=['--config',str(root/'trust.json'),'plugin','plan-current-install','--deployment-config',str(target),
                '--store',str(catalog),'--site','site','--workspace','workspace','--plugin','org.test.a','--version','1.0.0','--digest','sha256:'+'a'*64]
            if operator_store:args+=['--operator-store',str(control)]
            observer=Mock();observer.read.return_value={'sites':['native-site']};observer.state.return_value={'state':'observed'}
            with patch.object(modular,'configuration',return_value='validator'),patch.object(modular,'Catalog') as cat,\
                    patch('modular_platform.deployment.DockerObserver',return_value=observer) as legacy,\
                    patch('modular_platform.worker_operator.operator_observer',return_value=observer) as independent,\
                    patch('modular_platform.operator_store.OperatorStore',return_value='protected-control') as store,\
                    patch('modular_platform.lifecycle_planning.prepare_current_image_install',return_value={'result':'fixture'}) as planner,\
                    contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                cat.return_value.snapshot.return_value=['catalog-artifact']
                if reader_error:independent.side_effect=ValueError('authority refused')
                result=modular.main(args)
                if reader_error:
                    self.assertEqual(result,2);planner.assert_not_called();legacy.assert_not_called();return
                self.assertEqual(result,0);cat.assert_called_once_with(catalog,'validator',readonly=True)
                planner.assert_called_once();self.assertEqual(planner.call_args.args,({'state':'observed'},['native-site'],['catalog-artifact']))
                if operator_store:
                    store.assert_called_once_with(control);independent.assert_called_once_with('protected-control',target);legacy.assert_not_called()
                else:
                    store.assert_not_called();independent.assert_not_called();legacy.assert_called_once_with({})

    def test_explicit_control_store_uses_fresh_independent_reader_and_separate_catalog(self):self.invoke(True)
    def test_legacy_native_option_does_not_infer_or_open_control_store(self):self.invoke()
    def test_independent_refusal_cannot_fall_back_to_legacy_reader(self):self.invoke(True,True)

if __name__=='__main__':unittest.main()
