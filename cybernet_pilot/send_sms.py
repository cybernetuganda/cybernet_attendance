"""Manual, single-message dispatch. Never automatically retries uncertain requests."""
import argparse, os
import requests
from app import db
p=argparse.ArgumentParser(description='Review a DRY_RUN message; optionally submit it to Africa\'s Talking.')
p.add_argument('message_id',type=int); p.add_argument('--confirm-send',action='store_true')
a=p.parse_args()
with db() as c:
    r=c.execute('SELECT * FROM messages WHERE id=?',(a.message_id,)).fetchone()
    if not r: raise SystemExit('Message not found')
    print('Recipient:',r['phone']); print('Message:',r['body']); print('Status:',r['status'])
    if not a.confirm_send: raise SystemExit('Preview only. Add --confirm-send to submit this one message.')
    if r['status']!='DRY_RUN': raise SystemExit('Only a fresh DRY_RUN message may be submitted.')
    key=os.getenv('AT_API_KEY'); username=os.getenv('AT_USERNAME')
    if not key or not username: raise SystemExit('Set AT_API_KEY and AT_USERNAME in .env')
    changed=c.execute("UPDATE messages SET status='SUBMITTING' WHERE id=? AND status='DRY_RUN'",(r['id'],)).rowcount
    if not changed: raise SystemExit('Already claimed')
try:
    payload={'username':username,'to':r['phone'],'message':r['body']}
    if os.getenv('AT_SENDER_ID'): payload['from']=os.getenv('AT_SENDER_ID')
    url='https://api.sandbox.africastalking.com/version1/messaging' if username=='sandbox' else 'https://api.africastalking.com/version1/messaging'
    response=requests.post(url,data=payload,headers={'apiKey':key,'Accept':'application/json'},timeout=20)
    data=response.json()
    recipients=data.get('SMSMessageData',{}).get('Recipients',[])
    ok=response.ok and bool(recipients) and all(x.get('statusCode')==101 for x in recipients)
    status='ACCEPTED' if ok else 'REJECTED'
    detail=str([{'status':x.get('status'),'messageId':x.get('messageId')} for x in recipients]) or f'HTTP {response.status_code}'
except Exception:
    status='UNKNOWN'; detail='Submission outcome uncertain. Check provider dashboard before any resend.'
with db() as c: c.execute('UPDATE messages SET status=?,detail=? WHERE id=?',(status,detail,r['id']))
print(status,detail)
print('ACCEPTED means gateway accepted, not delivered to the phone. Check provider delivery reports.')
