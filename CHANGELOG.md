# Changelog

## 0.8 (build 14) – 2026-11-12
- **Overview:**
  - Opens as the start page.
  - New layout **1 camera** (‹ › switches camera).
  - Tap the date and time to **jump to a chosen point in time**.
  - **Zoom in full screen:** pinch with two fingers, + / − buttons, double-tap, drag to move, ⟲ to reset.
  - Where there is no recording, SynoArgus's own **image from the event** is shown.
  - Fixed: playback could get stuck, and pause/play did nothing. Playback that stands still is reloaded, the next part starts where the previous one actually ended (or at the next recording), and ▶ reloads a stuck video. The raw data shows the latest playbacks.
- **Settings > Other > Overview:** sound on at once in full screen, and whether the raw-data link is shown (off by default).
- **Cameras:** the fields from *Minimum confidence* to *Video stream* are under **More settings** (closed by default).
- All 80 object types have Swedish names; *Add another type…* is grouped (vehicles, animals, bags, other) and sorted.
- Fixed: the container could refuse to stop while Overview was open. SynoArgus now closes live streams and go2rtc and stops within 5 seconds. `docker-compose.yml` gains `init: true` and `stop_grace_period: 15s` – add them to your own compose file.

## 0.7.1 (build 13) – 2026-11-11
- **Overview:**
  - Fixed: recordings from the NAS were not shown and could not be played when Surveillance Station sent the recording list without start and stop times. The start is now read from the file name and the end is the next recording's start; the timeline shows everything the NAS has recorded, not only SynoArgus events.
  - The tab is now first in the menu.
  - New buttons: **<!** previous event (replaces *Last event*) and **!>** next event (after the last one: live). Order: <! −1 min −10 s ⏸/▶ +10 s +1 min LIVE !>.
  - Pause/play is always shown; pause in live freezes the picture.
  - Date and time on their own line below the buttons.
- Raw data for troubleshooting: Surveillance Station's stream keys (`StmKey`) are masked, the parsed recordings and a two-second test playback are included.
- go2rtc errors are shown per camera and cleared when the stream works again.

## 0.7 (build 12) – 2026-11-11
- **Overview** (experimental), new tab: all cameras live in a grid (1×2, 1×3, 2×2, 2×3, pages if there are more cameras), tap for full screen with sound, *Last event*, −1 min, −10 s, +10 s, +1 min, pause and LIVE, and a scrollable timeline with Surveillance Station recordings and SynoArgus events. Live video via the bundled [go2rtc](https://github.com/AlexxIT/go2rtc) (MIT), which listens on 127.0.0.1 only; SynoArgus passes the video to logged-in users over a WebSocket. Falls back to snapshots if live video cannot be played. Optional own stream address per camera. Raw data for troubleshooting.
- **Watch:**
  - Fixed: the watch could show "quiet" while someone moved. Identical snapshots from Surveillance Station are skipped, zone activity is judged per second instead of per image, and a large person close to the camera is no longer taken for a light change.
  - **Check presence with AI** (per watch): the AI looks at the zone every other second; a person sitting still keeps the zone occupied, and a new event *Nobody in the zone any more*.
  - Diagnostics: duplicates, share of the zone moving, skipped images, and *Show what the watch sees* (an image with motion and zone). Warning when the zone covers more than half the image. 1–4 images per second.
- **Notifications sent on request:** per notification *Send: Immediately / Only when called (webhook)*. Another system asks for it with `/api/notify?token=…&notifier=…&event=…[&text=…]`, optionally sent anyway after X minutes. New placeholder `%event_no%` / `%händelse_nr%`. Waiting notifications are marked ⏳ under Events. Warning for a notification without filters.
- **Export without secrets** also masks webhook URLs, ntfy topics and camera stream addresses.
- **Storage:** keep X days **or** at most Y MB, whichever comes first (default 14 days, 2000 MB). Space used shown under Other and Status.
- **Language before login:** the browser's language (Swedish or English) is used until you choose; the choice is stored in the browser.
- Fixed: after an update the browser could keep an old `app.js`, so buttons (e.g. under Watch) did nothing. Script and style URLs now carry the version and static files are sent with `no-cache`.
- README and guide: do not expose SynoArgus to the internet – use a VPN when away.

## 0.6.1 (build 11) – 2026-11-11
- Fixed: the tests failed on GitHub because a test helper used a package (Starlette) that is not installed there. The tests now need only NumPy and Pillow.
- GitHub Actions: `actions/checkout@v5` and `actions/setup-python@v6` (Node 24), runners pinned to Ubuntu 24.04.
- No changes to the app itself compared with 0.6.

## 0.6 (build 10) – 2026-11-11
- **Watch** (experimental), new tab under Settings: keeps an eye on a zone in one camera and reports *arrival*, *activity stops*, *activity resumes*, *leaves the zone* (towards the camera / another direction), *someone enters the picture*, *lingers* and *running for a long time*. Based on SynoArgus' own motion analysis (works in the dark and at a distance); the AI is only asked whether a newcomer is a vehicle. Per event: time limit, text, quiet time, notifications, *stop the watch*. Test mode, automatic stop, webhook `/api/watch?action=start|stop|status[&occupied=1]`, placeholders `%event%` / `%event_id%`, events saved with an image. Tuned against real recordings (day, dusk, night).
- **Install as an app (PWA)** under Settings > Other (requires https; guide for DSM reverse proxy + Let's Encrypt). Short message instead of a blank page when the NAS cannot be reached.
- Camera: *What should be registered as an event?*, *Active in mode*, *Minimum confidence* as a number field.
- Screenshots (drawn demo camera) in the README, the configuration guide and the in-app guide.
- Security (from a code review):
  - No passwords, session ids, keys or webhook addresses in the container log (the HTTP client and access log no longer log URLs; logins are sent in the request body).
  - `X-Forwarded-For` / `X-Forwarded-Proto` are only trusted from a proxy on the local network, so login throttling and the setup check cannot be bypassed from outside. Throttling also per account.
  - A failed first setup stores nothing. The SSO login checks the nonce.
  - All settings, cameras, notifications, watches and imports are validated; invalid values are refused with the field name.
  - Raw data from Surveillance Station masks passwords, keys and other rules' addresses.
  - `config.json.bak` is kept and used if `config.json` cannot be read.
- Schedule: entries missed while the NAS was busy or the container restarted are caught up (up to 24 h); the last known Home Mode state survives a restart, so a manually set mode is not overwritten.
- Tests are part of the repository (`tests/`) and run by GitHub Actions on every push and before every image build. OpenVINO is pinned to 2025.x.

## 0.5.1 (build 9) – 2026-11-09
- **New menu:** Events · Settings · Status · Guide. Settings has four tabs: Cameras · Notifications · Modes · Other. The last used tab is remembered. *Notifiers* is now called *Notifications*.
- **Guide** in the app (English and Swedish) and `docs/guide.md` on GitHub; the README now covers installation and points to the guide.
- **Unsaved changes warning** when leaving a tab, a camera or the page.
- **Schedule** can set *↩ Follow Home Mode* or *↩ Previous mode*. Between a schedule change and the return, Home Mode changes wait; a change by hand or via webhook applies immediately and ends the waiting.
- **I am walking past now**: 3 images per second for 90 seconds, motion measured between images 1 s apart, the AI analyses as many as it can. During the walk the calibration goes before alarms (alarm snapshots are taken immediately and analysed afterwards, up to 90 s late) – confirmation before start and a countdown in the header.
- **One calibration at a time** (checked in the UI and on the server).

## 0.5 (build 8) – 2026-11-09
- **Calibration** per camera (12–72 h): image pairs every 30 s with SynoArgus' own motion measurement in the detection area plus AI, every Surveillance Station reaction logged with the AI result, *I am walking past now*, load protection.
- Report: reactions, share of noise, missed targets, reactions per hour, day/night; proposal within ±10 in steps of 5 that never lowers the share of reacting targets; minimum data requirements; *Apply* and *Undo*.
- No images are stored; raw data is deleted when the report is ready.

## 0.4.3 (build 7) – 2026-11-09
- **Modes** (Home / Night / Away, renameable, add your own): per camera *Alarms in mode*, per notifier *Only in mode*. Mode pill in the header, mode buttons under Status.
- Mode changes by hand, schedule, webhook (`/api/mode`) or by following Surveillance Station Home Mode – last change wins.
- Action Rules created by SynoArgus are active in Home Mode; *Fix the rule* turns it on for existing rules.
- Yellow warning when a notifier filters on a type (or mode) that its cameras never alarm for.
- Every call from Surveillance Station is logged under Status (also ignored ones, with the reason).
- Wording: "reactions" instead of "triggers" in the motion meter and texts.

## 0.4.2 (build 6) – 2026-11-09
- Fixed (important): *Create rule* overwrote an existing Action Rule (Surveillance Station uses `ruleId`, which was copied from the template). New rules are now built from scratch: motion detected on the camera → webhook to SynoArgus, all week. Safety check: exactly one new rule, no existing rule changed.
- *Fix the rule* for SynoArgus rules not triggered by motion on the right camera.
- Created rules are remembered and shown even when the rules cannot be read.
- Clear messages for missing permissions: Administrator for Action Rules, All-Object Manager for motion detection.
- Raw data box wraps and has a copy button.
- Fixed: own models were labelled "built-in". Model list shows a hint per model (fast / balanced / accurate).
- Update instructions: stop the project first, then Build, then *Remove Unused Images*.
- docker-compose.yml: enabling the converter = delete the first character on each line (indentation stays correct).

## 0.4.1 (build 5) – 2026-11-09
- Fixed: motion detection tuning showed NaN – Surveillance Station returns values as objects (`{"value": 95, "minValue": 1, …}`).
- Saving sensitivity/threshold now sends all other motion settings (detection region etc.) back unchanged, respects min/max and verifies the result.
- Action Rules: shows whether a rule exists for the camera, **Create rule** (from an existing webhook rule as template) and **Update the address** for rules pointing to an old token. Experimental.
- README: credits to SynoAI and a note on AI-assisted development.

## 0.4 (build 4) – 2026-11-09
- Built-in model is now **YOLOX** (Apache-2.0, tiny/s/m). Own Ultralytics models (YOLO26 etc.) via the optional converter container; models in `data/models` are picked up automatically.
- Ready-made images on GitHub Container Registry, built by GitHub Actions – no build on the NAS needed.
- Update check against GitHub (daily + button under Status, dot in the menu).
- English and Swedish UI; alerts and `%what%` follow the language. English placeholder names (`%camera%`, `%what%` …).
- Time zone setting.
- New notifiers: **email**, **Telegram**, **ntfy**.
- Control webhook: `/api/control?camera=all|<name>&action=on|off|toggle|status`.
- Live view with full screen and optional AI overlay.
- Motion detection tuning: read/write Surveillance Station sensitivity and threshold (±5) and a live motion meter.
- Settings export/import (optionally with passwords).
- "Delete all events" under Settings > Storage.
- Mobile: menu on its own row, full width.
- README in English, MIT license.

## 0.3 (build 3) – 2026-11-08
- Placeholders in webhook URL and Pushbullet title/text, with clickable help.
- Copy button works over HTTP; hidden fields fixed; more robust DSM login; unlock via `SYNOARGUS_UNLOCK=1`.

## 0.2 (build 2) – 2026-11-08
- Local model files in `modeller/`, retries and fallback download, cleaner build log.

## 0.1 (build 1) – 2026-11-07
- First version: Surveillance Station trigger, YOLO26 via OpenVINO, per-camera filters and zones, Pushbullet/webhook/MQTT, web UI, DSM/SSO login.
