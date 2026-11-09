# Changelog

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
