# Cybernet Attendance Developer Handover

Updated 31 October 2026. Owner: Cybernet Computer and Security (U) Ltd. Current stage: Phases 1–3 plus a six-screen UI redesign implemented as a local single-device pilot for school or church Sunday School attendance and guardian SMS.

## Start here
Work in **cybernet_pilot/**. Root-level README.md, Device_Templates/ and Management_Scripts/ belong to the original upstream project and describe its older Access/MySQL design. They are retained for reference; do not launch them for the Cybernet pilot.

Upstream: https://github.com/simiyu-samuel/ZKTeco_SMS_System_v1.0 . Cybernet additions are committed locally; they have not been published to the author's GitHub repository. The supplied bundle contains the Git history.

```powershell
git clone Cybernet_Attendance.bundle CybernetAttendance
cd CybernetAttendance
cd cybernet_pilot
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe app.py
```
Open http://127.0.0.1:5000 . Python 3.11/3.12 recommended. Alternatively run start_windows.bat. Linux developers can use a Python venv and run python app.py. The release ZIP's source/ folder is also a clean working copy if Git is unavailable.

## Implemented features
| Area | Current behaviour |
|---|---|
| Device | ZKTeco K40 LAN connection test, firmware read and polling; default port 4370; communication key and TCP/UDP configurable |
| Identification | Exact K40 user ID mapped to student/child and one guardian phone; fingerprint enrolment remains on device |
| Direction | Configurable PUNCH mapping 0=IN, 1=OUT, or fixed IN/OUT per terminal configuration |
| Register | Add and explicit Edit, fixed device ID on edit, stale-edit protection, guardian phone validation/normalisation |
| Consent | Checkbox and readable status; required with a phone before message preparation; checked again before automatic dispatch |
| Classes | Dropdown, add/rename/remove unused classes; default primary classes plus existing names imported on upgrade |
| Student lookup | Name/ID/phone search, class and consent filters; scrollable list |
| CSV import | Defined class validation, duplicate-ID checks, explicit existing-record update option, atomic rollback on failure |
| Attendance | Timestamped scan feed, retained suppressed/unmapped events and processing explanations |
| Reporting | General search; name, ID, current class, inclusive date range, direction, source, processing and SMS-status filters; paging 25/50/100; oldest/newest order; export all matching rows |
| SMS | Pandora HTTPS POST adapter; optional Africa's Talking adapter; manually reviewed dispatch and automatic sending |
| Automatic mode | Enable/Pause acknowledgement; persistent queue; separate dispatch thread; counters; OFF after restart |
| Reliability | Persistent exact-event deduplication, 60-second same-direction repeat suppression, baseline/history handling, uncertain submissions never auto-retried |
| UI | Dashboard, Attendance, Students, Guardians, Terminals and Settings pages; live data panels update every 10 seconds without replacing open forms |
| Access | Localhost bind, optional dashboard password, POST CSRF checks, upload size limit |
| Change history | Local student create/update action timestamps; no staff identity or audit viewer |

## Code map and storage
| File | Responsibility |
|---|---|
| app.py | Flask routes, SQLite schema, validation, device polling, attendance processing, queue dispatch and reporting queries |
| templates/ and static/ | Shared layout, six page templates, responsive CSS and live-panel JavaScript |
| sms_provider.py | Provider validation, HTTP payloads, response classification and safe diagnostics |
| send_sms.py | Single DRY_RUN message preview/submission with --confirm-send |
| .env.example | Configuration template; real .env must stay private |
| tests/ | 33 automated application, UI and mocked-provider tests |
| PHASE_3_UPDATE.md | Latest installation/reporting notes; consult earlier phase notes only for background |

SQLite tables: students, classes, events, messages, meta, student_changes. Runtime database defaults to pilot.sqlite3 beside app.py; DATABASE_PATH can override it. Timestamps are treated as Africa/Kampala local time. Historical class snapshots are not stored; class filters use the current student assignment. init() creates/migrates missing tables and imports existing class names.

## Configuration and real device run
Preserve the user's working .env. Main settings: APP_MODE=device, SCHOOL_NAME, DEVICE_IP, DEVICE_PORT, DEVICE_COMM_KEY, DEVICE_FORCE_UDP, DEVICE_DIRECTION, POLL_SECONDS. Provider settings: SMS_PROVIDER=pandora, PANDORA_USERNAME, PANDORA_PASSWORD, PANDORA_SENDER, PANDORA_MESSAGE_TYPE, PANDORA_SENDER_FIELD. Optional PANDORA_API_URL allows only the two documented www/non-www HTTPS host variants. Do not change the working sender settings blindly.

Start app, Test connection, Start polling, then Enable automatic SMS. The first successful poll baselines existing logs without alerts; make new scans afterwards. Do not change the connected terminal while reusing an existing baseline database. No code disables, clears or uploads biometric templates to the terminal.

## Processing rules and message states
A new eligible event and its message are saved together. Old scans over five minutes, scans more than two minutes ahead, unknown direction, missing student/contact/consent and repeat scans are retained without a new notification. DEMO creates SIMULATED messages; manual real-device mode creates DRY_RUN; enabled automatic mode creates QUEUED.

QUEUED -> SUBMITTING -> ACCEPTED / REJECTED / UNKNOWN. Local validation produces BLOCKED. Pausing, expiry or changed contact/consent can produce CANCELLED. ACCEPTED means API acceptance, not confirmed phone delivery. No uncertain outcome is automatically retried. Restart cancels QUEUED and marks interrupted SUBMITTING as UNKNOWN. Existing previews are never bulk-sent when automatic mode is enabled. Name/contact changes or consent withdrawal cancel pending QUEUED/DRY_RUN records; in-flight submissions may still complete.

## Verified status and open issues
User confirmed real K40 capture and a successful SMS test, then automatic sending. Later MTN API attempts remained UNKNOWN, although the same numbers received messages from Pandora's web portal. Number formatting alone is not established as the cause. The latest adapter reports redirect/HTTP/non-JSON/TLS/timeout/connection diagnostics without exposing passwords. **MTN API delivery remains unresolved; no delivery callback is implemented.** Reconcile UNKNOWN records against the provider portal before resending.

The 33 tests use temporary databases and mocked device/provider responses. The six UI pages were visually checked at desktop and mobile widths in a browser. Hardware and live gateway testing remain on-site acceptance work. Do not treat mocked tests as end-to-end acceptance. See cybernet_pilot/UI_REDESIGN.md for the screen-to-feature mapping and Pending items.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Immediate developer priorities
1. Reproduce one MTN failure with the current diagnostic adapter; inspect provider-side records and confirm canonical endpoint, message type and response schema. Never log credentials or automatically resend ambiguous submissions.
2. Add multi-device identities/configuration and per-device baselines before delivering two-terminal central operation. Current source identity is the literal K40, so shared-database multi-device use would collide. Do not run multiple copies against the same database as a workaround.
3. Add users/roles, a production WSGI service, controlled startup, backups, monitoring and delivery tracking before shared production deployment. Polling currently reads retained device history every cycle; measure and improve this for larger registers.
4. Add church-specific session/roll-call reports and authorised pickup workflow only after scope approval. Current records are scans, not proof of physical passage, an absence register or pickup authorisation.

## Upgrade and commercial notes
Back up the complete working folder before replacing code. Keep .env, pilot.sqlite3 and device/provider settings. Run one local app instance. No real credentials or child/guardian database are included in this handover. Maintain .gitignore and review staged changes before committing.

Original upstream had no explicit licence file in the inspected checkout; public visibility does not grant commercial reuse rights. pyzk is unofficial and GPL-licensed. Resolve author/dependency distribution obligations before commercial delivery; an official licensed SDK is an alternative to assess. Quotation figures are draft budget estimates, and two-terminal aggregation is proposed deployment work, not a completed feature.
