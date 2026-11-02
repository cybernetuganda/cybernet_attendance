# Authentication

The attendance dashboard, student and guardian records, terminal controls, settings, and CSV export require a signed-in operator account. The login screen uses the supplied split-panel design, adapted to Cybernet branding. The Self-Service label is visibly unavailable because guardian accounts and per-guardian data access have not been designed or implemented.

## First setup

From `cybernet_pilot/`, install the requirements and create an administrator account before opening the app:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py create-admin
```

If your Python environment uses another executable, use it for both commands. The default username is `admin`; optionally pass another username after `create-admin`. The command prompts for a password of at least 12 characters and stores a password hash in `pilot.sqlite3`. It never accepts a password on the command line. Repeat `create-admin USERNAME` to add a separate operator account. All current accounts have the same administrative access; roles are future work.

Set a long, random `APP_SECRET` in the private `.env` file to keep sessions valid across restarts. Preserve the secret along with the database when upgrading. The app creates an ephemeral secret if none is set, which signs sessions until the next restart. `SESSION_COOKIE_SECURE=true` is for HTTPS deployments; the default localhost HTTP setup uses `false`.

## Sign in and recovery

Open `http://127.0.0.1:5000/login`. "Remember me" keeps the session for up to 30 days; otherwise it is a browser session. Five failed attempts for the same username and client address block login for 15 minutes. Sign out from the sidebar. A password reset invalidates existing sessions for that account:

```powershell
.venv\Scripts\python.exe app.py reset-password admin
```

The old `DASHBOARD_PASSWORD` setting is no longer used. Existing deployments must create an account before relying on the new login; no password is copied automatically. Back up the working database before upgrading. Keep the existing `.env` private and do not remove the old password until the new account has been created and verified.
