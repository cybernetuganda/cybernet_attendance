"""Provider adapters. No retries: uncertain submissions require reconciliation."""
import os
import requests

def prepare(phone, body):
    provider=os.getenv('SMS_PROVIDER','pandora').lower()
    if provider=='pandora':
        username=os.getenv('PANDORA_USERNAME'); password=os.getenv('PANDORA_PASSWORD'); sender=os.getenv('PANDORA_SENDER')
        if not username or not password or not sender: raise ValueError('Set PANDORA_USERNAME, PANDORA_PASSWORD and PANDORA_SENDER in .env')
        if len(sender)>11: raise ValueError('Pandora sender must be at most 11 characters')
        if len(body)>160 or not body.isascii(): raise ValueError('For this pilot use an ASCII message of at most 160 characters; confirm Unicode/multipart support with Pandora')
        number=phone.lstrip('+')
        if not number.isdigit() or not number.startswith('256') or len(number)!=12: raise ValueError('Pandora pilot expects a Uganda number such as +2567XXXXXXXX')
        field=os.getenv('PANDORA_SENDER_FIELD','sender')
        if field not in ('sender','sender_id'): raise ValueError('PANDORA_SENDER_FIELD must be sender or sender_id')
        kind=os.getenv('PANDORA_MESSAGE_TYPE','non_customised')
        if kind not in ('Info','non_customised','customised'): raise ValueError('Invalid Pandora message type')
        return provider,'https://www.sms.thepandoranetworks.com/API/send_sms/',{'username':username,'password':password,'number':number,'message':body,field:sender,'message_type':kind,'message_category':'bulk'},{'Accept':'application/json'}
    if provider=='africastalking':
        key=os.getenv('AT_API_KEY'); username=os.getenv('AT_USERNAME')
        if not key or not username: raise ValueError('Set AT_API_KEY and AT_USERNAME')
        payload={'username':username,'to':phone,'message':body}
        if os.getenv('AT_SENDER_ID'):payload['from']=os.getenv('AT_SENDER_ID')
        url='https://api.sandbox.africastalking.com/version1/messaging' if username=='sandbox' else 'https://api.africastalking.com/version1/messaging'
        return provider,url,payload,{'apiKey':key,'Accept':'application/json'}
    raise ValueError('SMS_PROVIDER must be pandora or africastalking')

def submit(prepared):
    provider,url,payload,headers=prepared
    try:
        # Refuse automatic redirects to avoid forwarding credentials or changing POST to GET.
        response=requests.post(url,data=payload,headers=headers,timeout=20,allow_redirects=False)
        if 300<=response.status_code<400:return 'UNKNOWN','Redirect refused; verify endpoint with provider before resending.'
        if response.status_code>=500:return 'UNKNOWN','Provider server error; check provider records before resending.'
        data=response.json()
        if provider=='pandora':
            if response.ok and data.get('success') is True:return 'ACCEPTED','Pandora reports success. Delivery not independently confirmed.'
            if data.get('success') is False:return 'REJECTED','Pandora reports failure. Check credentials, sender, balance and recipient in the provider dashboard.'
            return 'UNKNOWN','Unexpected Pandora response; check provider records before resending.'
        recipients=data.get('SMSMessageData',{}).get('Recipients',[])
        if response.ok and recipients and all(x.get('statusCode')==101 for x in recipients):return 'ACCEPTED','Gateway accepted submission. Delivery not independently confirmed.'
        return 'REJECTED','Gateway rejected submission; check provider dashboard.'
    except Exception:
        return 'UNKNOWN','Outcome uncertain; check provider records before resending.'
