import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as a
from auth_support import sign_in

class UiTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old_db=a.DB;self.old_mode=a.MODE
  a.DB=Path(self.tmp.name)/'ui.db';a.MODE='demo';a.init();self.client=a.app.test_client();sign_in(a,self.client)
 def tearDown(self):
  a.DB=self.old_db;a.MODE=self.old_mode;self.tmp.cleanup()
 def test_six_pages_and_empty_pending_states(self):
  for path,title in [('/','Dashboard'),('/attendance','Attendance'),('/students','Students'),('/guardians','Guardians'),('/terminals','Terminals'),('/settings','Settings')]:
   response=self.client.get(path);self.assertEqual(response.status_code,200,path)
   self.assertIn(title,response.data.decode())
  dashboard=self.client.get('/').data.decode()
  self.assertIn('No scans recorded yet',dashboard)
  self.assertIn('Absent today',dashboard);self.assertIn('Pending',dashboard)
  self.assertNotIn('Amara Nakato',dashboard)
  self.assertIn('Names Pending',self.client.get('/guardians').data.decode())
 def test_real_counts_and_today_filter(self):
  with a.db() as c:c.execute("INSERT INTO students VALUES('1','Student One','P5','+256700000000',1)")
  a.ingest('1',a.now(),0,'DEMO');a.ingest('1',a.now(),1,'DEMO')
  dashboard=self.client.get('/').data.decode();self.assertIn('Recorded scans today',dashboard);self.assertIn('Student One',dashboard)
  self.assertIn('<strong>1</strong><span>IN</span>',dashboard)
  self.assertIn('<strong>1</strong><span>OUT</span>',dashboard)
  attendance=self.client.get('/attendance').data.decode();self.assertIn('Student One',attendance);self.assertIn('IN',attendance)
  guardians=self.client.get('/guardians').data.decode();self.assertIn('+256700000000',guardians);self.assertIn('Student One',guardians)
 def test_direction_tabs_preserve_filters(self):
  html=self.client.get('/attendance?att_range=all&att_q=Alice&att_class=P5').data.decode()
  self.assertIn('att_q=Alice&amp;att_class=P5&amp;att_direction=IN',html)
  self.assertIn('att_q=Alice&amp;att_class=P5&amp;att_direction=OUT',html)
 def test_legacy_links_redirect_and_controls_remain_protected(self):
  self.assertEqual(self.client.get('/?student_q=x').location,'/students?student_q=x')
  self.assertEqual(self.client.get('/?att_q=x').location,'/attendance?att_q=x')
  self.assertEqual(self.client.post('/students',data={'id':'1'}).status_code,403)
