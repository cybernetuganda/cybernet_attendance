import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as a

class AuthTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old_db=a.DB;a.DB=Path(self.tmp.name)/'auth.db';a.init()
  self.client=a.app.test_client()
 def tearDown(self):
  a.DB=self.old_db;self.tmp.cleanup()
 def token(self):
  self.client.get('/login')
  with self.client.session_transaction() as session:return session['csrf']
 def make_admin(self):
  with patch.object(a.getpass,'getpass',side_effect=['a-long-private-password','a-long-private-password']):a.manage_account('create-admin','admin')
 def sign_in(self,remember=False,next_path='/'):
  return self.client.post('/login',data={'csrf':self.token(),'username':'admin','password':'a-long-private-password','remember':'on' if remember else '', 'next':next_path})
 def test_private_pages_and_export_require_login(self):
  for path in ('/','/attendance','/students','/guardians','/terminals','/settings','/export'):
   response=self.client.get(path)
   self.assertEqual(response.status_code,302,path)
   self.assertTrue(response.location.startswith('/login?next='),path)
  self.assertEqual(self.client.post('/students',data={}).status_code,401)
  self.assertEqual(self.client.get('/login').status_code,200)
  self.assertEqual(self.client.get('/login').headers['Cache-Control'],'no-store')
  response=self.client.get('/static/login.css');self.assertEqual(response.status_code,200);response.close()
 def test_login_csrf_session_remember_and_logout(self):
  self.make_admin()
  self.assertEqual(self.client.post('/login',data={'username':'admin','password':'a-long-private-password'}).status_code,403)
  response=self.sign_in(remember=True,next_path='/students?student_q=one')
  self.assertEqual(response.location,'/students?student_q=one')
  with self.client.session_transaction() as session:
   self.assertTrue(session.permanent)
   token=session['csrf']
  self.assertEqual(self.client.get('/settings').status_code,200)
  self.assertEqual(self.client.post('/logout',data={}).status_code,403)
  self.assertEqual(self.client.post('/logout',data={'csrf':token}).location,'/login')
  self.assertEqual(self.client.get('/settings').status_code,302)
 def test_failed_login_lockout_and_open_redirect(self):
  self.make_admin();token=self.token()
  for _ in range(5):
   response=self.client.post('/login',data={'csrf':token,'username':'admin','password':'wrong'})
   self.assertIn(b'Invalid username or password',response.data)
  response=self.client.post('/login',data={'csrf':token,'username':'admin','password':'a-long-private-password'})
  self.assertIn(b'Too many attempts',response.data)
  with a.db() as connection:connection.execute('DELETE FROM login_attempts')
  self.assertEqual(self.sign_in(next_path='//evil.example').location,'/')
 def test_password_reset_invalidates_existing_sessions(self):
  self.make_admin();self.sign_in()
  with patch.object(a.getpass,'getpass',side_effect=['new-private-password','new-private-password']):a.manage_account('reset-password','admin')
  self.assertEqual(self.client.get('/').status_code,302)
  response=self.client.post('/login',data={'csrf':self.token(),'username':'admin','password':'new-private-password'})
  self.assertEqual(response.location,'/')
 def test_admin_setup_rejects_weak_or_duplicate_account(self):
  with patch.object(a.getpass,'getpass',side_effect=['short','short']):
   with self.assertRaises(ValueError):a.manage_account('create-admin','admin')
  self.make_admin()
  with patch.object(a.getpass,'getpass',side_effect=['a-long-private-password','a-long-private-password']):
   with self.assertRaises(ValueError):a.manage_account('create-admin','ADMIN')
