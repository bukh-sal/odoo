"""Run host tests with explicit trusted project imports under isolated Python."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'packages/platform_sdk')]

if __name__=='__main__':
    loader=unittest.TestLoader()
    suite=loader.discover(str(ROOT/'tests'),pattern='test_*.py')
    if loader.errors:raise RuntimeError('\n'.join(loader.errors))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
