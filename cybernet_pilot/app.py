"""Independently authored Cybernet pilot; original upstream scripts remain untouched."""
import csv, hashlib, io, os, sqlite3, threading, time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from dotenv import load_dotenv
load_dotenv()
ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.secret_key = os.getenv('APP_SECRET') or os.urandom(32)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
DB = Path(os.getenv('DATABASE_PATH', str(ROOT / 'pilot.sqlite3')))
TZ = ZoneInfo('Africa/Kampala')
MODE = os.getenv('APP_MODE', 'demo')
DIRECTION = os.getenv('DEVICE_DIRECTION', 'PUNCH').upper()
state = {'device': 'Not tested', 'worker': 'Stopped'}
worker_lock = threading.Lock()

def now(): return datetime.now(TZ).replace(tzinfo=None)
def db():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    return c

def init():
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS students(id TEXT PRIMARY KEY,name TEXT NOT NULL,class_name TEXT,phone TEXT,consent INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,student_id TEXT,name TEXT,direction TEXT,stamp TEXT,source TEXT,reason TEXT);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,event_id TEXT UNIQUE,phone TEXT,body TEXT,status TEXT,detail TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);''')

def ingest(student_id, stamp, punch, source='F18', historical=False):
    student_id = str(student_id)
    direction = DIRECTION if source == 'F18' and DIRECTION in ('IN','OUT') else {0:'IN',1:'OUT'}.get(punch,'UNKNOWN')
    key = hashlib.sha256(f'{source}|{student_id}|{stamp.isoformat()}|{punch}'.encode()).hexdigest()
    with db() as c:
        if c.execute('SELECT 1 FROM events WHERE id=?',(key,)).fetchone(): return False
        s = c.execute('SELECT * FROM students WHERE id=?',(student_id,)).fetchone()
        name = s['name'] if s else f'Unmapped ID {student_id}'
        age = (now()-stamp).total_seconds()
        reason = 'Eligible'
        if historical: reason = 'Baseline: historical record, no alert'
        elif direction == 'UNKNOWN': reason = 'Unknown punch code: inspect terminal settings'
        elif age < -120: reason = 'Future timestamp: check device clock'
        elif age > 300: reason = 'Delayed record: review, no live alert'
        elif not s: reason = 'Student not mapped'
        elif not s['consent'] or not s['phone']: reason = 'Missing guardian consent or phone'
        previous = c.execute('SELECT stamp FROM events WHERE student_id=? AND direction=? AND source=? ORDER BY stamp DESC LIMIT 1',(student_id,direction,source)).fetchone()
        if reason == 'Eligible' and previous and abs((stamp-datetime.fromisoformat(previous['stamp'])).total_seconds()) < 60:
            reason = 'Repeat scan suppressed (60 seconds)'
        c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)',(key,student_id,name,direction,stamp.isoformat(),source,reason))
        if reason == 'Eligible':
            body = f"{os.getenv('SCHOOL_NAME','Cybernet Demo School')}: {name} recorded {direction} at {stamp:%H:%M} on {stamp:%d %b %Y}."
            status = 'SIMULATED' if source == 'DEMO' else 'DRY_RUN'
            c.execute('INSERT INTO messages(event_id,phone,body,status) VALUES(?,?,?,?)',(key,s['phone'],body,status))
    return True

def connect():
    from zk import ZK
    return ZK(os.getenv('DEVICE_IP','192.168.1.201'), port=int(os.getenv('DEVICE_PORT','4370')), timeout=8,
              password=int(os.getenv('DEVICE_COMM_KEY','0')), force_udp=os.getenv('DEVICE_FORCE_UDP','false').lower()=='true', ommit_ping=True).connect()

def poll_once():
    connection = None
    try:
        connection = connect()
        logs = connection.get_attendance()  # Never disable or clear the terminal.
        with db() as c:
            baseline = c.execute("SELECT value FROM meta WHERE key='baseline'").fetchone()
        for log in sorted(logs or [], key=lambda l:l.timestamp):
            ingest(log.user_id,log.timestamp,log.punch,historical=not baseline)
        if not baseline:
            with db() as c: c.execute("INSERT OR REPLACE INTO meta VALUES('baseline',?)",(now().isoformat(),))
        state['device'] = f'Connected: {len(logs or [])} records read at {now():%H:%M:%S}'
    finally:
        if connection: connection.disconnect()

def worker():
    state['worker'] = 'Running'
    while True:
        try: poll_once()
        except Exception as e: state['device'] = f'Connection failed: {type(e).__name__}: {e}'
        time.sleep(max(5,int(os.getenv('POLL_SECONDS','10'))))

@app.before_request
def protect():
    # Local-only bind by default. Optional password is required for any shared use.
    password = os.getenv('DASHBOARD_PASSWORD')
    if password:
        import hmac
        if not request.authorization or not hmac.compare_digest(request.authorization.password or '',password):
            return Response('Password required',401,{'WWW-Authenticate':'Basic realm="Cybernet Pilot"'})
    if request.method == 'POST':
        import hmac
        if not hmac.compare_digest(request.form.get('csrf',''),str(__import__('flask').session.get('csrf','missing'))):
            return 'Invalid form token',403

@app.route('/')
def index():
    from flask import session
    session.setdefault('csrf',os.urandom(24).hex())
    with db() as c:
        return render_template('index.html',mode=MODE,state=state,students=c.execute('SELECT * FROM students ORDER BY name').fetchall(),events=c.execute('SELECT * FROM events ORDER BY stamp DESC LIMIT 100').fetchall(),messages=c.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 100').fetchall(),csrf=session['csrf'])

@app.post('/students')
def student():
    sid=request.form['id'].strip(); name=request.form['name'].strip(); phone=request.form['phone'].strip()
    if not sid or not name or (phone and (not phone.startswith('+') or not phone[1:].isdigit())):
        flash('Provide an ID, name and international phone such as +256...'); return redirect('/')
    with db() as c: c.execute('INSERT OR REPLACE INTO students VALUES(?,?,?,?,?)',(sid,name,request.form.get('class_name',''),phone,int(request.form.get('consent')=='on')))
    flash('Student saved. Device ID must match exactly, including leading zeros.')
    return redirect('/')

@app.post('/import')
def import_students():
    try:
        rows=list(csv.DictReader(io.StringIO(request.files['file'].read().decode('utf-8-sig'))))
        clean=[]
        for r in rows:
            sid=r['id'].strip(); name=r['name'].strip(); phone=r['phone'].strip()
            if not sid or not name or (phone and (not phone.startswith('+') or not phone[1:].isdigit())): raise ValueError('Invalid row')
            clean.append((sid,name,r.get('class_name',''),phone,int(r.get('consent','0')=='1')))
        with db() as c: c.executemany('INSERT OR REPLACE INTO students VALUES(?,?,?,?,?)',clean)
        flash(f'Imported {len(clean)} students')
    except Exception: flash('Import rejected. Required columns: id,name,class_name,phone,consent; use consent 1 or 0.')
    return redirect('/')

@app.post('/demo')
def demo():
    if MODE != 'demo': return 'Demo disabled',403
    ingest(request.form['id'],now(),0 if request.form['direction']=='IN' else 1,'DEMO')
    return redirect('/')

@app.post('/test')
def test():
    if MODE != 'device': flash('Set APP_MODE=device in .env and restart first.'); return redirect('/')
    try:
        conn=connect()
        try: flash(f'F18 connection succeeded. Firmware: {conn.get_firmware_version()}')
        finally: conn.disconnect()
    except Exception as e: flash(f'Connection failed: {type(e).__name__}: {e}')
    return redirect('/')

@app.post('/start')
def start():
    if MODE != 'device': flash('Set APP_MODE=device and restart first.'); return redirect('/')
    with worker_lock:
        if state['worker'] != 'Running':
            state['worker']='Running'
            threading.Thread(target=worker,daemon=True).start()
    return redirect('/')

@app.get('/export')
def export():
    out=io.StringIO(); w=csv.writer(out); w.writerow(['student_id','name','direction','stamp','source','reason'])
    with db() as c:
        for r in c.execute('SELECT student_id,name,direction,stamp,source,reason FROM events ORDER BY stamp'):
            w.writerow([("'"+str(v)) if str(v).startswith(('=','+','-','@')) else v for v in r])
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=attendance.csv'})

init()
if __name__=='__main__': app.run(host='127.0.0.1',port=5000,debug=False)
