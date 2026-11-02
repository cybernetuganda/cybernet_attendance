import io,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as a
from auth_support import sign_in
class StudentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();a.DB=Path(self.tmp.name)/'test.db';a.init();self.c=a.app.test_client();self.token=sign_in(a,self.c)
 def tearDown(self):self.tmp.cleanup()
 def post(self,path,data):return self.c.post(path,data=dict(data,csrf=self.token),follow_redirects=True)
 def student(self):return dict(id='001',name='Student A',class_name='P5',phone='+256700000000',consent='on')
 def row(self):
  with a.db() as c:return c.execute("SELECT * FROM students WHERE id='001'").fetchone()
 def test_create_duplicate_edit_and_consent(self):
  self.post('/students',self.student());old=self.row();self.assertEqual(old['id'],'001')
  d=self.student();d['name']='Overwrite';self.post('/students',d);self.assertEqual(self.row()['name'],'Student A')
  d.update(operation='edit',record_token=a.record_token(old));d.pop('consent');self.post('/students',d);self.assertEqual(self.row()['consent'],0)
  self.assertEqual(self.row()['name'],'Overwrite')
  d['name']='Stale';self.post('/students',d);self.assertEqual(self.row()['name'],'Overwrite')
 def test_invalid_class_and_missing_phone(self):
  d=self.student();d['class_name']='Undefined';self.post('/students',d);self.assertIsNone(self.row())
  d=self.student();d['phone']='';self.post('/students',d);self.assertIsNone(self.row())
 def test_class_rename_and_remove(self):
  self.post('/students',self.student());self.post('/classes',dict(action='rename',old_name='P5',name='Primary Five'));self.assertEqual(self.row()['class_name'],'Primary Five')
  self.post('/classes',dict(action='remove',old_name='Primary Five'))
  with a.db() as c:self.assertIsNotNone(c.execute("SELECT 1 FROM classes WHERE name='Primary Five'").fetchone())
  self.post('/classes',dict(action='remove',old_name='Baby'));a.init()
  with a.db() as c:self.assertIsNone(c.execute("SELECT 1 FROM classes WHERE name='Baby'").fetchone())
 def test_import_atomic_and_explicit_updates(self):
  self.post('/students',self.student())
  text=b'id,name,class_name,phone,consent\n002,New,P5,,0\n001,Changed,P5,,0\n'
  self.post('/import',dict(file=(io.BytesIO(text),'test.csv')))
  with a.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM students').fetchone()[0],1)
  self.post('/import',dict(file=(io.BytesIO(text),'test.csv'),update_existing='on'));self.assertEqual(self.row()['name'],'Changed')
 def test_search_and_edit_form(self):
  self.post('/students',self.student());r=self.c.get('/students?edit=001');self.assertEqual(r.status_code,200);self.assertIn(b'Save changes',r.data)
  r=self.c.get('/students?student_q=nomatch');self.assertIn(b'No matching students',r.data)
 def test_edit_cancels_pending(self):
  self.post('/students',self.student());a.ingest('001',a.now(),0)
  old=self.row();d=self.student();d.update(operation='edit',record_token=a.record_token(old),phone='+256711111111');self.post('/students',d)
  with a.db() as c:self.assertEqual(c.execute('SELECT status FROM messages').fetchone()[0],'CANCELLED')
