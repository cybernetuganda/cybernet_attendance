# Phase 2 fix — uninterrupted student editing
Stop the app. Replace ONLY templates/index.html in your WORKING installation with this version. Keep .env, pilot.sqlite3 and all working SMS settings. Restart and press Ctrl+F5 once in the browser.

Automatic whole-page refresh has been removed. The attendance feed, notification activity, device/collector status and counters update in place every ten seconds. Student forms, class management and search controls are never replaced by this timer. There is no time limit for adding/editing. Manual browser refresh or navigation can still discard unsaved input.

## MTN delivery diagnosis
Do not switch providers or sender settings before determining where the message stops.
- No notification: inspect the attendance Processing reason and student consent/phone.
- BLOCKED: check the validation detail.
- REJECTED/UNKNOWN: check Pandora account records and contact support if required.
- ACCEPTED but not received: Pandora accepted the API request; this does not establish MTN handset delivery.

Pandora's documentation advertises both Airtel and MTN. It recommends message_type=Info. The existing adapter already supports Info. Test one consenting MTN recipient from the Pandora web portal first, using the same sender/message type and short plain-text content. If the portal also fails, ask Pandora to check the account's MTN route, sender permissions and delivery report. Include recipient, exact Uganda time and message type through their private support channel; do not send passwords.

A controlled test of PANDORA_MESSAGE_TYPE=Info is an option if your account is using non_customised, preferably after Pandora confirms the route/settings. Pause automatic SMS, change only that value, restart and send one new reviewed test message. Check account records before any resend. Do not change sender_id fields or fallback automatically after an uncertain outcome. No sender or routing configuration is changed by this dashboard fix.

Docs: https://sms.thepandoranetworks.com/api
