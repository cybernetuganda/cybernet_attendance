# Phase 1 — Automatic SMS

## Update your working installation
1. Stop the existing app with Ctrl+C. Close any old copy still running.
2. Back up your entire working cybernet_pilot folder, including .env and pilot.sqlite3.
3. Extract this ZIP elsewhere. Copy app.py, sms_provider.py, send_sms.py and templates/index.html into the matching locations in your working folder.
4. Preserve your working .env, pilot.sqlite3 and .venv. Keep your successful Pandora settings, K40 IP, communication key and direction settings.
5. Start start_windows.bat and open http://127.0.0.1:5000 . Use one running application instance only.

## First automatic test
1. Confirm DEVICE MODE, correct K40/computer times, correct punch mapping, and a consenting test student's phone.
2. Click Start polling and wait for a successful read.
3. In Automatic guardian SMS, tick the acknowledgement and click Enable automatic SMS. This enables live paid submissions for NEW eligible scans.
4. Make one new IN scan. After the poll interval, refresh or wait for the 10-second dashboard refresh. Expect QUEUED -> SUBMITTING -> ACCEPTED, and verify the phone receives it.
5. Make an OUT scan and confirm its message says OUT. A same-direction repeat inside 60 seconds is suppressed.
6. Click Pause automatic SMS when done. Queued items are cancelled. An SMS already being submitted may still complete.

There is no terminal command needed while automatic sending is enabled.

## Behaviour
- Automatic SMS resets to OFF after every application restart. Start polling and enable it again intentionally.
- Old DRY_RUN/SIMULATED messages never become queued merely by enabling automatic sending.
- New real eligible events are saved and queued atomically; the separate SMS worker submits them without blocking device polling.
- Current student consent and the recipient number are checked again immediately before dispatch.
- Messages queued over five minutes are cancelled rather than sent as current alerts.
- A failed validation becomes BLOCKED; explicit gateway failure becomes REJECTED; ambiguous network outcomes become UNKNOWN. None automatically retry.
- On app restart, leftover QUEUED entries become CANCELLED and interrupted SUBMITTING entries become UNKNOWN. Check provider records before considering a resend.
- ACCEPTED is gateway acceptance, not a delivery receipt. The provider's published API has not supplied a delivery callback implementation here.
- The dashboard shows queue/status totals and refreshes every ten seconds unless a form has been edited. Refresh manually after saving a form to resume automatic refresh. Browser refresh is not required for SMS sending.
- Existing contacts and attendance are preserved. No schema migration is required.
- Maintain a single local app instance; multi-process production deployment is not implemented.

## Next phases
Phase 2: explicit student edit actions, visible consent controls, defined classes and a class dropdown, validation and improved student search.
Phase 3: bounded scrollable attendance feed, per-column filters, text search, date ranges and filtered export/pagination.
These phases are planned and are not included in this Phase 1 release.

## Verification
Application and SMS tests use mock network responses and temporary databases. No live messages were sent during development. Test with your consenting volunteer before wider use.
