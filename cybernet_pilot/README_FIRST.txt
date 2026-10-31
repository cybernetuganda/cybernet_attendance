CYBERNET K40 ATTENDANCE PILOT - START HERE

Live device mode is the default. A real K40 and Pandora account are not included in this repository. The operator enters their values in the ignored .env file; no source-code edits are needed.

1. Install Python 3.11 or 3.12 on the Windows computer that can reach the K40.
2. Copy .env.example to .env in this folder. Fill SCHOOL_NAME and DEVICE_IP; confirm the port, communication key, transport, and punch direction. Keep .env private.
3. Double-click start_windows.bat. It installs dependencies and starts the local app at http://127.0.0.1:5000.
4. Read LIVE_DEVICE_SETUP.md for the connection, baseline, test scans, and optional paid SMS rollout.

The app shows Configuration required until the live settings are complete. It will not connect to the old example IP. Demo mode is available only by setting APP_MODE=demo and restarting. The database starts empty; students must be registered or imported with IDs that match K40 user IDs.
