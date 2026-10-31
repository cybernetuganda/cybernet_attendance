# Pandora SMS setup

Copy `.env.example` to the ignored `.env` in `cybernet_pilot`, then set these values for the account that will send SMS:

```ini
SMS_PROVIDER=pandora
PANDORA_USERNAME=
PANDORA_PASSWORD=
PANDORA_SENDER=
PANDORA_MESSAGE_TYPE=non_customised
PANDORA_SENDER_FIELD=sender
PANDORA_API_URL=https://www.sms.thepandoranetworks.com/API/send_sms/
```

The username, password, and approved sender are required. The sender is limited to 11 characters in this pilot. Confirm the message type, sender field (`sender` or `sender_id`), and HTTPS endpoint with the provider account before a paid test. Keep credentials out of Git, chat, and screenshots. Do not switch sender fields or endpoints and retry an uncertain submission without checking provider records first.

Automatic SMS remains **Off after every launch**. The app must complete a successful K40 baseline poll before Settings permits staff to enable it. Staff must tick the paid-send acknowledgement. Only subsequent eligible K40 scans for students with a matching device ID, verified guardian phone, and consent are queued. Existing previews are not sent when the switch is enabled. Pausing cancels pending queued messages, but cannot recall a submission in progress.

For the first paid test, use a consenting guardian's verified Uganda number (for example, `+2567XXXXXXXX`) and a short ASCII school/student name. The adapter requires `+256` followed by nine digits and rejects messages over 160 ASCII characters. Make one new scan after enabling, then check the SMS activity page, the Pandora account, and the phone. `ACCEPTED` means gateway acceptance, not confirmed handset delivery. `UNKNOWN` means check the provider record before considering another send. There are no automatic retries of uncertain submissions.

The optional Africa's Talking adapter uses `SMS_PROVIDER=africastalking`, `AT_USERNAME`, `AT_API_KEY`, and optionally `AT_SENDER_ID`. There is no automatic provider failover.

See [LIVE_DEVICE_SETUP.md](LIVE_DEVICE_SETUP.md) for the complete device-to-SMS rollout. No physical K40 or paid Pandora submission was available during development.
