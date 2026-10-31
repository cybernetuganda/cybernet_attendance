"""Independently authored Cybernet pilot; original upstream scripts remain untouched."""
import csv, hashlib, io, os, sqlite3, threading, time
from ipaddress import IPv4Address
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from werkzeug.datastructures import MultiDict
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
app = Flask(__name__)
app.secret_key = os.getenv('APP_SECRET') or os.urandom(32)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
DB = Path(os.getenv('DATABASE_PATH', str(ROOT / 'pilot.sqlite3')))
TZ = ZoneInfo('Africa/Kampala')
MODE = os.getenv('APP_MODE', 'device').strip().lower()
DIRECTION = os.getenv('DEVICE_DIRECTION', 'PUNCH').upper()
state = {'device': 'Not tested', 'worker': 'Stopped', 'last_poll': None, 'last_error': None}
worker_lock = threading.Lock()
poll_lock = threading.Lock()
retry_event = threading.Event()
worker_thread = None
sms_lock = threading.Lock()
auto_sms = False
sms_thread = None

def now(): return datetime.now(TZ).replace(tzinfo=None)

def school_name():
    configured = os.getenv('SCHOOL_NAME','').strip()
    return configured or ('Cybernet Demo School' if MODE == 'demo' else 'Institution not configured')

def device_settings():
    address=os.getenv('DEVICE_IP','').strip()
    try: IPv4Address(address)
    except ValueError: raise ValueError('Set DEVICE_IP to the real K40 IPv4 address in the local .env and restart.')
    try:
        port=int(os.getenv('DEVICE_PORT','4370'))
        key=int(os.getenv('DEVICE_COMM_KEY','0'))
        interval=int(os.getenv('POLL_SECONDS','10'))
    except ValueError: raise ValueError('DEVICE_PORT, DEVICE_COMM_KEY and POLL_SECONDS must be whole numbers.')
    if not 1<=port<=65535: raise ValueError('DEVICE_PORT must be between 1 and 65535.')
    if key<0: raise ValueError('DEVICE_COMM_KEY must not be negative.')
    if not 5<=interval<=300: raise ValueError('POLL_SECONDS must be between 5 and 300.')
    direction=os.getenv('DEVICE_DIRECTION','PUNCH').strip().upper()
    if direction not in ('PUNCH','IN','OUT'): raise ValueError('DEVICE_DIRECTION must be PUNCH, IN or OUT.')
    udp=os.getenv('DEVICE_FORCE_UDP','false').strip().lower()
    if udp not in ('true','false'): raise ValueError('DEVICE_FORCE_UDP must be true or false.')
    return dict(address=address,port=port,key=key,interval=interval,udp=udp=='true')

def device_config_error():
    if MODE not in ('device','demo'): return 'APP_MODE must be device or demo in the local .env.'
    if MODE!='device': return ''
    if not os.getenv('SCHOOL_NAME','').strip() or os.getenv('SCHOOL_NAME','').strip()=='Cybernet Demo School':
        return 'Set SCHOOL_NAME to the real institution name in the local .env and restart.'
    try: device_settings()
    except ValueError as error: return str(error)
    return ''

def sms_config_error():
    from sms_provider import prepare
    try:
        prepare('+256700000000',f'{school_name()}: Test Student recorded IN at 08:00 on 31 Oct 2026.')
    except ValueError as error: return str(error)
    return ''

@contextmanager
def db():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        with c:
            yield c
    finally:
        c.close()

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
            body = f"{school_name()}: {name} recorded {direction} at {stamp:%H:%M} on {stamp:%d %b %Y}."
            status = 'SIMULATED' if source == 'DEMO' else ('QUEUED' if auto_sms and MODE == 'device' else 'DRY_RUN')
            c.execute('INSERT INTO messages(event_id,phone,body,status) VALUES(?,?,?,?)',(key,s['phone'],body,status))
    return True

def connect():
    from zk import ZK
    settings=device_settings()
    return ZK(settings['address'], port=settings['port'], timeout=8,
              password=settings['key'], force_udp=settings['udp'], ommit_ping=True).connect()

def poll_once():
    with poll_lock:
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
            state['last_poll'] = now().isoformat()
            state['last_error'] = None
        finally:
            if connection: connection.disconnect()

def poll_cycle():
    try: poll_once()
    except Exception as error:
        state['last_error']=f'{type(error).__name__}: {error}'
        state['device']=f'Connection failed: {state["last_error"]}'

def worker():
    state['worker'] = 'Running'
    try:
        interval=device_settings()['interval']
        while True:
            retry_event.clear()
            poll_cycle()
            retry_event.wait(timeout=interval)
    finally:
        state['worker']='Stopped'

def start_collector():
    global worker_thread
    if MODE!='device': return False
    error=device_config_error()
    if error:
        state['worker']='Configuration required'
        state['device']='Configuration required: '+error
        return False
    with worker_lock:
        if worker_thread is not None and worker_thread.is_alive():
            retry_event.set()
            return True
        retry_event.clear()
        state['worker']='Starting'
        state['device']='Connecting to K40...'
        worker_thread=threading.Thread(target=worker,daemon=True,name='k40-poller')
        worker_thread.start()
    return True

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

def attendance_query(args):
    clauses=[];params=[]
    for key,column in [('att_student','e.name'),('att_id','e.student_id'),('att_reason','e.reason')]:
        value=args.get(key,'').strip()[:100]
        if value:clauses.append(f"instr(lower({column}),lower(?))>0");params.append(value)
    q=args.get('att_q','').strip()[:100]
    if q:
        clauses.append("(instr(lower(e.name),lower(?))>0 OR instr(e.student_id,?)>0 OR instr(lower(e.reason),lower(?))>0)");params.extend([q,q,q])
    for key,col in [('att_direction','e.direction'),('att_source','e.source'),('att_class','s.class_name'),('att_status',"COALESCE(m.status,'NO_MESSAGE')")]:
        value=args.get(key,'').strip()[:100]
        if value:clauses.append(col+'=?');params.append(value)
    for key,operator in [('att_from','>='),('att_to','<=')]:
        value=args.get(key,'')
        if value:
            try:datetime.strptime(value,'%Y-%m-%d')
            except ValueError:raise ValueError('Use valid attendance dates in YYYY-MM-DD format.')
            clauses.append(f'substr(e.stamp,1,10){operator}?');params.append(value)
    if args.get('att_from') and args.get('att_to') and args['att_from']>args['att_to']:raise ValueError('From date must not be after To date.')
    base=" FROM events e LEFT JOIN students s ON s.id=e.student_id LEFT JOIN messages m ON m.event_id=e.id"
    if clauses:base+=' WHERE '+' AND '.join(clauses)
    return base,params

def attendance_view(c,args):
    from urllib.parse import urlencode
    try:base,params=attendance_query(args);error=''
    except ValueError as e:base=' FROM events e LEFT JOIN students s ON s.id=e.student_id LEFT JOIN messages m ON m.event_id=e.id WHERE 0';params=[];error=str(e)
    try:size=int(args.get('att_size',25))
    except ValueError:size=25
    if size not in (25,50,100):size=25
    total=c.execute('SELECT COUNT(*)'+base,params).fetchone()[0];pages=max(1,(total+size-1)//size)
    try:page=max(1,min(pages,int(args.get('att_page',1))))
    except ValueError:page=1
    order='ASC' if args.get('att_order')=='oldest' else 'DESC'
    rows=c.execute("SELECT e.*,s.class_name,COALESCE(m.status,'NO_MESSAGE') AS sms_status"+base+f' ORDER BY e.stamp {order},e.id {order} LIMIT ? OFFSET ?',params+[size,(page-1)*size]).fetchall()
    def link(p):
        values=args.to_dict();values['att_page']=p;return '/attendance?'+urlencode(values)
    tabs=[]
    for value,label in [('', 'All'),('IN','IN'),('OUT','OUT'),('UNKNOWN','Unknown')]:
        values=args.to_dict();values.pop('att_page',None)
        if value:values['att_direction']=value
        else:values.pop('att_direction',None)
        tabs.append((value,label,'/attendance?'+urlencode(values)))
    export_args={k:v for k,v in args.items() if k.startswith('att_')}
    return dict(att_rows=rows,att_total=total,att_page=page,att_pages=pages,att_size=size,att_error=error,att_prev=link(page-1),att_next=link(page+1),att_export='/export?'+urlencode(export_args),att_tabs=tabs,att=args)

def page_context(page):
    from flask import session
    session.setdefault('csrf',os.urandom(24).hex())
    today=now().date().isoformat()
    q=request.args.get('student_q','').strip()
    class_filter=request.args.get('student_class','').strip()
    consent_filter=request.args.get('student_consent','')
    with db() as c:
        all_students=c.execute('SELECT * FROM students ORDER BY name COLLATE NOCASE').fetchall()
        students=[r for r in all_students if (not q or q.casefold() in ' '.join(str(r[k] or '') for k in ['id','name','phone']).casefold()) and (not class_filter or r['class_name']==class_filter) and (consent_filter not in ('0','1') or r['consent']==int(consent_filter))]
        edit_student=c.execute('SELECT * FROM students WHERE id=?',(request.args.get('edit',''),)).fetchone()
        token=record_token(edit_student) if edit_student else ''
        att_args=MultiDict(request.args)
        if page=='attendance' and att_args.get('att_range')!='all' and not att_args.get('att_from') and not att_args.get('att_to'):
            att_args.setlist('att_from',[today]);att_args.setlist('att_to',[today])
        recent=c.execute("SELECT e.*,s.class_name,COALESCE(m.status,'NO_MESSAGE') AS sms_status FROM events e LEFT JOIN students s ON s.id=e.student_id LEFT JOIN messages m ON m.event_id=e.id ORDER BY e.stamp DESC,e.id DESC LIMIT 6").fetchall()
        checkins=c.execute("SELECT COUNT(DISTINCT e.student_id) FROM events e JOIN students s ON s.id=e.student_id WHERE substr(e.stamp,1,10)=? AND e.direction='IN'",(today,)).fetchone()[0]
        checkouts=c.execute("SELECT COUNT(DISTINCT e.student_id) FROM events e JOIN students s ON s.id=e.student_id WHERE substr(e.stamp,1,10)=? AND e.direction='OUT'",(today,)).fetchone()[0]
        k40_scans=c.execute("SELECT COUNT(*) FROM events WHERE substr(stamp,1,10)=? AND source='K40'",(today,)).fetchone()[0]
        baseline_ready=bool(c.execute("SELECT 1 FROM meta WHERE key='baseline'").fetchone())
        config_error=device_config_error()
        if MODE!='device':terminal_label,terminal_color='Not connected','gray'
        elif config_error:terminal_label,terminal_color='Configuration required','amber'
        elif state['last_error']:terminal_label,terminal_color='Connection failed','red'
        elif state['device'].lower().startswith('connection failed'):terminal_label,terminal_color='Connection failed','red'
        elif state['device'].startswith('Connected:'):terminal_label,terminal_color='Connected','green'
        elif state['device'].startswith('Connection test succeeded'):terminal_label,terminal_color='Connection verified','green'
        else:terminal_label,terminal_color='Connecting','gray'
        provider_error=sms_config_error() if MODE=='device' else ''
        sms_ready=MODE=='device' and not config_error and baseline_ready and bool(state['last_poll']) and not state['last_error'] and not provider_error
        context=dict(page=page,mode=MODE,state=state,terminal_label=terminal_label,terminal_color=terminal_color,config_error=config_error,provider_error=provider_error,baseline_ready=baseline_ready,sms_ready=sms_ready,school_name=school_name(),today=now(),student_count=len(all_students),checkins=checkins,checkouts=checkouts,k40_scans=k40_scans,recent=recent,students=students,all_students=all_students,classes=c.execute('SELECT name FROM classes ORDER BY name COLLATE NOCASE').fetchall(),edit_student=edit_student,record_token=token,student_q=q,student_class=class_filter,student_consent=consent_filter,messages=c.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 100').fetchall(),auto_sms=auto_sms,counts=dict(c.execute('SELECT status,COUNT(*) FROM messages GROUP BY status').fetchall()),csrf=session['csrf'])
        if page=='attendance':context.update(attendance_view(c,att_args))
        return context

def render_page(page):
    return render_template(page+'.html',**page_context(page))

@app.get('/')
def index():
    from urllib.parse import urlencode
    if 'edit' in request.args or any(k.startswith('student_') for k in request.args):
        return redirect('/students?'+urlencode(request.args))
    if any(k.startswith('att_') for k in request.args):
        return redirect('/attendance?'+urlencode(request.args))
    return render_page('dashboard')

@app.get('/attendance')
def attendance_page(): return render_page('attendance')

@app.get('/students')
def students_page(): return render_page('students')

@app.get('/guardians')
def guardians_page(): return render_page('guardians')

@app.get('/terminals')
def terminals_page(): return render_page('terminals')

@app.get('/settings')
def settings_page(): return render_page('settings')

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
    return redirect(url_for('students_page')+'#student-register')

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
    return redirect(url_for('students_page')+'#manage-classes')

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
    return redirect(url_for('students_page')+'#student-import')

@app.post('/demo')
def demo():
    if MODE != 'demo': return 'Demo disabled',403
    ingest(request.form['id'],now(),0 if request.form['direction']=='IN' else 1,'DEMO')
    return redirect('/attendance')

@app.post('/test')
def test():
    if MODE != 'device': flash('Set APP_MODE=device in .env and restart first.'); return redirect('/terminals')
    error=device_config_error()
    if error: flash(error); return redirect('/terminals')
    try:
        with poll_lock:
            conn=connect()
            try:
                firmware=conn.get_firmware_version()
                state['device']=f'Connection test succeeded. Firmware: {firmware}'
                flash(f'K40 connection succeeded. Firmware: {firmware}')
            finally: conn.disconnect()
    except Exception as e:
        state['last_error']=f'{type(e).__name__}: {e}'
        state['device']=f'Connection failed: {type(e).__name__}: {e}'
        flash(state['device'])
    return redirect('/terminals')

@app.post('/start')
def start():
    target = '/settings#device-polling' if request.form.get('return_to') == 'settings' else '/terminals'
    if MODE != 'device': flash('Set APP_MODE=device and restart first.'); return redirect(target)
    if start_collector(): flash('Poll requested. The K40 status will update after the read completes.')
    else: flash(device_config_error())
    return redirect(target)

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
    if MODE!='device': flash('Automatic sending is available only in device mode.');return redirect('/settings#sms-control')
    enable=request.form.get('action')=='enable'
    with sms_lock:
        if enable:
            if request.form.get('ack')!='on': flash('Tick the live SMS acknowledgement first.');return redirect('/settings#sms-control')
            if device_config_error(): flash(device_config_error());return redirect('/settings#sms-control')
            with db() as c:baseline_ready=bool(c.execute("SELECT 1 FROM meta WHERE key='baseline'").fetchone())
            if not baseline_ready or not state['last_poll'] or state['last_error']:
                flash('Wait for a successful K40 poll and historical baseline before enabling SMS.');return redirect('/settings#sms-control')
            provider_error=sms_config_error()
            if provider_error:flash(provider_error);return redirect('/settings#sms-control')
            auto_sms=True
            if sms_thread is None or not sms_thread.is_alive():
                sms_thread=threading.Thread(target=sms_worker,daemon=True);sms_thread.start()
        else:
            auto_sms=False
            with db() as c:c.execute("UPDATE messages SET status='CANCELLED',detail='Cancelled when automatic sending was paused.' WHERE status='QUEUED'")
    flash('Automatic SMS ON for new eligible scans.' if enable else 'Automatic SMS OFF. Pending queue cancelled; a submission already in progress may complete.')
    return redirect('/settings#sms-control')

@app.get('/export')
def export():
    try:base,params=attendance_query(request.args)
    except ValueError as e:return str(e),400
    out=io.StringIO(); w=csv.writer(out); w.writerow(['student_id','name','current_class','direction','stamp','source','processing','sms_status'])
    with db() as c:
        rows=c.execute("SELECT e.student_id,e.name,s.class_name,e.direction,e.stamp,e.source,e.reason,COALESCE(m.status,'NO_MESSAGE')"+base+(' ORDER BY e.stamp ASC,e.id ASC' if request.args.get('att_order')=='oldest' else ' ORDER BY e.stamp DESC,e.id DESC'),params)
        for r in rows:
            w.writerow([("'"+str(v)) if str(v).startswith(('=','+','-','@')) else (v or '') for v in r])
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=attendance.csv'})

init()
if __name__=='__main__':
    recover_dispatch()
    start_collector()
    app.run(host='127.0.0.1',port=5000,debug=False)
