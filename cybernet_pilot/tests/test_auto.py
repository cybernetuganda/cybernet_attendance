import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as a
class AutoTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();a.DB=Path(self.tmp.name)/'test.db';a.init();self.old=a.MODE;a.MODE='device';a.auto_sms=True
  with a.db() as c:c.execute("INSERT INTO students VALUES('1','Test','P5','+256700000000',1)")
 def tearDown(self):a.MODE=self.old;a.auto_sms=False;self.tmp.cleanup()
 def status(self):
  with a.db() as c:return c.execute('SELECT status FROM messages').fetchone()[0]
 def test_send_once(self):
  a.ingest('1',a.now(),0)
  with patch('sms_provider.prepare',return_value=('mock',)),patch('sms_provider.submit',return_value=('ACCEPTED','test')) as send:
   self.assertTrue(a.dispatch_once());self.assertFalse(a.dispatch_once());self.assertEqual(send.call_count,1);self.assertEqual(self.status(),'ACCEPTED')
 def test_off_no_backlog(self):
  a.auto_sms=False;a.ingest('1',a.now(),0);a.auto_sms=True
  with patch('sms_provider.submit') as send:a.dispatch_once();send.assert_not_called()
  self.assertEqual(self.status(),'DRY_RUN')
 def test_consent_revoked(self):
  a.ingest('1',a.now(),0)
  with a.db() as c:c.execute('UPDATE students SET consent=0')
  with patch('sms_provider.submit') as send:a.dispatch_once();send.assert_not_called()
  self.assertEqual(self.status(),'CANCELLED')
 def test_unknown_not_retried(self):
  a.ingest('1',a.now(),0)
  with patch('sms_provider.prepare',return_value=('mock',)),patch('sms_provider.submit',return_value=('UNKNOWN','test')) as send:
   a.dispatch_once();a.dispatch_once();self.assertEqual(send.call_count,1)
 def test_restart_does_not_resend(self):
  a.ingest('1',a.now(),0);a.recover_dispatch();self.assertEqual(self.status(),'CANCELLED')
 def test_pause_and_ack(self):
  a.ingest('1',a.now(),0)
  with a.app.test_client() as c:
   c.get('/')
   with c.session_transaction() as sess:token=sess['csrf']
   c.post('/sms-control',data={'csrf':token,'action':'pause'});self.assertFalse(a.auto_sms);self.assertEqual(self.status(),'CANCELLED')
   c.post('/sms-control',data={'csrf':token,'action':'enable'});self.assertFalse(a.auto_sms)
