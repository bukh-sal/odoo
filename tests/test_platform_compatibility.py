"""Image-observed platform API versions preserve old published releases."""
import copy
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
from modular_platform.projection import runtime_inputs
from modular_platform.resolution import PlanningError
from test_release_staging import staged_runtime


class PlatformCompatibilityTests(unittest.TestCase):
    def test_legacy_image_retains_platform_010_without_host_version_inference(self):
        runtime=staged_runtime([])
        _,environment,provenance=runtime_inputs(runtime,[])
        self.assertEqual(environment['platform_version'],'0.1.0')
        self.assertEqual(provenance['platform_version'],'0.1.0')

    def test_new_image_requires_its_matching_native_core_version(self):
        runtime=staged_runtime([]);runtime.update(platform_version='0.1.8',native_manifests={'mp_core':{'version':'19.0.0.1.8'}})
        _,environment,provenance=runtime_inputs(runtime,[])
        self.assertEqual(environment['platform_version'],'0.1.8');self.assertEqual(provenance['platform_version'],'0.1.8')
        runtime['native_manifests']['mp_core']['version']='19.0.0.1.7'
        with self.assertRaisesRegex(PlanningError,'platform/native core'):runtime_inputs(runtime,[])

    def test_invalid_static_version_never_becomes_authority(self):
        for value in [True,'0.1','v0.1.8','0.1.8\n',None]:
            runtime=staged_runtime([]);runtime['platform_version']=value
            with self.assertRaises(PlanningError):runtime_inputs(runtime,[])


if __name__=='__main__':unittest.main()
