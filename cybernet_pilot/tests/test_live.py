import os,sys,tempfile,unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as a

class LiveModeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old_db=a.DB;self.old_mode=a.MODE
  self.old_state=a.state.copy();self.old_thread=a.worker_thread;self.old_sms_thread=a.sms_thread
  self.env=patch.dict(os.environ,{'SCHOOL_NAME':'Test School','DEVICE_IP':'192.168.1.42','DEVICE_PORT':'4370','DEVICE_COMM_KEY':'0','DEVICE_FORCE_UDP':'false','DEVICE_DIRECTION':'PUNCH','POLL_SECONDS':'10','SMS_PROVIDER':'pandora','PANDORA_USERNAME':'','PANDORA_PASSWORD':'','PANDORA_SENDER':''});self.env.start()
  a.DB=Path(self.tmp.name)/'live.db';a.MODE='device';a.auto_sms=False;a.worker_thread=None;a.sms_thread=None
  a.state.update(device='Not tested',worker='Stopped',last_poll=None,last_error=None);a.retry_event.clear();a.init()
  self.client=a.app.test_client();self.client.get('/')
  with self.client.session_transaction() as session:self.csrf=session['csrf']
 def tearDown(self):
  a.DB=self.old_db;a.MODE=self.old_mode;a.auto_sms=False;a.worker_thread=self.old_thread;a.sms_thread=self.old_sms_thread
  a.state.clear();a.state.update(self.old_state);a.retry_event.clear();self.env.stop();self.tmp.cleanup()
 def test_missing_configuration_prevents_collector(self):
  with patch.dict(os.environ,{'DEVICE_IP':''}),patch.object(a.threading,'Thread') as thread:
   self.assertFalse(a.start_collector());thread.assert_not_called()
   self.assertIn('DEVICE_IP',a.state['device'])
   self.assertIn('Configuration required',self.client.get('/terminals').data.decode())
  template=(Path(__file__).resolve().parents[1]/'.env.example').read_text()
  self.assertIn('APP_MODE=device',template)
  self.assertIn('\nDEVICE_IP=\n',template)
  for name in ('SCHOOL_NAME','DEVICE_PORT','DEVICE_COMM_KEY','DEVICE_FORCE_UDP','DEVICE_DIRECTION','POLL_SECONDS','PANDORA_USERNAME','PANDORA_PASSWORD','PANDORA_SENDER','PANDORA_MESSAGE_TYPE','PANDORA_SENDER_FIELD','PANDORA_API_URL'):
   self.assertIn(f'\n{name}=',template)
 def test_poll_buttons_config_and_csrf(self):
  for page in ('/terminals','/settings'):
   html=self.client.get(page).data.decode()
   self.assertIn('action="/start"',html)
   self.assertIn('>Poll now</button>',html)
  self.assertEqual(self.client.post('/start',data={'return_to':'settings'}).status_code,403)
  with patch.dict(os.environ,{'DEVICE_IP':''}),patch.object(a.threading,'Thread') as thread:
   for page in ('/terminals','/settings'):
    html=self.client.get(page).data.decode()
    self.assertIn('disabled>Poll now</button>',html)
    self.assertIn('DEVICE_IP',html)
   response=self.client.post('/start',data={'csrf':self.csrf,'return_to':'settings'},follow_redirects=True)
   self.assertEqual(response.request.path,'/settings')
   self.assertIn('DEVICE_IP',response.data.decode())
   thread.assert_not_called()
 def test_one_worker_and_manual_poll_during_read(self):
  with patch.object(a.threading,'Thread') as thread,patch.object(a,'connect') as connect:
   thread.return_value.is_alive.return_value=True
   self.assertTrue(a.start_collector());self.assertTrue(a.start_collector())
   a.poll_lock.acquire()
   try:
    response=self.client.post('/start',data={'csrf':self.csrf,'return_to':'settings'},follow_redirects=True)
   finally:
    a.poll_lock.release()
   self.assertEqual(response.request.path,'/settings')
   self.assertIn('Poll requested',response.data.decode())
   thread.assert_called_once();thread.return_value.start.assert_called_once()
   connect.assert_not_called()
   self.assertTrue(a.retry_event.is_set())
 def test_manual_poll_imports_new_in_and_out(self):
  with a.db() as c:c.execute("INSERT INTO students VALUES('7','Test Student','P5','+256700000000',1)")
  stamp=a.now()-timedelta(seconds=3)
  logs=[SimpleNamespace(user_id='99',timestamp=stamp,punch=0)]
  connection=SimpleNamespace(get_attendance=lambda:logs,disconnect=lambda:None)
  with patch.object(a,'connect',return_value=connection),patch.object(a,'worker',side_effect=a.poll_cycle):
   for direction,offset in ((None,0),(0,1),(1,2)):
    if direction is not None:logs.append(SimpleNamespace(user_id='7',timestamp=stamp+timedelta(seconds=offset),punch=direction))
    response=self.client.post('/start',data={'csrf':self.csrf,'return_to':'settings'},follow_redirects=True)
    self.assertEqual(response.request.path,'/settings')
    a.worker_thread.join(timeout=2)
    self.assertFalse(a.worker_thread.is_alive())
   with a.db() as c:
    self.assertEqual([r[0] for r in c.execute('SELECT direction FROM events ORDER BY stamp,id')],['IN','IN','OUT'])
    self.assertEqual([r[0] for r in c.execute('SELECT status FROM messages ORDER BY id')],['DRY_RUN','DRY_RUN'])
 def test_failure_then_baseline_and_new_in_out(self):
  with a.db() as c:c.execute("INSERT INTO students VALUES('7','Test Student','P5','+256700000000',1)")
  stamp=a.now();logs=[SimpleNamespace(user_id='7',timestamp=stamp,punch=0)]
  connection=SimpleNamespace(get_attendance=lambda:logs,disconnect=lambda:None)
  with patch.object(a,'connect',side_effect=[OSError('offline'),connection,connection]):
   a.poll_cycle();self.assertIn('Connection failed',a.state['device'])
   a.poll_cycle();self.assertIsNone(a.state['last_error'])
   with a.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)
   logs.append(SimpleNamespace(user_id='7',timestamp=stamp+timedelta(seconds=1),punch=1));a.poll_cycle()
  with a.db() as c:
   self.assertEqual([r[0] for r in c.execute('SELECT direction FROM events ORDER BY stamp,id')],['IN','OUT'])
   self.assertEqual(c.execute('SELECT COUNT(*) FROM messages').fetchone()[0],1)
  dashboard=self.client.get('/').data.decode()
  self.assertIn('Recorded scans today',dashboard)
  self.assertIn('<strong>1</strong><span>OUT</span>',dashboard)
 def test_sms_enable_requires_baseline_and_pandora_settings(self):
  def enable():return self.client.post('/sms-control',data={'csrf':self.csrf,'action':'enable','ack':'on'},follow_redirects=True).data.decode()
  self.assertIn('successful K40 poll',enable());self.assertFalse(a.auto_sms)
  with a.db() as c:c.execute("INSERT OR REPLACE INTO meta VALUES('baseline',?)",(a.now().isoformat(),))
  a.state['last_poll']=a.now().isoformat()
  self.assertIn('PANDORA_USERNAME',enable());self.assertFalse(a.auto_sms)
  with patch.dict(os.environ,{'PANDORA_USERNAME':'test','PANDORA_PASSWORD':'test','PANDORA_SENDER':'Cybernet'}),patch.object(a.threading,'Thread') as thread:
   thread.return_value.is_alive.return_value=True
   self.assertIn('Automatic SMS ON',enable());self.assertTrue(a.auto_sms)
   thread.return_value.start.assert_called_once()
  self.client.post('/sms-control',data={'csrf':self.csrf,'action':'pause'})
  self.assertFalse(a.auto_sms)

if __name__=='__main__':unittest.main()
