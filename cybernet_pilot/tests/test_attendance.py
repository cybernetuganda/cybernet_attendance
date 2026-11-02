import csv,io,sys,tempfile,unittest
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as a
from auth_support import sign_in
class AttendanceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();a.DB=Path(self.tmp.name)/'db.sqlite3';a.init()
  with a.db() as c:
   c.execute("INSERT INTO students VALUES('001','Alice','P5','',0)")
   for i in range(32):c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)',(str(i),'001','Alice','IN' if i%2==0 else 'OUT',f'2026-10-29T09:{i:02d}:00','K40','Missing guardian consent or phone'))
   c.execute("INSERT INTO events VALUES('other','002','Bob','IN','2026-10-28T09:00:00','DEMO','Eligible')")
  self.client=a.app.test_client();sign_in(a,self.client)
 def tearDown(self):self.tmp.cleanup()
 def test_pagination(self):
  with a.db() as c:
   from werkzeug.datastructures import MultiDict
   v=a.attendance_view(c,MultiDict({'att_class':'P5','att_page':'2'}));self.assertEqual(v['att_total'],32);self.assertEqual(len(v['att_rows']),7)
 def test_combined_filter_and_export(self):
  r=self.client.get('/export?att_student=Alice&att_direction=OUT&att_from=2026-10-29&att_to=2026-10-29');rows=list(csv.reader(io.StringIO(r.data.decode())));self.assertEqual(len(rows),17)
  self.assertTrue(all(x[3]=='OUT' for x in rows[1:]))
 def test_literal_sql_text_and_no_message(self):
  r=self.client.get('/export?att_q=%27%20OR%201%3D1');self.assertEqual(len(list(csv.reader(io.StringIO(r.data.decode())))),1)
  r=self.client.get('/export?att_status=NO_MESSAGE');self.assertEqual(len(list(csv.reader(io.StringIO(r.data.decode())))),34)
 def test_invalid_dates(self):
  self.assertEqual(self.client.get('/export?att_from=bad').status_code,400)
  r=self.client.get('/attendance?att_from=2026-12-01&att_to=2026-01-01');self.assertEqual(r.status_code,200);self.assertIn(b'From date must not',r.data)
 def test_live_controls_outside_replaceable_panel(self):
  r=self.client.get('/attendance');self.assertEqual(r.status_code,200)
  text=r.data.decode();self.assertLess(text.index('id="attendance-filters"'),text.index('id="live-attendance"'));self.assertNotIn('location.reload',text)
