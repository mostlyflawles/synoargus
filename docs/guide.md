# SynoArgus – configuration guide

This guide covers everything after installation. Installing the container is described in the [README](../README.md).
The same guide (shorter, in English and Swedish) is available in SynoArgus under **Guide**.

The menu: **Events · Settings · Status · Guide**. Settings has five tabs: **Cameras · Notifications · Watch · Modes · Other**.
If you leave a tab, camera or the page with unsaved changes, SynoArgus asks first.

<img src="../app/static/guide/en-events.png" alt="The Events page" width="720">

## Contents

1. [Connect Surveillance Station](#1-connect-surveillance-station)
2. [Configure cameras](#2-configure-cameras)
3. [Notifications](#3-notifications)
4. [Modes and Home Mode](#4-modes-and-home-mode)
5. [Calibration](#5-calibration)
6. [Watch (experimental)](#6-watch-experimental)
7. [Overview (experimental)](#7-overview-experimental)
8. [Control cameras via webhook](#8-control-cameras-via-webhook)
9. [Install as an app (PWA) and https](#9-install-as-an-app-pwa-and-https)
10. [Login with Synology SSO](#10-login-with-synology-sso-optional)
11. [Own models (YOLO26 etc.)](#11-own-models-yolo26-etc)
12. [Backup, restore and storage](#12-backup-restore-and-storage)
13. [Security notes](#13-security-notes)
13. [Troubleshooting](#troubleshooting)

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

<img src="../app/static/guide/en-camera.png" alt="Camera settings" width="720">

- **What should be registered as an event?** – object types (the built-in models know the 80 COCO classes).
- **Active in mode** – in which [modes](#4-modes-and-home-mode) the camera alarms (none selected = all).
- **Minimum confidence (%)** – how sure the AI must be (10–95). Empty = the default under Settings > Other.
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

<img src="../app/static/guide/en-notifications.png" alt="Notifications" width="720">

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
| `%event_no%` | `%händelse_nr%` | the event number in SynoArgus | 42 |

**Example – Homey:** webhook, method GET, URL
`https://webhook.homey.app/<homey-id>/synoargus?tag=%camera%;%what%`.
In Homey: *When* Logic > *A webhook is called*, event `synoargus`. The tag becomes e.g. `Backyard;Person`.
Uncheck *Send image* – Homey's webhook does not accept images.

`%event_no%` (`%händelse_nr%`) is the event number in SynoArgus – useful together with *Send only when called* below.

### Send only when called

Each notification has **Send: Immediately / Only when called (webhook)**. With *Only when called* nothing is sent when
the event happens; another system decides – for example a home automation that only wants a phone notification when
nobody is home:

1. An ordinary notification (e.g. a webhook with `%event_no%` in the URL) tells your system about the event.
2. Your system calls

   ```
   GET http://<NAS-IP>:8686/api/notify?token=<token>&notifier=<id or name>&event=<event no>
   ```

   and the notification is sent with the event's image and text. `&text=…` replaces the text. Without `event` the
   latest event waiting for that notification is sent. The page shows the URL under each such notification.
3. **Send anyway after X min** (0 = never) sends it anyway if nobody has called, marked *sent without confirmation*.

Waiting notifications are marked ⏳ under Events and can be requested for 24 hours. A notification with no filters
(all cameras, types and modes) gets a yellow warning.

`%image%` links require being logged in to SynoArgus and are only reachable from your network (or VPN).
Set the address used in links under Settings > Other > Storage.

## 4. Modes and Home Mode


<img src="../app/static/guide/en-modes.png" alt="Modes and schedule" width="720">
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

## 6. Watch (experimental)

Under **Settings > Watch** SynoArgus can keep an eye on a **zone** in one camera – a swing, a patio, a gate – and tell
you when something deviates from how it was. It is based on **motion** (SynoArgus' own image comparison), not on the
AI model, so it also works in the dark and when whoever is watched is only a few dozen pixels tall.

<img src="../app/static/guide/en-watch.png" alt="Watch" width="720">

1. Choose a camera, press **Get image** and drag a box around what should be watched (with a little margin).
   The camera's exclusion zones are honoured too (put them over trees and roads).
2. Choose which events should give a notification and press **Save**.
3. Turn on **Test mode** the first time: events are only logged on the page, nothing is sent.
4. Start it with the button or the webhook (e.g. from Homey when someone goes out):

```
GET http://<NAS-IP>:8686/api/watch?token=<token>&camera=<camera>&action=start
GET http://<NAS-IP>:8686/api/watch?token=<token>&camera=<camera>&action=start&occupied=1   # the zone is already in use
GET http://<NAS-IP>:8686/api/watch?token=<token>&action=stop
GET http://<NAS-IP>:8686/api/watch?token=<token>&action=status
```

`camera` can be left out when only one watch is configured. The page builds the URLs for you.

### Events

<img src="../app/static/guide/en-watch-events.png" alt="Watch events" width="720">

| Event (`%event_id%`) | When | Settings |
|---|---|---|
| Arrival at the zone (`arrive`) | Someone moves up to the zone and stays, or the zone becomes active | – |
| Activity stops (`quiet`) | The zone has been quiet for X s although nobody left it | after X s |
| Activity resumes (`resume`) | Motion in the zone again after *Activity stops* | – |
| Leaves the zone, towards the camera (`leave_toward`) | A track goes from the zone and comes closer (down in the picture / grows) | – |
| Leaves the zone, in another direction (`leave_other`) | A track goes from the zone some other way | – |
| Someone enters the picture (`enter`) | Motion that did not start at the zone, moving purposefully for X s | after X s, *only when the zone is occupied*, *ignore vehicles* |
| Lingers (`linger`) | Whoever entered stops at the zone or somewhere in the picture for X s and is still there, or stays in the picture for a long time | after X s, *in the picture longer than* |
| The watch has been running for a long time (`timeout`) | A reminder after X minutes | after X min |

Every event also has an **own text**, a **quiet time** (no repeat within X s), a choice of **notifications**
(none selected = all notifications that apply to the camera) and **Stop the watch when this happens**.
The watch can also stop by itself after a number of minutes. Each event is saved under Events with an image showing the
zone (blue) and what moved (orange).

In notifications, `%event%` is the event text and `%event_id%` the id in the table; `%what%` contains the text too.
Webhook payloads (JSON) get `"watch_event": "<id>"`.

*Ignore vehicles* asks the AI model what is moving (on a crop around the motion). *Only when the zone is occupied*
keeps whoever walks to the zone from being reported as *Someone enters the picture*.

### Example: a child on the swing

| Setting | Value |
|---|---|
| Zone | around the swing set, with some margin |
| Start | webhook from Homey when the child goes out |
| Arrival at the zone | on |
| Activity stops | 60 s |
| Leaves the zone, towards the camera | on, **stops the watch** |
| Leaves the zone, in another direction | on, to an urgent notification (e.g. ntfy priority 5) |
| Someone enters the picture | 3 s, only when the zone is occupied, ignore vehicles |
| Lingers | 12 s, urgent notification |
| Activity resumes | off |
| Stop automatically after | 90–120 min |

These values were tuned against recordings: a child sitting still for half a minute on her own, a passer-by with dogs
stopping for two seconds, and insects flashing in the infrared light for a fraction of a second.

### Good to know

- Someone standing or sitting completely still is not visible as motion; the arrival and the time are what is detected.
- If the watch is started while the zone is already in use, use *Start – the zone is already occupied* (or `occupied=1`),
  otherwise the first activity is reported as an arrival.
- Low sun (moving shadows), rain, snow and headlights can give false *Someone enters the picture*. Use test mode and
  exclusion zones, and raise the times if needed.
- One watch at a time, and not together with a calibration. Normal alarms work as usual. After a restart of the
  container the watch has to be started again.
- The page shows images per second and milliseconds per image so you can see the load. On a desktop CPU the motion
  analysis takes 15–30 ms per image; a Celeron J3455 is several times slower, which is still well within 3 images/s.
- It is an aid, not a guarantee.

### Check presence with AI

Motion is not visible when someone sits completely still. With **Check presence with AI** the AI model looks at the zone
(plus a margin) every other second. While it sees a person (or one of the camera's types) with at least 40 % confidence,
the zone counts as occupied even without motion, and a new event becomes available: **Nobody in the zone any more**
(`empty`, after X s without anyone). It costs CPU – use a small model.

### Diagnostics

The status shows images per second, the share of the zone that is moving (and the limit), images skipped as light
changes and the share of **duplicates** – images identical to the previous one. Many duplicates mean Surveillance
Station cannot deliver new snapshots fast enough; lower the images per second (1–4). **Show what the watch sees** draws
the motion grid, the moving blobs and the zone on the current image. A zone larger than half the image gives a warning:
when most of the picture is zone, a person close to the camera is easily taken for a light change.

## 7. Overview (experimental)

<img src="../app/static/guide/en-overview.png" alt="Overview" width="720">

The **Overview** tab shows all cameras at once, much like Multi View in Surveillance Station:

- **Layouts** 1×2, 1×3, 2×2 and 2×3 (stored in the browser; more cameras than tiles give pages).
- **Tap a camera** for full screen with sound.
- **Controls:** *Last event* (plays from 3 s before the latest alarm), −1 min, −10 s, +10 s, +1 min, pause and **LIVE**.
- **Timeline** at the bottom: recordings from Surveillance Station (blue) and SynoArgus events (orange). Drag it to play
  from that point; scroll to the left to load earlier days.

How it works:

- Live video goes through **[go2rtc](https://github.com/AlexxIT/go2rtc)** (MIT), bundled in the image. It listens on
  127.0.0.1 inside the container only; the browser talks to SynoArgus, which only lets logged-in users through.
  The video is sent as fragmented MP4 over a WebSocket (Media Source Extensions); no extra port is opened.
- The stream address (RTSP) is read from Surveillance Station. If a camera does not show, enter its own address under
  **Cameras > Video stream for Overview**, e.g. `rtsp://user:password@192.168.1.20:554/stream1`. The address is masked
  in exports without secrets.
- **Sound:** AAC is passed through; G.711 (PCMA/PCMU) is converted by go2rtc. Browsers start video muted until you tap.
- If live video cannot be played, the tile falls back to a snapshot every other second.
- **Recordings** are played through SynoArgus from Surveillance Station's recording API, five minutes at a time. The
  SynoArgus account must be allowed to view recordings (error 105 = missing permission).
- *Show raw data for troubleshooting* shows what Surveillance Station returns, with passwords removed.
- Each live tile is a stream from the NAS. Close the tab when you are not watching.

## 8. Control cameras via webhook

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

## 9. Install as an app (PWA) and https

Under **Settings > Other > Install as an app** SynoArgus can be added to the home screen or desktop and opens in its
own window. Browsers only allow this on **https**. On iPhone/iPad: Share > *Add to Home Screen*.
The app always needs the NAS – without a connection it shows a short message instead of a blank page.

Setting up https with DSM:

1. **Certificate:** Control Panel > External Access > DDNS – create a name (e.g. `yourname.synology.me`) and let DSM
   get a Let's Encrypt certificate.
2. **Reverse proxy:** Control Panel > Login Portal > Advanced > Reverse Proxy > Create.
   Source: HTTPS, your hostname, a port (e.g. 8687). Destination: HTTP, `localhost`, port 8686.
3. **Assign the certificate:** Control Panel > Security > Certificate > Settings – choose the certificate for the new service.
4. Open `https://yourname.synology.me:8687`, log in and press *Install as an app*.

**Do not open a port to the internet** for SynoArgus – use the address at home or over VPN (see
[Security notes](#13-security-notes)). The name must resolve to the NAS from inside (NAT loopback in the router or a
local DNS entry). The Action Rules in Surveillance Station can keep
using the plain http address.

SynoArgus trusts `X-Forwarded-For` / `X-Forwarded-Proto` only from a proxy on the local network (such as DSM's own
reverse proxy), so login throttling and the "setup only from the home network" check cannot be fooled from outside.

## 10. Login with Synology SSO (optional)

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

## 11. Own models (YOLO26 etc.)

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

## 12. Backup, restore and storage

Settings > Other > *Backup*:

- **Export** downloads a JSON file with all settings: cameras, zones, notifiers and the trigger token
  (so your Action Rules keep working). With *Include passwords and keys* the file contains passwords in plain text – keep it safe.
- **Import** replaces all settings. Passwords missing from the file (export without secrets) keep their current values.

Images and history are not part of the export; they live in `data/captures` and `data/history.db`.
Without secrets, webhook URLs, ntfy topics and camera stream addresses are masked too.

**Storage** (Settings > Other): events are kept for X days **or** until the images take up Y MB, whichever comes first
(default 14 days and 2000 MB, 0 = no size limit). The oldest are removed first, checked every 10 minutes. The space used
is shown under Other and on Status.
Every import is checked; invalid values are refused with the name of the field.

## 13. Security notes

- **Do not expose SynoArgus to the internet** – no port forwarding, no public reverse proxy. It shows your cameras and
  recordings. When away, connect to the home network with a VPN (VPN Server in DSM, WireGuard in the router, Tailscale …)
  and use the usual address. Alerts still reach you, since they are sent out from the NAS.
- Passwords and keys are stored in plain text in `data/config.json`, readable by root only. SynoArgus keeps the
  previous version as `config.json.bak` and uses it if the file cannot be read.
- The container log contains no passwords, session ids or webhook addresses (from 0.6). Logs from earlier versions may
  contain them – clear them, and do not paste old logs into an issue.
- The trigger token is part of the webhook URLs. Treat it like a password; change it under Settings > Other if it leaks
  (then use *Update the address* under each camera).
- *Show raw data from Surveillance Station* masks passwords, keys and the addresses of other rules.
- Login is throttled: 5 failed attempts per address or 10 per account within 5 minutes.
- The first setup is only allowed from the local network.

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

**The watch gives too many events**
Run it in test mode, raise the times, turn on *Only when the zone is occupied* and put exclusion zones over trees and roads.

**The watch only shows "quiet" although someone moves**
Look at the diagnostics line. Many duplicates: lower the images per second. A small share of the zone moving: make the
zone tighter or check *Show what the watch sees*. Try *Check presence with AI*.

**Nothing happens when I press a button after an update**
The browser may have kept old files. Reload the page; from 0.7 the files carry the version number and this is not needed.

**Overview only shows still images**
Live video could not be started. Open *Show raw data for troubleshooting*; if the address is empty or wrong, enter the
camera's own RTSP address under Cameras > Video stream for Overview.

**Install as an app is greyed out**
The page must be opened over https, see [Install as an app](#9-install-as-an-app-pwa-and-https).

**Logs**
Container Manager > Container > synoargus > Log.
