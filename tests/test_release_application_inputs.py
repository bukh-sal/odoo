"""Explicit release inputs fail before any kit/Docker mutation."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'release'))
from application_inputs import COMPARISONS,load_application_inputs


class ReleaseApplicationInputs(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'source';self.root.mkdir()
        for name in ['.dockerignore','LICENSE','COPYRIGHT','tools/sample.py']:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('source')
        self.repro=dict(result='passed_second_no_cache_build_declared_inventory_reproduction',acceptance=['BOOT-02'],
            reference_image='sha256:'+'a'*64,candidate_image='sha256:'+'b'*64,dependency_base='sha256:'+'c'*64,
            inventory_digest='sha256:'+'d'*64,comparisons={key:True for key in COMPARISONS})
        self.build=dict(state='built',result='built_not_deployed',image_id=self.repro['reference_image'],
            dependency_base_image=self.repro['dependency_base'],inventory_digest=self.repro['inventory_digest'],
            source_sha256={p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()})
        self.r=Path(self.temp.name)/'repro.json';self.b=Path(self.temp.name)/'build.json'

    def load(self):
        self.r.write_text(json.dumps(self.repro));self.b.write_text(json.dumps(self.build))
        return load_application_inputs(self.root,self.r,self.b)

    def test_complete_explicit_identity_and_source_pass(self):
        value=self.load();self.assertEqual(value['source_files_verified'],4)
        self.assertEqual(value['reproduction_bytes'],self.r.read_bytes())
        self.assertEqual(value['build_sha256'],hashlib.sha256(self.b.read_bytes()).hexdigest())

    def test_every_required_comparison_is_true_not_truthy(self):
        for key in COMPARISONS:
            for value in [False,1,'true',None]:
                with self.subTest(key=key,value=value):
                    self.repro['comparisons'][key]=value
                    with self.assertRaises(ValueError):self.load()
            self.repro['comparisons'][key]=True

    def test_unqualified_or_missing_acceptance_refused(self):
        self.repro['acceptance']=[]
        with self.assertRaises(ValueError):self.load()
        self.repro['acceptance']=['BOOT-02'];self.repro['result']='built'
        with self.assertRaises(ValueError):self.load()

    def test_mutable_image_and_wrong_identity_refused(self):
        for key in ['reference_image','candidate_image','dependency_base','inventory_digest']:
            old=self.repro[key];self.repro[key]='platform:latest'
            with self.subTest(key=key),self.assertRaises(ValueError):self.load()
            self.repro[key]=old
        for key in ['image_id','dependency_base_image','inventory_digest']:
            old=self.build[key];self.build[key]='sha256:'+'e'*64
            with self.subTest(key=key),self.assertRaises(ValueError):self.load()
            self.build[key]=old

    def test_modified_source_refused(self):
        (self.root/'tools/sample.py').write_text('changed')
        with self.assertRaisesRegex(ValueError,'differs from selected build'):self.load()

    def test_new_or_omitted_source_file_refused(self):
        path=self.root/'tools/new.py';path.write_text('new')
        with self.assertRaisesRegex(ValueError,'input set differs'):self.load()
        path.unlink();self.build['source_sha256'].pop('tools/sample.py')
        with self.assertRaisesRegex(ValueError,'input set differs'):self.load()

    def test_noncanonical_or_traversal_source_path_refused(self):
        original=copy.deepcopy(self.build)
        for name in ['../LICENSE','/LICENSE','tools/../LICENSE','tools\\sample.py','C:/LICENSE']:
            self.build=copy.deepcopy(original);self.build['source_sha256'][name]='a'*64
            with self.subTest(name=name),self.assertRaises(ValueError):self.load()

    def test_duplicate_and_oversized_receipt_refused(self):
        self.load();self.r.write_text('{"result":1,"result":2}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):load_application_inputs(self.root,self.r,self.b)
        self.r.write_bytes(b' '*(4*1024*1024+1))
        with self.assertRaisesRegex(ValueError,'Oversized'):load_application_inputs(self.root,self.r,self.b)

    def test_source_refresh_cannot_change_kit_image_base_or_inventory(self):
        import refresh_draft
        self.load();kit=self.root/'.local/releases/draft';kit.mkdir(parents=True)
        original=dict(images=dict(application=dict(image_id=self.repro['reference_image']),
                                   dependency_base=dict(image_id=self.repro['dependency_base'])),
                      application_inventory_digest=self.repro['inventory_digest'])
        for key in ['application','dependency_base','inventory']:
            images=copy.deepcopy(original)
            if key=='inventory':images['application_inventory_digest']='sha256:'+'e'*64
            else:images['images'][key]['image_id']='sha256:'+'e'*64
            raw=json.dumps(images).encode();(kit/'images.json').write_bytes(raw)
            manifest=dict(format='modular-platform-local-kit-1',stage='draft_requires_clean_install_and_G7_closure',
                          source_commit='0'*40,files={'images.json':dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())})
            raw=json.dumps(manifest).encode();(kit/'kit-inventory.json').write_bytes(raw)
            (kit/'SHA256SUMS').write_text(manifest['files']['images.json']['sha256']+'  images.json\n'+hashlib.sha256(raw).hexdigest()+'  kit-inventory.json\n')
            before={p.name:p.read_bytes() for p in kit.iterdir()}
            args=['refresh_draft.py',str(kit),'--receipt',str(self.root/'unused-receipt.json'),
                  '--application-reproduction',str(self.r),'--application-build',str(self.b)]
            with self.subTest(key=key),patch.object(refresh_draft,'ROOT',self.root),patch.object(sys,'argv',args), \
                    patch.object(refresh_draft.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as calls:
                with self.assertRaisesRegex(ValueError,'Kit image differs'):refresh_draft.main()
                self.assertEqual(calls.call_count,1)
                self.assertEqual(calls.call_args.args[0][:2],['git','diff'])
            self.assertEqual(before,{p.name:p.read_bytes() for p in kit.iterdir()})
            self.assertFalse((self.root/'unused-receipt.json').exists())


if __name__=='__main__':unittest.main()
