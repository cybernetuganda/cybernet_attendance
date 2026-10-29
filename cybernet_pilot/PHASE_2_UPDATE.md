# Phase 2 — Student management

## Install over your working Phase 1 application
1. Stop the app with Ctrl+C and back up your complete working folder.
2. Extract the updated ZIP into a separate location.
3. Copy ONLY app.py and templates/index.html into their matching locations in your working cybernet_pilot folder.
4. Keep your existing .env, pilot.sqlite3, .venv, sms_provider.py and send_sms.py. Your working Pandora configuration is unchanged.
5. Restart using start_windows.bat. New class and change-history tables are added automatically; existing students, attendance and SMS records remain.
6. Start polling and enable automatic SMS again when ready, as in Phase 1.

## Student actions
- Add: select a defined class, enter the exact K40 ID, name and optional guardian number. SMS consent is a clear checkbox. Consent requires a phone number.
- Edit: find a student and click Edit. Update name, class, guardian number and consent, then Save changes. Device ID is read-only to preserve attendance identity. Changing a device ID is not included.
- Consent: tick only after obtaining guardian agreement; untick to stop preparing new alerts. Name/contact changes or withdrawal cancel that student's pending QUEUED/DRY_RUN messages. Messages already being submitted may still complete. Older attendance and sent-message history keep their original values.
- Search: search by name, device ID or guardian phone; filter by class or consent. Clear restores the full list.
- Existing IDs are not silently overwritten by Add. The app requires Edit. If another save happened while the edit page was open, refresh and edit again.
- The application does not enrol fingerprints or edit the K40 user directly; IDs must match the device.

## Classes
Defaults: Baby, Middle, Top and P1–P7. Existing class names are imported into the catalog automatically. Open Manage classes to add or rename a class; renaming updates assigned students. Only unused classes can be removed. Choose your school's real labels, including streams where needed, e.g. P5 Blue or S1.

## CSV import
Define classes first. Headers remain id,name,class_name,phone,consent. Use 0/1 for consent. Import rejects undefined classes, invalid Uganda phones, duplicate IDs within the CSV and existing IDs unless Update matching device IDs is ticked. Validation failure rolls back the entire import. Existing-record updates follow the same pending-message cancellation rules as Edit. Phone values starting with 256 are normalised to +256. Preserve ID leading zeros in your CSV.

## Checks to perform
1. Add a class and a new test student; ensure the class appears in the dropdown.
2. Edit the student's class and phone, and verify the list.
3. Search by name and ID, then filter class and consent.
4. Untick consent, make a new scan, and verify attendance is recorded without an SMS notification.
5. Restore consent; make a fresh eligible scan and verify automatic SMS as before.

The local change log records student create/update actions and timestamps. It does not identify an authenticated staff member; multi-user roles and a full audit viewer remain future work.

Phase 3 remains separate: attendance feed filters, search, scrollable layout, date ranges and filtered export/pagination.

Verification: 22 automated tests passed, including student edits, stale-form protection, consent cancellation, class rename/removal, CSV rollback and prior SMS tests. Dashboard/edit pages render successfully in application tests; a browser visual check was unavailable in this environment. No live SMS was sent during development.
