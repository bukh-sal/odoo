"""A final owned extraction seal cannot borrow incomplete/historical gates."""
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'release'))
from seal_local import qualification_stage


class ReleaseQualification(unittest.TestCase):
    def setUp(self):
        self.ar=dict(result='passed_owned_addon_cleanup_qualification',
            gates={f'AR-0{i}':'passed' for i in range(1,6)},
            checks={f'AR-{letter}':'passed' for letter in 'ABCDEFGHIJKLMNOP'},
            contract_revision=20,core_version='0.1.47')

    def test_current_ar_and_historical_cf_have_distinct_seal_profiles(self):
        self.assertEqual(qualification_stage(self.ar),'qualified_local_foundation_ar_1')
        cf=dict(result='passed_consolidated_foundation_qualification',
            gates={f'CF-0{i}':'passed' for i in range(1,6)},checks={f'CF-{letter}':'passed' for letter in 'ABCDEFGHIJKL'})
        self.assertEqual(qualification_stage(cf),'qualified_local_foundation_cf_1')
        forged=copy.deepcopy(self.ar);forged['gates']=cf['gates']
        with self.assertRaises(ValueError):qualification_stage(forged)

    def test_every_required_ar_check_and_gate_must_really_be_declared_passed(self):
        for field in ('checks','gates'):
            for name in self.ar[field]:
                d=copy.deepcopy(self.ar);d[field][name]='not_tested'
                with self.subTest(field=field,name=name),self.assertRaises(ValueError):qualification_stage(d)
        for field,value in [('result','draft'),('contract_revision',19),('core_version','0.1.46')]:
            d=copy.deepcopy(self.ar);d[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):qualification_stage(d)

    def test_tasks_release_cannot_borrow_old_or_partial_qualification(self):
        tasks=dict(result='passed_aurora_tasks_release_qualification',
            gates={f'AT-0{i}':'passed' for i in range(1,6)},
            checks={f'AT-{letter}':'passed' for letter in 'ABCDEFGHIJKLMN'},
            contract_revision=25,core_version='0.1.49',application=dict(plugin_id='dev.aurora.tasks',version='0.2.2',
                digest='sha256:71c97db1113cba7ba664171962208e429ecff66feb2ef8433e966a1ef20aa52c'))
        self.assertEqual(qualification_stage(tasks),'qualified_local_foundation_tasks_1')
        for field in ('gates','checks'):
            for key in tasks[field]:
                changed=copy.deepcopy(tasks);changed[field][key]='not_run'
                with self.subTest(field=field,key=key),self.assertRaises(ValueError):qualification_stage(changed)
        for field,value in [('gates',self.ar['gates']),('checks',self.ar['checks']),('contract_revision',24),
                            ('core_version','0.1.48'),('application',dict(tasks['application'],version='0.2.1'))]:
            changed=copy.deepcopy(tasks);changed[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):qualification_stage(changed)


if __name__=='__main__':unittest.main()
