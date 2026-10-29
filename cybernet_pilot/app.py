"""Independently authored Cybernet pilot; original upstream scripts remain untouched."""
import csv, hashlib, io, os, sqlite3, threading, time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
app = Flask(__name__)
app.secret_key = os.getenv('APP_SECRET') or os.urandom(32)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
DB = Path(os.getenv('DATABASE_PATH', str(ROOT / 'pilot.sqlite3')))
TZ = ZoneInfo('Africa/Kampala')
MODE = os.getenv('APP_MODE', 'demo')
DIRECTION = os.getenv('DEVICE_DIRECTION', 'PUNCH').upper()
state = {'device': 'Not tested', 'worker': 'Stopped'}
worker_lock = threading.Lock()
sms_lock = threading.Lock()
auto_sms = False
sms_thread = None

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
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS classes(name TEXT PRIMARY KEY COLLATE NOCASE);
        CREATE TABLE IF NOT EXISTS student_changes(id INTEGER PRIMARY KEY,student_id TEXT,changed_at TEXT,action TEXT);''')
        if not c.execute("SELECT 1 FROM meta WHERE key='class_catalog_seeded'").fetchone():
            c.executemany('INSERT OR IGNORE INTO classes(name) VALUES(?)',[(x,) for x in ['Baby','Middle','Top','P1','P2','P3','P4','P5','P6','P7']])
            c.execute("INSERT INTO meta VALUES('class_catalog_seeded','1')")
        c.execute("INSERT OR IGNORE INTO classes(name) SELECT DISTINCT TRIM(class_name) FROM students WHERE class_name IS NOT NULL AND TRIM(class_name)!=''")
def recover_dispatch():
    with db() as c:
        c.execute("UPDATE messages SET status='UNKNOWN',detail='Application stopped during submission; check provider before resending.' WHERE status='SUBMITTING'")
        c.execute("UPDATE messages SET status='CANCELLED',detail='Automatic sending resets to OFF after restart.' WHERE status='QUEUED'")

def ingest(student_id, stamp, punch, source='K40', historical=False):
    student_id = str(student_id)
    direction = DIRECTION if source == 'K40' and DIRECTION in ('IN','OUT') else {0:'IN',1:'OUT'}.get(punch,'UNKNOWN')
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
            status = 'SIMULATED' if source == 'DEMO' else ('QUEUED' if auto_sms and MODE == 'device' else 'DRY_RUN')
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
    q=request.args.get('student_q','').strip()
    class_filter=request.args.get('student_class','').strip()
    consent_filter=request.args.get('student_consent','')
    with db() as c:
        all_students=c.execute('SELECT * FROM students ORDER BY name COLLATE NOCASE').fetchall()
        students=[r for r in all_students if (not q or q.casefold() in ' '.join(str(r[k] or '') for k in ['id','name','phone']).casefold()) and (not class_filter or r['class_name']==class_filter) and (consent_filter not in ('0','1') or r['consent']==int(consent_filter))]
        edit_student=c.execute('SELECT * FROM students WHERE id=?',(request.args.get('edit',''),)).fetchone()
        token=record_token(edit_student) if edit_student else ''
        return render_template('index.html',mode=MODE,state=state,students=students,all_students=all_students,classes=c.execute('SELECT name FROM classes ORDER BY name COLLATE NOCASE').fetchall(),edit_student=edit_student,record_token=token,student_q=q,student_class=class_filter,student_consent=consent_filter,events=c.execute('SELECT * FROM events ORDER BY stamp DESC LIMIT 100').fetchall(),messages=c.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 100').fetchall(),auto_sms=auto_sms,counts=dict(c.execute('SELECT status,COUNT(*) FROM messages GROUP BY status').fetchall()),csrf=session['csrf'])

def record_token(row):
    return hashlib.sha256(repr(tuple(row)).encode()).hexdigest()

def validated_student(form,c):
    sid=form.get('id','').strip();name=form.get('name','').strip();phone=form.get('phone','').strip();cls=form.get('class_name','').strip()
    consent=1 if form.get('consent') in ('on','1') else 0
    if not sid or len(sid)>32 or not name or len(name)>100:raise ValueError('Enter a device ID (up to 32 characters) and student name (up to 100).')
    if phone.startswith('256') and len(phone)==12:phone='+'+phone
    if phone and (not phone.startswith('+256') or len(phone)!=13 or not phone[1:].isdigit()):raise ValueError('Use a Uganda guardian number such as +2567XXXXXXXX.')
    if consent and not phone:raise ValueError('Enter a guardian phone number before enabling SMS consent.')
    found=c.execute('SELECT name FROM classes WHERE name=? COLLATE NOCASE',(cls,)).fetchone()
    if not found:raise ValueError('Choose a defined class. Add it under Manage classes if needed.')
    return sid,name,found['name'],phone,consent

def save_student(c,values,updating=False):
    sid=values[0]
    old=c.execute('SELECT * FROM students WHERE id=?',(sid,)).fetchone()
    if old and not updating:raise ValueError('This device ID already exists. Use its Edit button.')
    if updating and not old:raise ValueError('Student no longer exists. Refresh the page.')
    if old:
        c.execute('UPDATE students SET name=?,class_name=?,phone=?,consent=? WHERE id=?',(*values[1:],sid))
        if old['phone']!=values[3] or old['name']!=values[1] or not values[4]:
            c.execute("UPDATE messages SET status='CANCELLED',detail='Student information/consent changed; create a new scan.' WHERE status IN ('QUEUED','DRY_RUN') AND event_id IN (SELECT id FROM events WHERE student_id=?)",(sid,))
    else:c.execute('INSERT INTO students VALUES(?,?,?,?,?)',values)
    c.execute('INSERT INTO student_changes(student_id,changed_at,action) VALUES(?,?,?)',(sid,now().isoformat(),'updated' if old else 'created'))

@app.post('/students')
def student():
    try:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            values=validated_student(request.form,c)
            updating=request.form.get('operation')=='edit'
            if updating:
                old=c.execute('SELECT * FROM students WHERE id=?',(values[0],)).fetchone()
                if not old or request.form.get('record_token')!=record_token(old):raise ValueError('Student changed since this form was opened. Refresh and edit again.')
            save_student(c,values,updating)
        flash('Student updated.' if updating else 'Student added. Enrol the identical user ID on the K40.')
    except ValueError as e:flash(str(e))
    return redirect(url_for('index')+'#student-register')

@app.post('/classes')
def manage_classes():
    try:
        name=request.form.get('name','').strip();old=request.form.get('old_name','').strip()
        action=request.form.get('action','add')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if action=='remove':
                if c.execute('SELECT 1 FROM students WHERE class_name=?',(old,)).fetchone():raise ValueError('Class is in use. Reassign its students before removing it.')
                c.execute('DELETE FROM classes WHERE name=?',(old,))
            else:
                if not name or len(name)>40:raise ValueError('Enter a class name of 1–40 characters.')
                if action=='rename':
                    if not c.execute('SELECT 1 FROM classes WHERE name=?',(old,)).fetchone():raise ValueError('Class not found.')
                    c.execute('UPDATE classes SET name=? WHERE name=?',(name,old))
                    c.execute('UPDATE students SET class_name=? WHERE class_name=?',(name,old))
                else:c.execute('INSERT INTO classes VALUES(?)',(name,))
        flash('Class list updated.')
    except sqlite3.IntegrityError:flash('That class name already exists.')
    except ValueError as e:flash(str(e))
    return redirect(url_for('index')+'#student-register')

@app.post('/import')
def import_students():
    try:
        rows=list(csv.DictReader(io.StringIO(request.files['file'].read().decode('utf-8-sig'))))
        if not rows:raise ValueError('CSV has no student rows.')
        with db() as c:
            c.execute('BEGIN IMMEDIATE');seen=set()
            for number,r in enumerate(rows,2):
                if not {'id','name','class_name','phone','consent'}<=r.keys():raise ValueError('Required CSV columns: id,name,class_name,phone,consent.')
                if r['consent'] not in ('0','1'):raise ValueError(f'Row {number}: consent must be 0 or 1.')
                v=validated_student(r,c)
                if v[0] in seen:raise ValueError(f'Row {number}: duplicate device ID in CSV.')
                seen.add(v[0]);exists=c.execute('SELECT 1 FROM students WHERE id=?',(v[0],)).fetchone()
                if exists and request.form.get('update_existing')!='on':raise ValueError(f'Row {number}: ID already exists. Tick update existing records if intended.')
                save_student(c,v,bool(exists))
        flash(f'Imported {len(rows)} students successfully.')
    except (ValueError,KeyError,UnicodeDecodeError) as e:flash('Import cancelled; no rows changed. '+str(e))
    return redirect(url_for('index')+'#student-register')

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
        try: flash(f'K40 connection succeeded. Firmware: {conn.get_firmware_version()}')
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

def dispatch_once():
    from sms_provider import prepare, submit
    # Serialize toggling and claiming. An already submitted request cannot be recalled.
    with sms_lock:
        if not auto_sms or MODE != 'device': return False
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute("SELECT m.*,e.student_id,e.stamp,e.source FROM messages m JOIN events e ON e.id=m.event_id WHERE m.status='QUEUED' ORDER BY m.id LIMIT 1").fetchone()
            if not r: return False
            student=c.execute('SELECT * FROM students WHERE id=?',(r['student_id'],)).fetchone()
            reason=None
            if r['source']!='K40': reason='Not a real K40 scan'
            elif not student or not student['consent'] or student['phone']!=r['phone']: reason='Consent/contact changed; review student record'
            elif (now()-datetime.fromisoformat(r['stamp'])).total_seconds()>300: reason='Queue expired after five minutes; no current alert sent'
            if reason:
                c.execute("UPDATE messages SET status='CANCELLED',detail=? WHERE id=?",(reason,r['id']));return True
            try: prepared=prepare(r['phone'],r['body'])
            except ValueError as e:
                c.execute("UPDATE messages SET status='BLOCKED',detail=? WHERE id=?",(str(e),r['id']));return True
            c.execute("UPDATE messages SET status='SUBMITTING',detail='Submitting to SMS gateway' WHERE id=? AND status='QUEUED'",(r['id'],))
    status,detail=submit(prepared)
    with db() as c:c.execute('UPDATE messages SET status=?,detail=? WHERE id=?',(status,detail,r['id']))
    return True

def sms_worker():
    while True:
        try:
            if not dispatch_once(): time.sleep(1)
        except Exception:
            state['sms_error']='SMS worker error; inspect statuses and restart before continuing.'
            time.sleep(2)

@app.post('/sms-control')
def sms_control():
    global auto_sms,sms_thread
    if MODE!='device': flash('Automatic sending is available only in device mode.');return redirect('/')
    enable=request.form.get('action')=='enable'
    with sms_lock:
        if enable:
            if request.form.get('ack')!='on': flash('Tick the live SMS acknowledgement first.');return redirect('/')
            auto_sms=True
            if sms_thread is None or not sms_thread.is_alive():
                sms_thread=threading.Thread(target=sms_worker,daemon=True);sms_thread.start()
        else:
            auto_sms=False
            with db() as c:c.execute("UPDATE messages SET status='CANCELLED',detail='Cancelled when automatic sending was paused.' WHERE status='QUEUED'")
    flash('Automatic SMS ON for new eligible scans. Start polling if stopped.' if enable else 'Automatic SMS OFF. Pending queue cancelled; a submission already in progress may complete.')
    return redirect('/')

@app.get('/export')
def export():
    out=io.StringIO(); w=csv.writer(out); w.writerow(['student_id','name','direction','stamp','source','reason'])
    with db() as c:
        for r in c.execute('SELECT student_id,name,direction,stamp,source,reason FROM events ORDER BY stamp'):
            w.writerow([("'"+str(v)) if str(v).startswith(('=','+','-','@')) else v for v in r])
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=attendance.csv'})

init()
if __name__=='__main__':
    recover_dispatch()
    app.run(host='127.0.0.1',port=5000,debug=False)
