"""Known secrets are found across encodings/chunks without exposing a value."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('mp_secret_scan',ROOT/'tools/secret_scan.py');m=importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name]=m;spec.loader.exec_module(m)


class SecretScanTests(unittest.TestCase):
    def setUp(self):self.value=secrets.token_urlsafe(32).encode();self.scanner=m.Scanner(secrets.token_bytes(32),{'fixture-generated':self.value})

    def test_known_plain_UTF16_and_encoded_scalar_are_detected(self):
        import base64
        for raw in [self.value,self.value.decode().encode('utf-16le'),self.value.decode().encode('utf-16be'),base64.b64encode(self.value),base64.b64encode(b'{"password":"'+self.value+b'"}')]:
            with self.subTest(size=len(raw)):self.assertTrue(any(f['rule']=='known-generated-secret' for f in self.scanner.inspect_bytes(raw,'fixture')))

    def test_reports_and_even_locations_never_contain_matched_value(self):
        found=self.scanner.inspect_bytes(self.value,'path/'+self.value.decode());text=json.dumps(found).encode();self.assertNotIn(self.value,text);self.assertIn(b'<redacted>',text)

    def test_actual_ripgrep_matches_binary_UTF16_not_only_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);patterns=root/'patterns';self.scanner.write_patterns(patterns);payload=root/'payload.bin';payload.write_bytes(b'\0before'+self.value.decode().encode('utf-16le')+b'\0after')
            self.assertEqual([str(payload)],self.scanner.candidates([payload],patterns))

    def test_explicit_ripgrep_executable_is_selected_as_one_argv_element(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);patterns=root/'patterns';self.scanner.write_patterns(patterns);payload=root/'payload.bin';payload.write_bytes(b'payload');executable=root/'local rg.exe';executable.write_bytes(b'')
            with patch.dict(os.environ,{'MP_SECRET_SCAN_RG':str(executable)}),patch.object(m.subprocess,'run') as run:
                run.return_value=m.subprocess.CompletedProcess([str(executable)],0,stdout=b'',stderr=b'')
                self.assertEqual(self.scanner.candidates([payload],patterns),[])
                command=run.call_args.args[0]
                self.assertIsInstance(command,list)
                self.assertEqual(command[0],str(executable))
                self.assertEqual(run.call_args.kwargs.get('shell',False),False)

    def test_configured_ripgrep_must_name_an_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            missing=Path(directory)/'missing-rg.exe'
            with patch.dict(os.environ,{'MP_SECRET_SCAN_RG':str(missing)}):
                with self.assertRaisesRegex(RuntimeError,'MP_SECRET_SCAN_RG'):
                    m.rg_executable()

    def test_missing_default_ripgrep_fails_closed(self):
        with patch.dict(os.environ,{'PATH':''},clear=True):
            with self.assertRaisesRegex(RuntimeError,'ripgrep'):
                m.rg_executable()

    def test_cross_chunk_match_and_dedup_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'data';path.write_bytes(b'x'*(4*1024*1024-12)+self.value+b'after');found=self.scanner.inspect_file(path)
            known=[f for f in found if f['rule']=='known-generated-secret'];self.assertEqual(len(known),1);self.assertEqual(known[0]['offset'],4*1024*1024-12)

    def test_private_key_and_literal_detections_are_redacted(self):
        value=b'-----BEGIN PRIVATE KEY-----\nSYNTHETIC_ONLY\n-----END PRIVATE KEY-----\npassword="SYNTHETIC_NEGATIVE_LITERAL"'
        found=self.scanner.inspect_bytes(value,'negative-fixture');self.assertEqual({f['rule'] for f in found},{'private-key-marker','credential-literal'});self.assertNotIn('SYNTHETIC_NEGATIVE_LITERAL',json.dumps(found))

    def test_credential_collection_never_treats_password_UI_sources_as_values(self):
        for name in ['password_field.js','password_field.xml','auth_password_policy.pot','password.css']:
            self.assertFalse(m.is_credential_file(name,b'public source containing password support'))
        self.assertTrue(m.is_credential_file('password-alice',self.value+b'\n'))
        self.assertFalse(m.is_credential_file('password-alice',b'line1\n'+self.value))


if __name__=='__main__':unittest.main()
