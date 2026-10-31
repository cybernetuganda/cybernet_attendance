# Six-screen pilot UI

The Flask pilot now opens on a Dashboard with sidebar links to Attendance, Students, Guardians, Terminals, and Settings. The institution label comes from `SCHOOL_NAME`. The operator label is generic because this pilot has no user accounts. No example students or terminal records are inserted.

| Screen | Connected features | Pending displays |
|---|---|---|
| Dashboard | Enrolled student count, distinct mapped students with IN and OUT scans today, recent scans, one K40 status | Absent total, attendance rate, additional terminals |
| Attendance | Today's scans by default, direction tabs, existing report filters, pagination, CSV export, demo scan control | Present/Late/Absent roll call |
| Students | Search, class/consent filters, add/edit, class management, CSV import | Attendance percentage |
| Guardians | One phone and consent record per linked student; edit via Students | Guardian names and independent guardian records |
| Terminals | Configured K40 connection test, automatic polling, Poll now, scan count and last successful poll | Multi-terminal management |
| Settings | Configured institution name, Poll now with live K40 status, manual automatic-SMS enable, SMS activity | Institution type, check-in/late rules, absence SMS |

The UI retains the existing POST routes and `/export`. Old `/?student_*`, `/?edit=`, and `/?att_*` links redirect to their new pages. Attendance dates use Africa/Kampala time. Today's check-in count means distinct mapped students with a recorded IN scan; it is not proof of physical presence or a roll call. `ACCEPTED` SMS still means gateway acceptance, not handset delivery.

Run `python -m unittest discover -s tests -q` from this folder to verify the application. The database context manager now closes connections after each transaction, including on Windows, so temporary test databases can be removed cleanly.
