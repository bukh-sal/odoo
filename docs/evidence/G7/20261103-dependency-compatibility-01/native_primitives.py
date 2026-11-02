"""Actual unchanged pinned Odoo/SDK interfaces against isolated candidate wheels."""
import base64,io,json,time,unittest
from uuid import uuid4

class NativeDependencyCompatibility(unittest.TestCase):
 def test_framework_import_and_native_types(self):
  import odoo
  from odoo import api,fields,models,release
  self.assertTrue(release.version.startswith('19.0'));self.assertTrue(api.Environment);self.assertTrue(fields.Char);self.assertTrue(models.Model)
 def test_native_image_png_jpeg_gif_processing(self):
  from PIL import Image
  from odoo.tools.image import image_process
  for fmt in ['PNG','JPEG','GIF']:
   data=io.BytesIO();Image.new('RGB',(16,12),(30,80,140)).save(data,format=fmt)
   result=image_process(data.getvalue(),size=(8,8),verify_resolution=True,output_format='PNG')
   with Image.open(io.BytesIO(result)) as image:self.assertEqual(image.size,(8,6));self.assertEqual(image.format,'PNG')
 def test_native_pdf_existing_pypdf_adapter_and_merge(self):
  from odoo.tools import pdf
  self.assertEqual(pdf.SUBMOD,'._pypdf')
  writer=pdf.PdfWriter();writer.addBlankPage(width=100,height=150);writer.addMetadata({'/Title':'Compatibility fixture'})
  data=io.BytesIO();writer.write(data);raw=data.getvalue()
  reader=pdf.PdfFileReader(io.BytesIO(raw),strict=False);self.assertEqual(reader.getNumPages(),1)
  merged=pdf.merge_pdf([raw,raw]);self.assertEqual(pdf.PdfFileReader(io.BytesIO(merged),strict=False).getNumPages(),2)
 def test_native_pdf_encryption_with_candidate_crypto(self):
  from odoo.tools import pdf
  writer=pdf.PdfWriter();writer.addBlankPage(width=100,height=150);writer.encrypt('fixture-only-password',algorithm='AES-256')
  data=io.BytesIO();writer.write(data);reader=pdf.PdfFileReader(io.BytesIO(data.getvalue()),strict=False)
  self.assertTrue(reader.isEncrypted);self.assertTrue(reader.decrypt('fixture-only-password'));self.assertEqual(reader.getNumPages(),1)
 def test_native_html_sanitizer_and_lxml(self):
  from odoo.tools.mail import html_sanitize
  from lxml import etree
  value=str(html_sanitize('<p>Safe<script>alert(1)</script><a href="javascript:alert(2)">Link</a></p>',sanitize_attributes=True))
  self.assertNotIn('<script',value);self.assertNotIn('javascript:',value);self.assertIn('Safe',value)
  self.assertEqual(etree.fromstring(b'<root><item>ok</item></root>').findtext('item'),'ok')
 def test_werkzeug_wsgi_json_cookie_and_multipart(self):
  from werkzeug.test import Client
  from werkzeug.wrappers import Request,Response
  @Request.application
  def app(request):
   response=Response(json.dumps(dict(path=request.path,values=list(request.form.getlist('value')))),content_type='application/json')
   response.set_cookie('fixture','value',httponly=True,samesite='Lax');return response
  response=Client(app,Response).post('/probe',data={'value':'safe'},content_type='multipart/form-data')
  self.assertEqual(response.status_code,200);self.assertEqual(response.json,dict(path='/probe',values=['safe']))
  self.assertIn('HttpOnly',response.headers['Set-Cookie'])
 def test_cbor_canonical_and_unicode_roundtrip(self):
  import cbor2
  value={'key':[1,True,None,'مرحبا',b'bytes']};self.assertEqual(cbor2.loads(cbor2.dumps(value,canonical=True)),value)
 def test_actual_worker_token_validator_rs256_scope_and_expiry(self):
  import jwt
  from cryptography.hazmat.primitives.asymmetric import rsa
  from modular_platform.tokens import verify_worker_token
  request=REQUEST;now=int(time.time());scope={k:request[k] for k in ['site_id','workspace_id','installation_id','endpoint_generation']}
  key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  claims=dict(iss='modular-platform-host-v1',aud='mp-document-stats-v1',sub=scope['installation_id'],jti=str(uuid4()),iat=now,nbf=now,exp=now+120,methods=['analyze'],**scope)
  token=jwt.encode(claims,key,algorithm='RS256',headers={'kid':'probe-only'})
  self.assertEqual(verify_worker_token(token,key.public_key(),key_id='probe-only',request=request)['workspace_id'],scope['workspace_id'])
  with self.assertRaises(Exception):verify_worker_token(token,key.public_key(),key_id='wrong',request=request)
  forged={**claims,'workspace_id':str(uuid4())};token=jwt.encode(forged,key,algorithm='RS256',headers={'kid':'probe-only'})
  with self.assertRaises(Exception):verify_worker_token(token,key.public_key(),key_id='probe-only',request=request)
