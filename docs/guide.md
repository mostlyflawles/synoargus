# SynoArgus – configuration guide

This guide covers everything after installation. Installing the container is described in the [README](../README.md).
The same guide (shorter, in English and Swedish) is available in SynoArgus under **Guide**.

The menu: **Events · Settings · Status · Guide**. Settings has four tabs: **Cameras · Notifications · Modes · Other**.
If you leave a tab, camera or the page with unsaved changes, SynoArgus asks first.

## Contents

1. [Connect Surveillance Station](#1-connect-surveillance-station)
2. [Configure cameras](#2-configure-cameras)
3. [Notifications](#3-notifications)
4. [Modes and Home Mode](#4-modes-and-home-mode)
5. [Calibration](#5-calibration)
6. [Control cameras via webhook](#6-control-cameras-via-webhook)
7. [Login with Synology SSO](#7-login-with-synology-sso-optional)
8. [Own models (YOLO26 etc.)](#8-own-models-yolo26-etc)
9. [Backup and restore](#9-backup-and-restore)
10. [Troubleshooting](#troubleshooting)

---

## 1. Connect Surveillance Station

Do this **for each camera**:

**Automatic (experimental):** under each camera SynoArgus shows whether a matching Action Rule exists.

- **Create rule** creates a new rule `SynoArgus - <camera>`: event *Motion detected* on the camera, action webhook (GET)
  to SynoArgus, schedule all week. SynoArgus checks afterwards that exactly one new rule was added and that no
  existing rule changed. The time of creation is remembered and shown even if the rules cannot be read later.
- **Update the address** fixes SynoArgus rules that point to an old address or token (e.g. after a fresh install).
- **Fix the rule** appears if a SynoArgus rule is not triggered by motion on that camera.
- Reading and creating rules requires the **Administrator** profile in Surveillance Station for the SynoArgus user.
  You can enable it temporarily, create/update the rules and switch back – the rules keep working.
- If something fails, *Show raw data from Surveillance Station* (with a copy button) shows what the NAS returned –
  useful in an issue.

**Manual:**

1. In SynoArgus, open **Settings > Cameras**, select the camera and press **Copy** next to the address.
2. In Surveillance Station open **Action Rule** > **Add**:
   - Name: `SynoArgus – <camera>`, rule type *Triggered*, action type *Interruptible*
   - Event: source *Camera*, device *your camera*, event *Motion detected*
   - Action: device **Webhook**, URL = the copied address, method **GET**, times 1
   - Press **Send test**. A line appears in the log under **Status** in SynoArgus.
3. Make Surveillance Station's motion detection fairly sensitive – SynoArgus filters out the noise.
   Every call from Surveillance Station is shown under Status > Log (also ignored ones: quiet period, mode, disabled).
   See [motion detection tuning](#motion-detection-tuning).

**Home Mode:** in Surveillance Station > Home Mode > Settings > Action Rule, a rule that is *checked* stays active while
Home Mode is on; an unchecked rule is disabled while Home Mode is on. SynoArgus rules should **always be active**
(rules created by SynoArgus are) – use [modes](#4-modes-and-home-mode) in SynoArgus to decide when to alarm instead. *Fix the rule*
turns this on for existing rules.

## 2. Configure cameras

For each camera under **Settings > Cameras**:

- **What should trigger an alarm?** – object types (the built-in models know the 80 COCO classes).
- **Minimum confidence** – how sure the AI must be.
- **Minimum width/height** – ignore tiny detections far away.
- **Quiet after alarm** – no new alarms for X seconds after one was sent.
- **Minimum time between analyses** – limits load if Surveillance Station triggers constantly.
- **Snapshots per motion event** – if the first snapshot shows nothing, take another one.
- **Exclusion zones** – press *Get image* and drag boxes, e.g. over the neighbour's driveway.
  *Fully inside* ignores objects completely inside the zone, *Touches* ignores anything touching it.

### Test and live view

- **Take snapshot and analyse** shows exactly what the AI finds and why each detection would or would not alarm –
  without sending anything. Unsaved settings are used, so you can experiment.
- **Live** shows a continuously refreshed image (about 1–3 frames/s) with a **full screen** button.
  With **Show AI** every frame is analysed and the boxes are drawn.

### Motion detection tuning

Under each camera, SynoArgus reads **Sensitivity** and **Threshold** from Surveillance Station's motion detection and lets you
change them in steps of 5 and save them back. Press **Start measuring** and walk in front of the camera: the motion meter
flashes every time Surveillance Station triggers SynoArgus and shows triggers per minute and the AI result.

- **Sensitivity** (1–99): how much a pixel must change to count. Higher = smaller changes count.
- **Threshold** (1–99): how large a share of the detection area must change. Lower = smaller areas trigger.

This uses the Surveillance Station Web API (`SYNO.SurveillanceStation.Camera.Event`). It only works when the camera's detection
source is *By Surveillance Station*, and the SynoArgus DSM user needs the **All-Object Manager** (or Administrator)
profile. All other motion settings (detection area etc.) are sent back unchanged.

## 3. Notifications

Under **Settings > Notifications** you can add as many as you like and limit each one to certain cameras, object types and modes.
Save, then press **Send test**.

| Type | What you need |
|---|---|
| **Pushbullet** | Access token from pushbullet.com > Settings > Account. *Device id* (optional) is **not** the phone model: go to pushbullet.com > Devices, click the device and copy what follows `#devices/` in the address bar. |
| **Telegram** | Create a bot with **@BotFather** and copy the token. Send a message to the bot, open `https://api.telegram.org/bot<token>/getUpdates` and copy `chat.id`. For a group, add the bot to the group (the id starts with `-`). |
| **ntfy** | Install the ntfy app (Google Play / App Store / F-Droid) and subscribe to a topic. Use a hard-to-guess topic name on ntfy.sh – anyone who knows it can read the messages – or run your own ntfy server. Priority 5 breaks through Do Not Disturb. |
| **Email** | Any SMTP server. Gmail: `smtp.gmail.com`, port 587, STARTTLS and an *app password*. The image is attached. |
| **Webhook** | Any URL. POST/PUT send JSON (see below), optionally multipart with the image in `image` and the JSON in `payload`. GET sends `camera`, `types` and `message` as query parameters unless the URL contains placeholders. |
| **MQTT** | Broker host/port (e.g. Homey or Mosquitto). Published to `synoargus/<camera>/notification` as JSON, optionally with the image base64-encoded in `image`. |

JSON payload (webhook and MQTT):

```json
{
  "camera": "Backyard",
  "types": ["person"],
  "message": "Backyard: 2 people",
  "time": "2026-11-09T22:58:14+01:00",
  "detections": [{"label": "person", "confidence": 87.4, "x1": 812, "y1": 301, "x2": 990, "y2": 902}],
  "image_url": "http://192.168.1.10:8686/captures/2026-11-09/225814_123_Backyard.jpg",
  "event_id": 42
}
```

### Placeholders

Placeholders can be used in webhook URLs and in the title/text/subject of Pushbullet, Telegram, ntfy and email.
In URLs the values are URL-encoded automatically. A clickable list is shown in the UI. English and Swedish names work alike.

| Placeholder | Swedish | Meaning | Example |
|---|---|---|---|
| `%camera%` | `%kamera%` | camera name | Backyard |
| `%what%` | `%vad%` | what was found (UI language) | Person, Cat |
| `%what_en%` | `%vad_en%` | what was found (English labels) | person, cat |
| `%count%` | `%antal%` | number of detections | 3 |
| `%message%` | `%meddelande%` | the full message | Backyard: 2 people, Cat |
| `%confidence%` | `%säkerhet%` | highest confidence in % | 87 |
| `%time%` | `%tid%` | time | 22:58:14 |
| `%date%` | `%datum%` | date | 2026-11-09 |
| `%image%` | `%bild%` | link to the image in SynoArgus | http://…/captures/….jpg |

**Example – Homey:** webhook, method GET, URL
`https://webhook.homey.app/<homey-id>/synoargus?tag=%camera%;%what%`.
In Homey: *When* Logic > *A webhook is called*, event `synoargus`. The tag becomes e.g. `Backyard;Person`.
Uncheck *Send image* – Homey's webhook does not accept images.

`%image%` links require being logged in to SynoArgus and are only reachable from your network (or VPN).
Set the address used in links under Settings > Other > Storage.

## 4. Modes and Home Mode

SynoArgus has a current **mode** – by default *Home*, *Night* and *Away*. Rename them and add your own under
**Settings > Modes**.

- **Per camera** (Settings > Cameras > *Alarms in mode*): in which modes the camera alarms. None selected = all modes.
- **Per notification** (Settings > Notifications > *Only in mode*): in which modes it is sent. None selected = all modes.
- When a camera is not active in the current mode, Surveillance Station's call is ignored without analysis
  (shown as *mode … – no alarm* in the motion meter and the log).

The mode is changed by whatever happens last:

| Source | How |
|---|---|
| Manually | Click the mode pill at the top, or Status > Mode |
| Schedule | Settings > Modes > Schedule, e.g. *Night* at 01:00 and *↩ Follow Home Mode* at 06:00 |
| Webhook | `GET /api/mode?token=<token>&mode=night` (id or name; `mode=status` only returns the current mode) – e.g. from Homey presence |
| Home Mode | Settings > Modes > *Follow Home Mode*: e.g. Home Mode on → *Home*, off → *Away* (checked every 20 s) |

### Schedule with return

A schedule entry can set a mode, **↩ Follow Home Mode** or **↩ Previous mode**.

- From a schedule change until the schedule returns, **Home Mode changes wait** (Status shows ⏸).
- **↩ Follow Home Mode** switches to the mode Home Mode indicates at that moment. If Home Mode is not followed or
  unknown, it goes back to the mode before the schedule.
- **↩ Previous mode** goes back to the mode before the schedule period.
- A change **by hand or via webhook** applies immediately and ends the waiting.

Example: Follow Home Mode (on → *Home*, off → *Away*) plus *Night* at 01:00 and *↩ Follow Home Mode* at 06:00 every day.
Leaving at 03:00 keeps *Night* until 06:00, then *Away*. Coming home at 05:00 gives *Home* at 06:00.

Filter example: outdoor cameras alarm in all modes, the hall only at *Night* and *Away*; Telegram is sent only at
*Night* and *Away*, while the Homey webhook gets everything (e.g. to turn on lights).

## 5. Calibration

Under each camera (Settings > Cameras), **Calibration** measures how the camera behaves over 12–72 hours (default 24)
and proposes sensitivity and threshold for Surveillance Station.

- Every 30 seconds SynoArgus takes **two images one second apart**, measures itself how much of the camera's
  detection area changed (independent of Surveillance Station's own logic) and lets the AI decide whether one of the
  camera's object types is visible and moving. This gives two distributions: *noise* and *moving target*.
- Every **reaction** from Surveillance Station is logged too, with the AI result – also during quiet periods and in
  modes where the camera does not alarm. A moving target with no reaction nearby counts as *missed*.
- **I am walking past now** takes **3 images per second for 90 seconds** – walk through the picture meanwhile.
  Motion is measured between images 1 second apart (image *i* against *i+3*) and the AI analyses as many images as it
  can keep up with (on a J3455 with yolox_s roughly 2 of 3). Only analysed images become image pairs.
- During those 90 seconds **the calibration goes before alarms**: snapshots for alarms from all cameras are taken
  right away, but analysed when the walk is over – alarms can arrive up to 90 seconds late. A confirmation is shown
  before it starts and the header shows *Calibrating – alarms delayed* with a countdown.
- **Only one calibration at a time.** Start is disabled on the other cameras while one is running (the server checks
  this as well). Finished reports stay on each camera.
- **No images are stored**, only numbers. The raw data is deleted when the report is ready. Outside the walk, normal
  alarms always go first and image pairs are spaced out if the analysis is slow.
- The report shows reactions, share of noise, missed targets, reactions per hour and day/night separately.
- The **proposal** changes each value by at most ±10 in steps of 5, never reduces the share of targets that react,
  and requires enough data (at least 20 reactions or 30 image pairs, and 2 moving targets for a full proposal).
  It is **never applied automatically**: *Apply the proposal* saves it in Surveillance Station, *Undo* restores the
  previous values.
- Best results: run it during a normal day and walk past the camera 2–3 times. An empty house only gives noise,
  and then the proposal can only make the camera less sensitive.

> The proposal is an estimate. Synology does not document its algorithm, so SynoArgus maps sensitivity to the pixel
> change that counts (`4 + (99 − S) × 60/98` of 255) and threshold to the share of the detection area (`T %`).
> Check the result with the motion meter and run another calibration if needed.

## 6. Control cameras via webhook

Turn the analysis for a camera on or off from Homey, Home Assistant, a script …
(Surveillance Station itself is not affected):

```
GET http://<NAS-IP>:8686/api/control?token=<token>&camera=all&action=off
GET http://<NAS-IP>:8686/api/control?token=<token>&camera=Hallway&action=on
```

- `camera`: `all` or a camera name
- `action`: `on`, `off`, `toggle` or `status`
- The response is JSON with the current state of the affected cameras.

Settings > Other > *Control cameras (webhook)* builds the URL (with your token) for you.

## 7. Login with Synology SSO (optional)

1. Install **SSO Server** from Package Center.
2. SSO Server > **Service**: enable **OIDC** and set a server URL (e.g. `https://192.168.1.10:5001`).
3. **Application list** > **Add** > OIDC:
   - Name: SynoArgus
   - Redirect URI: `http://<NAS-IP>:8686/auth/sso/callback` (shown in SynoArgus under Settings > Other > Login)
4. Copy **Application ID** and **Application Secret** to SynoArgus, and the **well-known URL**
   (or just the part before `/.well-known/…`) to *Issuer*.
5. Check *Enable SSO* and save. The login page now shows *Log in with Synology SSO*.

If the NAS uses a self-signed certificate on that address, leave *Verify HTTPS certificate* unchecked under Surveillance Station.
**Allowed DSM accounts** apply to both password login and SSO.

## 8. Own models (YOLO26 etc.)

The built-in models are YOLOX tiny/s/m (Apache-2.0). You can add Ultralytics models such as **YOLO26** or **YOLO11**:

1. Download the `.pt` files (e.g. `yolo26s.pt`) from Ultralytics and put them in `docker/synoargus/modeller`.
2. In `docker-compose.yml`, delete **only the first character (`#`)** on each of the 8 `synoargus-converter` lines
   at the bottom. The indentation is then correct (YAML is sensitive to spaces).
3. Container Manager > Project > synoargus > **Action** > **Stop**, then **Action** > **Build**.
4. The converter (~3 GB image with PyTorch) starts, converts new files to `data/models` and stops by itself.
   **Wait until `synoargus-converter` shows as stopped** in Container Manager (status *Exited*) – its log ends with
   `Converted: …`. This takes a few minutes per model.
5. Then choose the model in SynoArgus under Settings > Other > AI – your models are listed as *own*. No restart needed.
   Recommended on a Celeron J3455: an **s** model (e.g. `yolo26s`). Check the time with *Take snapshot and analyse*;
   under ~1 s per image is good.

To add more models later, put the files in `modeller` and start the `synoargus-converter` container again.
You can comment the block out afterwards to save space (and delete the converter image).

> Ultralytics models are licensed **AGPL-3.0**. Using them is your choice; SynoArgus itself (MIT) does not include them.

## 9. Backup and restore

Settings > Other > *Backup*:

- **Export** downloads a JSON file with all settings: cameras, zones, notifiers and the trigger token
  (so your Action Rules keep working). With *Include passwords and keys* the file contains passwords in plain text – keep it safe.
- **Import** replaces all settings. Passwords missing from the file (export without secrets) keep their current values.

Images and history are not part of the export; they live in `data/captures` and `data/history.db`.

---

## Troubleshooting

**Locked out of SynoArgus**
Remove the `#` in front of `- SYNOARGUS_UNLOCK=1` in `docker-compose.yml` and build the project. All DSM accounts can now log in.
Add your account under Settings > Other > Login, put the `#` back and build again.
(`data/config.json` is readable by root only, so it cannot be opened with Text Editor.)

**"pull access denied" / image not found**
The GitHub package must be public (see [publishing](../README.md#publishing-a-release-maintainers)), or you build the image yourself.

**Container does not start**
Remove the `devices: /dev/dri` lines (no Intel iGPU).

**Alarms arrive late**
During *I am walking past now* (90 s) the calibration goes before alarms; alarms are queued and analysed afterwards.
The header shows *Calibrating – alarms delayed*.

**Nothing happens when there is motion**
Check under Status > Log whether SynoArgus receives the trigger. *ignored (mode …)* means the camera does not alarm in the current mode. If not: is the Action Rule enabled (also in Home Mode)?
Does *Send test* in the Action Rule work? Is the camera *Active* in SynoArgus?

**The AI finds nothing / too much**
Use *Take snapshot and analyse* to see all detections with confidence and the reason they are rejected.
Lower the minimum confidence or minimum size, try a larger model (yolox_m) or check the zones.

**Copy button does not work**
Browsers only allow automatic copying on HTTPS pages; over HTTP SynoArgus selects the text so you can press Ctrl+C.

**Logs**
Container Manager > Container > synoargus > Log.
