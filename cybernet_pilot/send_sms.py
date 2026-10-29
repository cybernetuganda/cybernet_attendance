"""Manual, single-message dispatch. Never automatically retries uncertain requests."""
import argparse, os
from sms_provider import prepare, submit
from app import db
p=argparse.ArgumentParser(description='Review a DRY_RUN message; optionally submit it to the configured SMS provider.')
p.add_argument('message_id',type=int); p.add_argument('--confirm-send',action='store_true')
a=p.parse_args()
with db() as c:
    r=c.execute('SELECT * FROM messages WHERE id=?',(a.message_id,)).fetchone()
    if not r: raise SystemExit('Message not found')
    print('Recipient:',r['phone']); print('Message:',r['body']); print('Status:',r['status'])
    if not a.confirm_send: raise SystemExit('Preview only. Add --confirm-send to submit this one message.')
    if r['status']!='DRY_RUN': raise SystemExit('Only a fresh DRY_RUN message may be submitted.')
    try: prepared=prepare(r['phone'],r['body'])
    except ValueError as e: raise SystemExit(str(e))
    changed=c.execute("UPDATE messages SET status='SUBMITTING' WHERE id=? AND status='DRY_RUN'",(r['id'],)).rowcount
    if not changed: raise SystemExit('Already claimed')
status,detail=submit(prepared)
with db() as c: c.execute('UPDATE messages SET status=?,detail=? WHERE id=?',(status,detail,r['id']))
print(status,detail)
print('ACCEPTED means gateway accepted, not delivered to the phone. Check provider delivery reports.')
