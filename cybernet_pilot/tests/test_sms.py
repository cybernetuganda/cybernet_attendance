import os, unittest
from unittest.mock import patch, Mock
from sms_provider import prepare, submit
class SmsTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'SMS_PROVIDER':'pandora','PANDORA_USERNAME':'test','PANDORA_PASSWORD':'test-secret','PANDORA_SENDER':'Cybernet'},clear=True); self.env.start()
 def tearDown(self):self.env.stop()
 def test_fields_and_encoding(self):
  p=prepare('+256700000000','A & B entry');self.assertEqual(p[2]['number'],'256700000000');self.assertEqual(p[2]['message'],'A & B entry');self.assertEqual(p[2]['sender'],'Cybernet')
 def test_post_sender_variant(self):
  os.environ['PANDORA_SENDER_FIELD']='sender_id';self.assertIn('sender_id',prepare('+256700000000','Test')[2])
 def test_validation(self):
  for text in ['x'*161,'Hello ⚠']:
   with self.assertRaises(ValueError):prepare('+256700000000',text)
 def test_response_states(self):
  p=prepare('+256700000000','Test')
  for value,status in [(True,'ACCEPTED'),(False,'REJECTED'),('true','UNKNOWN')]:
   with patch('sms_provider.requests.post',return_value=Mock(status_code=200,ok=True,json=lambda:{'success':value})) as req:
    self.assertEqual(submit(p)[0],status);self.assertFalse(req.call_args.kwargs['allow_redirects'])
 def test_uncertain_never_retried(self):
  with patch('sms_provider.requests.post',side_effect=TimeoutError) as req:
   self.assertEqual(submit(prepare('+256700000000','Test'))[0],'UNKNOWN');self.assertEqual(req.call_count,1)
 def test_redirect_diagnostic_hides_query(self):
  response=Mock(status_code=302,headers={'Location':'https://sms.thepandoranetworks.com/API/send_sms/?password=secret'})
  with patch('sms_provider.requests.post',return_value=response):
   status,detail=submit(prepare('+256700000000','Test'));self.assertEqual(status,'UNKNOWN');self.assertIn('302',detail);self.assertNotIn('secret',detail)
 def test_non_json_diagnostic(self):
  response=Mock(status_code=200);response.json.side_effect=ValueError()
  with patch('sms_provider.requests.post',return_value=response):
   status,detail=submit(prepare('+256700000000','Test'));self.assertEqual(status,'UNKNOWN');self.assertIn('not JSON',detail)
