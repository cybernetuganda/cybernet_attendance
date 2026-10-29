CURRENT RELEASE: PHASE 1 AUTOMATIC SMS. Read PHASE_1_UPDATE.md first; it supersedes older manual-only instructions below.

# Pandora SMS setup for the K40 pilot

Documentation checked: https://sms.thepandoranetworks.com/api

Python can call the same HTTP API as PHP. This adapter submits form-encoded HTTPS POST data, with no automatic redirects or retries. It uses the documented send endpoint and normalises +256 numbers to 256. Pandora lists MTN and Airtel only. Use a verified consenting test recipient.

## Update your existing working installation
Stop the application. Back up the existing folder. From this updated ZIP, copy ONLY `sms_provider.py` and `send_sms.py` into your existing `cybernet_pilot` folder. Preserve your existing `.env` and `pilot.sqlite3`; do not replace them. No database migration is required.

Append these settings to your existing `.env` (keep APP_MODE=device and your K40 settings unchanged):
```ini
SMS_PROVIDER=pandora
PANDORA_USERNAME=your_account_username
PANDORA_PASSWORD="your_account_password"
PANDORA_SENDER=Cybernet
PANDORA_MESSAGE_TYPE=non_customised
PANDORA_SENDER_FIELD=sender
```
Use your actual account credentials and a sender accepted for your account. Use quotes around passwords containing spaces or #. Do not paste credentials into a chat or screenshot. The adapter defaults to the documented generic sender mode; a customised sender requires provider approval/setup.

The documentation conflicts: the parameter list and GET example use `sender`, while the POST example uses `sender_id`. We default to `sender`. If Pandora support confirms `sender_id`, change PANDORA_SENDER_FIELD accordingly. Do not automatically try both after an uncertain request; check provider records first to avoid duplicate SMS charges. The parameter section says sender maximum 11 characters while one example says 20; the adapter uses the stricter 11-character limit.

## Send one reviewed message
1. Restart the app, click Start polling, then make a new K40 scan with a student mapped to a consenting test phone. Note its DRY_RUN notification ID.
2. Open a second terminal inside your existing cybernet_pilot folder.
3. Preview the message (replace 12 with its ID):
```powershell
.venv\Scripts\python.exe send_sms.py 12
```
4. Check recipient and body, then submit once:
```powershell
.venv\Scripts\python.exe send_sms.py 12 --confirm-send
```
5. Refresh the dashboard and inspect your phone and Pandora account.

ACCEPTED: Pandora returned HTTP success and JSON success=true. This is provider acceptance, not independently confirmed phone delivery.
REJECTED: Pandora returned success=false. Check account balance, credentials, sender permissions and recipient format with support.
UNKNOWN/SUBMITTING: Check Pandora logs or support before any resend. Timeouts may happen after a message was accepted. Raw provider text is deliberately not stored because it could echo credentials.

For the first test use a short ASCII student name and school name: this adapter rejects non-ASCII and messages longer than the documented 160-character limit. It never silently truncates. If a body is too long, shorten school/student names and create a NEW event; ask Pandora about multipart/Unicode support before extending it.

Demo messages remain SIMULATED and cannot be dispatched. Real eligible K40 scans create DRY_RUN messages. Dispatch remains manual in this version; automatic alerts are the next implementation stage after a successful provider test.

## Fallback
The previous Africa's Talking adapter remains available. Set SMS_PROVIDER=africastalking and configure AT_USERNAME, AT_API_KEY and optionally AT_SENDER_ID. There is no automatic failover, because a timeout at one provider does not prove that it failed to send.

## Verification
Five provider tests use mocked responses, not live submissions: request field mapping, sender variant, limits, response classification, and no retries on timeout. No account credentials or paid SMS were used during development.
