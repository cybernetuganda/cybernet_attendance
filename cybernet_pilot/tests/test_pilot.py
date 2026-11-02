import sys, tempfile, unittest
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as a
from auth_support import sign_in
class PilotTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); a.DB=Path(self.temp.name)/'test.db'; a.init()
  with a.db() as c:c.execute("INSERT INTO students VALUES('1001','Test Student','P5','+256700000000',1)")
 def tearDown(self):self.temp.cleanup()
 def count(self):
  with a.db() as c:return c.execute('SELECT COUNT(*) FROM messages').fetchone()[0]
 def test_duplicate_and_repeat(self):
  t=a.now(); self.assertTrue(a.ingest('1001',t,0)); self.assertFalse(a.ingest('1001',t,0)); a.ingest('1001',t+timedelta(seconds=1),0); self.assertEqual(self.count(),1)
 def test_old_future_unknown_unmapped_baseline(self):
  t=a.now(); a.ingest('1001',t-timedelta(days=1),0); a.ingest('1001',t+timedelta(days=1),0); a.ingest('1001',t,9); a.ingest('999',t,0); a.ingest('1001',t,1,historical=True); self.assertEqual(self.count(),0)
 def test_consent_required(self):
  with a.db() as c:c.execute('UPDATE students SET consent=0')
  a.ingest('1001',a.now(),0); self.assertEqual(self.count(),0)
 def test_in_out_and_dashboard(self):
  t=a.now(); a.ingest('1001',t,0); a.ingest('1001',t,1); self.assertEqual(self.count(),2)
  with a.app.test_client() as c:
   sign_in(a,c)
   self.assertEqual(c.get('/').status_code,200); self.assertEqual(c.post('/demo',data={}).status_code,403)
 def test_first_poll_baseline_then_new_scan(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  class Connection:
   def get_attendance(self):return logs
   def disconnect(self):pass
  t=a.now(); logs=[SimpleNamespace(user_id='1001',timestamp=t-timedelta(seconds=10),punch=0)]
  with patch.object(a,'connect',return_value=Connection()):
   a.poll_once(); self.assertEqual(self.count(),0)
   logs.append(SimpleNamespace(user_id='1001',timestamp=t,punch=1));a.poll_once();a.poll_once();self.assertEqual(self.count(),1)
if __name__=='__main__':unittest.main()
