"""Recovery review start fences and actual one-site checkpoint extraction."""
import copy
from datetime import datetime,timedelta,timezone
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.operator_os import OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.recovery_reviews import RecoveryReviews
from modular_platform.restore_filestore import restore
from modular_platform.native_executor import ARCHIVE_FILESTORE
from test_plans import ident

STAMP=datetime(2026,10,28,10,0,tzinfo=timezone.utc)
SOURCE='mp_disposable_r0_r1_current'
OTHER='mp_disposable_r0_r1_retained'
TARGET='mp_disposable_r0_r1_fresh_restore'


def archive(members):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as tar:
        for name,kind,raw in members:
            item=tarfile.TarInfo(name);item.type=kind
            if kind==tarfile.REGTYPE:item.size=len(raw)
            elif kind in (tarfile.SYMTYPE,tarfile.LNKTYPE):item.linkname=raw.decode()
            tar.addfile(item,io.BytesIO(raw) if kind==tarfile.REGTYPE else None)
    return output.getvalue()


class RecoveryReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.store=OperatorStore.initialize(Path(self.temporary.name)/'control',{ident(10):[ident(20)]})
        self.reviews=RecoveryReviews(self.store)
        self.payload={'schema_version':1,'action':'restore_to_fresh_database','operation_id':ident(500),
            'checkpoint_digest':'sha256:'+'a'*64,'configuration':{'deployment_id':ident(10),'site_id':ident(20)}}

    def test_actual_private_review_has_exact_nonextendable_start_deadline(self):
        decision=self.reviews.issue(self.payload,now=STAMP);digest=data_digest(decision)
        path=self.reviews.root/(decision['review']['review_id']+'.json');before=path.read_bytes()
        self.reviews.verify(decision,exact_hash=digest,current_payload=self.payload,now=STAMP+timedelta(seconds=899))
        for now in (STAMP-timedelta(seconds=1),STAMP+timedelta(seconds=900)):
            with self.assertRaisesRegex(OperatorError,'start lifetime'):
                self.reviews.verify(decision,exact_hash=digest,current_payload=self.payload,now=now)
        second=self.reviews.issue(self.payload,now=STAMP+timedelta(seconds=10))
        self.assertNotEqual(second['review']['review_id'],decision['review']['review_id'])
        self.assertEqual(path.read_bytes(),before)
        # A reserved execution can cross its start deadline; authority/revoke
        # checks still run at subsequent safe boundaries.
        self.reviews.check_reserved(decision,exact_hash=digest)

    def test_wrong_hash_fabrication_cross_operation_and_changed_state_fail_closed(self):
        decision=self.reviews.issue(self.payload,now=STAMP);digest=data_digest(decision)
        with self.assertRaisesRegex(OperatorError,'Exact reviewed'):
            self.reviews.verify(decision,exact_hash='sha256:'+'f'*64,current_payload=self.payload,now=STAMP)
        changed=copy.deepcopy(decision);changed['operation_id']=ident(501)
        with self.assertRaisesRegex(OperatorError,'Exact reviewed'):
            self.reviews.verify(changed,exact_hash=data_digest(changed),current_payload=self.payload,now=STAMP)
        with self.assertRaisesRegex(OperatorError,'actual state changed'):
            self.reviews.verify(decision,exact_hash=digest,current_payload=self.payload|{'checkpoint_digest':'sha256:'+'b'*64},now=STAMP)
        fabricated=copy.deepcopy(decision);fabricated['review']['expires_at']='2099-01-01T00:00:00Z'
        with self.assertRaisesRegex(OperatorError,'Exact reviewed'):
            self.reviews.verify(fabricated,exact_hash=data_digest(fabricated),current_payload=self.payload,now=STAMP)

    def test_revocation_and_policy_generation_fence_starts_and_running_boundaries(self):
        decision=self.reviews.issue(self.payload,now=STAMP);digest=data_digest(decision)
        self.reviews.revoke(decision,exact_hash=digest);self.reviews.revoke(decision,exact_hash=digest)
        with self.assertRaisesRegex(OperatorError,'revoked'):
            self.reviews.verify(decision,exact_hash=digest,current_payload=self.payload,now=STAMP)
        with self.assertRaisesRegex(OperatorError,'revoked'):self.reviews.check_reserved(decision,exact_hash=digest)
        other=self.reviews.issue(self.payload,now=STAMP)
        policy_path=self.store.root/'policy.json';policy=json.loads(policy_path.read_text());policy['authorization_generation']+=1
        policy_path.write_text(json.dumps(policy))
        with self.assertRaisesRegex(OperatorError,'authority changed'):
            self.reviews.verify(other,exact_hash=data_digest(other),current_payload=self.payload,now=STAMP)


class RecoveryFilestoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)/'filestore'

    def test_old_whole_project_checkpoint_selects_source_and_preserves_retained_directory(self):
        (self.root/OTHER).mkdir(parents=True);(self.root/OTHER/'existing').write_bytes(b'untouched')
        raw=archive([(f'filestore/{SOURCE}/aa/selected',tarfile.REGTYPE,b'checkpoint bytes'),
                     (f'filestore/{OTHER}/bb/other',tarfile.REGTYPE,b'do not restore')])
        result=restore(io.BytesIO(raw),self.root,SOURCE,TARGET)
        self.assertEqual(result['selected_files'],1);self.assertEqual(result['ignored_members'],1)
        self.assertEqual((self.root/TARGET/'aa/selected').read_bytes(),b'checkpoint bytes')
        self.assertEqual((self.root/OTHER/'existing').read_bytes(),b'untouched')
        self.assertFalse((self.root/TARGET/'bb').exists())

    def test_new_backup_child_archives_only_selected_database(self):
        for name in (SOURCE,OTHER):
            (self.root/name).mkdir(parents=True);(self.root/name/'marker').write_bytes(name.encode())
        result=subprocess.run([sys.executable,'-c',ARCHIVE_FILESTORE,SOURCE,str(self.root)],capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        with tarfile.open(fileobj=io.BytesIO(result.stdout),mode='r:gz') as tar:
            self.assertTrue(all(name.startswith('filestore/'+SOURCE) for name in tar.getnames()))
        restored=restore(io.BytesIO(result.stdout),self.root,SOURCE,TARGET)
        self.assertEqual(restored['selected_files'],1)

    def test_empty_checkpoint_and_real_cli_child(self):
        result=subprocess.run([sys.executable,str(ROOT/'packages/platform_sdk/modular_platform/restore_filestore.py'),SOURCE,TARGET,str(self.root)],
            input=archive([]),capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr.decode());self.assertEqual(json.loads(result.stdout)['selected_files'],0)
        self.assertTrue((self.root/TARGET).is_dir())

    def test_unsafe_members_links_and_duplicates_never_publish_a_target(self):
        cases=[[(f'filestore/{SOURCE}/../../escape',tarfile.REGTYPE,b'x')],
               [(f'/filestore/{SOURCE}/absolute',tarfile.REGTYPE,b'x')],
               [(f'filestore/{SOURCE}/link',tarfile.SYMTYPE,b'../../escape')],
               [(f'filestore/{SOURCE}/link',tarfile.LNKTYPE,b'filestore/other')],
               [(f'filestore/{OTHER}/fifo',tarfile.FIFOTYPE,b'')],
               [(f'filestore/{SOURCE}/one',tarfile.REGTYPE,b'x'),(f'filestore/{SOURCE}/ONE',tarfile.REGTYPE,b'y')]]
        for members in cases:
            with self.subTest(members=members),self.assertRaises(ValueError):restore(io.BytesIO(archive(members)),self.root,SOURCE,TARGET)
            self.assertFalse((self.root/TARGET).exists())

    def test_existing_target_and_invalid_source_are_never_overwritten(self):
        (self.root/TARGET).mkdir(parents=True);(self.root/TARGET/'marker').write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError,'Never overwrite'):restore(io.BytesIO(archive([])),self.root,SOURCE,TARGET)
        self.assertEqual((self.root/TARGET/'marker').read_bytes(),b'keep')
        with self.assertRaisesRegex(ValueError,'Distinct canonical'):restore(io.BytesIO(archive([])),self.root,SOURCE,SOURCE)


if __name__=='__main__':unittest.main()
