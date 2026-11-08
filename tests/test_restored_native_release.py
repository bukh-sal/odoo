"""Guard the distinct checkpoint-job and restored-publication identities."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.dispatch_jobs_maintenance import reconcile_transaction

SOURCE='sha256:'+'a'*64
TARGET='sha256:'+'b'*64
SITE='00000000-0000-4000-8000-000000000001'


class Cursor:
    def __init__(self,rows=None):self.rows=[(SITE,TARGET,'paused')] if rows is None else rows;self.updates=[]
    def execute(self,query,args=None):
        if query.startswith('UPDATE'):
            self.updates.append(args);self.rows=[(s,args[0],state) for s,_,state in self.rows]
    def fetchall(self):return self.rows


class RestoredReleaseTests(unittest.TestCase):
    def data(self,**changes):return dict(site_id=SITE,previous_release=TARGET,release_digest=TARGET,source_release=SOURCE)|changes
    def test_valid_restore_invokes_original_identity_and_finishes_closed_on_target(self):
        cr=Cursor()
        def invoke(previous,target):
            self.assertEqual((previous,target),(SOURCE,TARGET));self.assertEqual(cr.rows,[(SITE,SOURCE,'paused')])
            cr.rows=[(SITE,TARGET,'paused')];return {'resumable':1}
        self.assertEqual(reconcile_transaction(cr,self.data(),invoke),{'resumable':1})
        self.assertEqual(cr.updates,[[SOURCE,SITE]])

    def test_normal_forward_does_not_retag_control(self):
        cr=Cursor();data=self.data();data.pop('source_release')
        self.assertEqual(reconcile_transaction(cr,data,lambda prior,target:(prior,target)),(TARGET,TARGET))
        self.assertEqual(cr.updates,[])

    def test_source_must_be_a_canonical_hash(self):
        for source in [None,True,{},'',SOURCE.upper(),SOURCE+'x']:
            cr=Cursor()
            with self.subTest(source=source),self.assertRaises(ValueError):reconcile_transaction(cr,self.data(source_release=source),lambda *a:self.fail('invoked'))
            self.assertEqual(cr.updates,[])

    def test_source_extension_is_confined_to_fresh_restored_publication(self):
        cr=Cursor()
        with self.assertRaises(ValueError):reconcile_transaction(cr,self.data(previous_release=SOURCE),lambda *a:self.fail('invoked'))
        self.assertEqual(cr.updates,[])

    def test_wrong_missing_or_multiple_control_rows_refuse_before_callback(self):
        for rows in [[],[(SITE,SOURCE,'paused')],[('other',TARGET,'paused')],[(SITE,TARGET,'paused')]*2]:
            cr=Cursor(rows)
            with self.subTest(rows=rows),self.assertRaises(ValueError):reconcile_transaction(cr,self.data(),lambda *a:self.fail('invoked'))
            self.assertEqual(cr.updates,[])

    def test_enabled_or_unknown_control_never_admits_restore_classification(self):
        for state in ['enabled','unknown',None]:
            cr=Cursor([(SITE,TARGET,state)])
            with self.subTest(state=state),self.assertRaises(ValueError):reconcile_transaction(cr,self.data(),lambda *a:self.fail('invoked'))
            self.assertEqual(cr.updates,[])

    def test_wrong_final_identity_or_open_control_never_returns_success(self):
        for rows in [[(SITE,SOURCE,'paused')],[(SITE,TARGET,'enabled')],[],[('other',TARGET,'paused')]]:
            cr=Cursor()
            def invoke(*args):cr.rows=rows;return {}
            with self.subTest(rows=rows),self.assertRaises(ValueError):reconcile_transaction(cr,self.data(),invoke)

    def test_classification_exception_propagates_to_callers_transaction(self):
        cr=Cursor()
        def failed(*args):raise RuntimeError('classification failed')
        with self.assertRaisesRegex(RuntimeError,'classification failed'):reconcile_transaction(cr,self.data(),failed)
        # Actual PostgreSQL rollback of this temporary tag is tested separately.

if __name__=='__main__':unittest.main()
