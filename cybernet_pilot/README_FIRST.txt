CYBERNET K40 ATTENDANCE PILOT - START HERE

Live device mode is the default. A real K40 and Pandora account are not included in this repository. The operator enters their values in the ignored .env file; no source-code edits are needed.

1. Install Python 3.11 or 3.12 on the Windows computer that can reach the K40.
2. Copy .env.example to .env in this folder. Fill SCHOOL_NAME and DEVICE_IP; confirm the port, communication key, transport, and punch direction. Keep .env private.
3. In this folder, create a virtual environment with `py -3 -m venv .venv`, then run `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
4. Run `.venv\Scripts\python.exe app.py create-admin`. Enter a private password of at least 12 characters when prompted.
5. Double-click start_windows.bat to start the local app at http://127.0.0.1:5000. Sign in with the account you created.
6. Read AUTHENTICATION.md and LIVE_DEVICE_SETUP.md for account recovery, connection, baseline, test scans, and optional paid SMS rollout.

The app shows Configuration required until the live settings are complete. It will not connect to the old example IP. Demo mode is available only by setting APP_MODE=demo and restarting. The database starts empty; students must be registered or imported with IDs that match K40 user IDs.
