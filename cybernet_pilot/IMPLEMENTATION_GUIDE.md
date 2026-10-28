# Cybernet F18 school attendance pilot

## What has been built
A separate Python/Flask pilot in `cybernet_pilot/`, informed by the linked project. Original scripts remain unchanged. SQLite replaces the Access/MySQL dependency for a quick local demonstration. Student CSV import, guardian contact/consent mapping, attendance feed, IN/OUT processing, CSV export, demo scans, F18 connection test, persistent deduplication and manually dispatched SMS are included.

This is a local, single-device prototype. No physical F18 or live SMS account was available during development. Automated tests validate application logic, not hardware/network delivery. WhatsApp, automatic SMS dispatch, delivery callbacks, multi-school tenancy and production hosting are not implemented.

## 1. Fastest Windows demonstration
1. Install Python 3.11 or 3.12 from python.org; enable the Python launcher and PATH options.
2. Extract the ZIP to a folder such as `C:\CybernetAttendance`.
3. Open `cybernet_pilot` and double-click `start_windows.bat`. First launch needs internet to install dependencies. Keep the console open.
4. Open http://127.0.0.1:5000 in your browser.
5. Save a fictional student: ID `1001`, name `Demo Student`, class `P5`, a test phone in +256 format. Tick guardian agreement only for your own/consenting volunteer number. No message is sent in demo mode.
6. Select the student, select IN and click Record demo scan. Repeat with OUT.
7. Show the attendance feed and SIMULATED notification previews. Export attendance CSV.
8. Stop with Ctrl+C in the console. Restarting keeps records in `pilot.sqlite3`.

Alternative terminal commands, inside `cybernet_pilot`:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe app.py
```
Do not overwrite an existing configured .env. Linux: create a Python venv, install requirements, copy .env.example to .env, run python app.py. No XAMPP or ZKTime installation is needed for this pilot.

## 2. Connect the F18
Use an isolated test terminal or supplier demo unit first. Do not connect this initial prototype to a live gate lock. Keep biometric enrolment on the F18; the application reads attendance only.

1. Connect laptop and F18 to the same router using Ethernet. Power the F18 with its specified adapter.
2. In the F18 communications menu, set an unused static LAN IP matching your router's subnet. Example ONLY: laptop 192.168.1.10, F18 192.168.1.201, subnet 255.255.255.0. Your existing network may differ.
3. Note the device communication port and communication key/password. The connector defaults to port 4370 and key 0, but these must match the unit. Do not expose this port on the public internet.
4. Set the F18 date/time to Uganda local time, and verify the laptop clock. The application interprets naive terminal timestamps as Africa/Kampala time.
5. Enrol an adult test volunteer on the terminal as user ID 1001. Save the identical ID in the application. Leading zeros matter.
6. Close other attendance software during testing to avoid competing sessions.
7. Edit `.env`:
```ini
APP_MODE=device
DEVICE_IP=192.168.1.201
DEVICE_PORT=4370
DEVICE_COMM_KEY=0
DEVICE_DIRECTION=PUNCH
DEVICE_FORCE_UDP=false
POLL_SECONDS=10
```
8. Restart the application, open the dashboard and click Test connection. If it succeeds, click Start polling ONCE.
9. Wait until the device status shows a successful read. The FIRST read baselines all pre-existing records without alerts. Make your new scans only AFTER that first successful read.
10. Select/check the terminal's attendance status for IN and OUT, then make one scan of each type. Verify the feed. This pilot expects punch 0=IN, 1=OUT; confirm that your F18 actually emits those codes.
11. If your firmware does not expose selectable punch codes, use `DEVICE_DIRECTION=IN` for a dedicated entry terminal. For a one-device presentation you may restart with OUT for the exit demonstration, explicitly explaining the manual switch. Do not alternate directions automatically from scan count.

Network troubleshooting: confirm same subnet, power, cable, correct key and port; ping the IP if ICMP is allowed. A failed ping alone does not prove the device service is unavailable. If the device uses UDP, try DEVICE_FORCE_UDP=true and restart. If pyzk cannot communicate with this firmware, obtain the matching official Standalone SDK or TA Push firmware/documentation from the supplier. Do not flash arbitrary firmware. This connector is a test candidate, not a universal F18 guarantee.

## 3. Student import
Open `students.example.csv` in a text editor or spreadsheet. Required headers:
```csv
id,name,class_name,phone,consent
1001,Demo Student,P5,+256700000000,1
```
Replace the placeholder phone with a verified consenting test recipient. Consent 1 enables notification preparation; 0 records attendance without preparing a message. Preserve IDs and phone numbers as text when editing spreadsheets. Import replaces matching student records. Changing a contact does not rewrite messages already prepared.

## 4. Submit one real SMS for a controlled presentation
The web application NEVER sends SMS automatically. DEMO events are SIMULATED and cannot be dispatched by the SMS script. Only fresh eligible F18 events produce DRY_RUN messages.

1. Obtain Africa's Talking SMS API credentials, a funded live account and an authorised sender arrangement for Uganda. Sandbox credentials do not deliver to an ordinary handset.
2. Add the following to `.env` (do not share this file):
```ini
AT_USERNAME=your_live_username
AT_API_KEY=your_actual_api_key
AT_SENDER_ID=your_approved_sender
```
3. Make a new F18 scan after baselining, and note its notification ID in the dashboard.
4. From a second terminal in `cybernet_pilot`, preview it, substituting the actual ID:
```powershell
.venv\Scripts\python.exe send_sms.py 1
```
5. Check the recipient and exact message. To submit that one message:
```powershell
.venv\Scripts\python.exe send_sms.py 1 --confirm-send
```
6. Refresh the dashboard. ACCEPTED means the gateway accepted the submission, not that the parent received it. Check the provider dashboard and the physical test phone. REJECTED needs provider configuration review. UNKNOWN/SUBMITTING requires checking provider records before any resend; there is intentionally no automatic retry after an ambiguous submission.

No paid messages were sent during development. No credentials are bundled. Live gateway behaviour remains untested.

## 5. Five-minute presentation sequence
- Explain the problem: parents need timely notice of recorded school entry and exit.
- Show student ID to guardian mapping.
- Demonstrate IN and OUT using demo mode OR actual F18 scans.
- Show timestamps and the prepared parent messages. Clearly label simulated/dry-run messages.
- For the hardware demo, manually submit one reviewed SMS and show receipt on the consenting volunteer's phone.
- Scan repeatedly and show duplicate suppression.
- Export CSV and explain the next pilot: two supervised readers/terminals, fixed direction, backup power, automatic SMS queue and delivery tracking.

A scan records verification at the terminal; it does not independently prove physical passage through a gate. Explain this distinction when presenting.

## 6. Current behaviour and limits
- Same device/source, user, timestamp and punch is processed once across restarts.
- Same-direction scans within 60 seconds are retained but suppressed for notifications.
- Old records over five minutes, future records over two minutes, unknown punch codes, missing students and missing consent/phone do not prepare messages.
- On internet recovery, delayed attendance is visible but does not trigger misleading current alerts.
- Baseline is specific to this pilot database and one device. Do not repoint a baselined database at a different terminal. Use a separate clean database path for a new device.
- Polling reads the retained device history each cycle. This is adequate only for a small pilot; measure performance with full F18 logs before scaling. The code does not disable the terminal, clear records or upload biometric templates.
- Dashboard binds only to localhost. Use it on the presentation laptop. Set DASHBOARD_PASSWORD before use with personal records. Shared/network deployment needs a proper server, HTTPS, authentication, roles, monitoring and deployment work.
- One message/guardian per event. No absence rule, early-exit authorisation or pickup verification yet.
- Close the program to stop polling. It is not installed as a Windows background service.

## 7. Verification
```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```
Five automated checks cover duplicate/repeat handling, consent, old/future/unknown/unmapped events, dashboard/CSRF handling and baseline/replay behaviour with a mocked connection. Application logic passed; physical hardware and SMS require your on-site test.

## Source and reuse notes
Upstream inspected: https://github.com/simiyu-samuel/ZKTeco_SMS_System_v1.0 . No explicit licence file was found in the inspected checkout. Public GitHub visibility alone does not establish commercial reuse permission; obtain the author's permission before distributing/commercialising original upstream code. This pilot was separately authored and leaves upstream code unchanged.
Device library: https://github.com/fananimi/pyzk is unofficial and GPL-2.0 licensed. Review dependency obligations before distributing a commercial package; a licensed official SDK may be preferable for the product. No claim of licence clearance is made.
