# Live K40 setup

The normal installation uses `APP_MODE=device`. The app starts one polling worker automatically when its local configuration is complete. Demo scans remain available only with `APP_MODE=demo` and a restart.

No source-code edits are required at the site. Copy `.env.example` to `.env` on the Windows computer that can reach the K40, then fill the blank values there. The following names are already in the template:

| Setting | What the operator enters |
| --- | --- |
| `SCHOOL_NAME` | The actual institution name. Required to start live polling. |
| `DEVICE_IP` | The K40's IPv4 address on the same reachable network. Required to start live polling. |
| `DEVICE_PORT`, `DEVICE_COMM_KEY`, `DEVICE_FORCE_UDP` | Values from the K40 communication settings; keep defaults only if they match. |
| `DEVICE_DIRECTION` | `PUNCH` for terminal IN/OUT codes; use fixed `IN` or `OUT` only for a dedicated one-direction terminal. |
| `PANDORA_USERNAME`, `PANDORA_PASSWORD`, `PANDORA_SENDER` | Credentials and approved sender for paid SMS. Scans work without them, but automatic SMS cannot be enabled. |
| `PANDORA_MESSAGE_TYPE`, `PANDORA_SENDER_FIELD`, `PANDORA_API_URL` | Provider-specific values to confirm before the first paid submission. |
| `DASHBOARD_PASSWORD`, `APP_SECRET` | Optional local access password and stable session key. |

Leave `APP_MODE=device` and `POLL_SECONDS=10` for the first on-site test. Do not put real credentials in `.env.example` or commit `.env` to Git. Restart the app after changing `.env`; it reads settings at launch.

1. Edit the ignored `cybernet_pilot/.env` on the computer connected to the K40. Set `SCHOOL_NAME` to the real institution and `DEVICE_IP` to the K40's actual IPv4 address. Confirm `DEVICE_PORT`, `DEVICE_COMM_KEY`, `DEVICE_FORCE_UDP`, `DEVICE_DIRECTION=PUNCH`, and `POLL_SECONDS=10`. The example IP from older handover notes is not a working device address.
2. If SMS will be tested, set `SMS_PROVIDER=pandora` and enter the approved `PANDORA_USERNAME`, `PANDORA_PASSWORD`, and `PANDORA_SENDER` in the same local file. Check the provider's message type, sender-field setting, and endpoint. Device scans can be verified first while these credentials remain blank. Keep `.env` and `pilot.sqlite3` out of Git.
3. Register or import a consenting test student. The student ID must exactly match the user ID enrolled on the K40; enter a verified guardian phone. The database in this checkout currently has no students.
4. Start the app with `start_windows.bat` or `python app.py`. It binds to `127.0.0.1:5000`. The Terminals page shows configuration and connection status. Polling starts automatically after valid configuration and retries failures every 10 seconds. Test connection and Retry now remain available without starting a second worker.
5. Wait for the **first successful poll**. That read imports retained history as a baseline without alerts. Then make a new IN punch and a new OUT punch. Confirm the Attendance feed, Dashboard counts, timestamps and direction. The expected punch codes are `0=IN` and `1=OUT`; do not enable SMS until the actual terminal output matches them.
6. After the baseline and Pandora settings are ready, open Settings, tick the paid-send acknowledgement, and enable automatic SMS. Make one further new eligible punch for the consenting test student. Check the app status, the Pandora portal, and the test phone. `ACCEPTED` confirms gateway acceptance only. Reconcile `UNKNOWN` with the provider before considering another send. Pause automatic SMS when the test is complete.

Automatic SMS returns to Off after every app restart. Scans collected while it is Off remain unsent previews and are not sent later merely by enabling it. A scan identifies terminal activity, not physical passage or an absence register. This remains a single-device local pilot.
