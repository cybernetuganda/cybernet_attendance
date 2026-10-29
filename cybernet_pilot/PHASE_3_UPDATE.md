# Phase 3 — Attendance reporting

Stop the application and back up the working folder. Extract this package separately and replace ONLY app.py and templates/index.html in your working folder. Keep .env, pilot.sqlite3, .venv and the successful or diagnostic SMS adapter settings. Restart and hard-refresh the browser once with Ctrl+F5.

## Included
- Scrollable attendance feed with sticky column headings.
- General search plus student name, device ID, class, date range, direction, source, processing reason and SMS status filters.
- 25/50/100 rows per page, previous/next links and oldest/newest sorting.
- Export all matching records, not just the displayed page.
- Empty-result messages and invalid date feedback.
- Live updates preserve student input and attendance filters. Applying filters/paging uses in-place updates, even if periodic updates are turned off.

Dates are inclusive Uganda local calendar dates. Class means the student's current class; a historical class snapshot is not stored. Attendance remains raw scan records, not a roll-call or absent-child calculation. NO_MESSAGE means no SMS record was prepared for that attendance event. ACCEPTED means provider acceptance, not proof of handset receipt.

## Church Sunday School setup
Set SCHOOL_NAME in your existing .env to the church/Sunday School name, keeping generated messages short enough for the current provider limit. Use Manage classes to add the church's actual groups, e.g. Toddlers, Beginners, Juniors and Teens. Preserve existing student IDs and use verified guardian contacts and consent. A fixed-IN entry and fixed-OUT exit terminal require separate device processes/configuration; this application remains a single-device pilot. Multi-device central operation needs a further implementation stage before delivery of the proposed two-terminal deployment.

## Outstanding SMS issue
MTN API submissions remain UNKNOWN. This release does not claim to resolve delivery and makes no provider configuration changes. Keep automatic sending paused if you are not ready for paid tests. Records can still be collected and reports demonstrated. Check provider records before resending uncertain messages.

29 automated tests cover the application and mocked provider logic, including combined filters, dates, paging, export, consent and duplicate handling. No physical device or live gateway was exercised in this release. Browser visual testing remains unavailable in this runtime.
