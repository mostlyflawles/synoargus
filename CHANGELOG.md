# Changelog

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
