# SynoArgus

**AI object detection alerts for Synology Surveillance Station.**

Surveillance Station's motion detection fires on everything – shadows, rain, trees, headlights.
SynoArgus sits behind it: when Surveillance Station detects motion, SynoArgus grabs a snapshot,
lets an AI model look for what you care about (person, car, cat …) and only then sends an alert –
with the picture.

- Runs as a single Docker container on the NAS (built for Intel models such as the DS918+, works on any x86-64 host)
- Local AI only – nothing leaves your network except the alerts you configure
- Built-in model: **YOLOX** (Apache-2.0). Optionally bring your own Ultralytics model (YOLO26, YOLO11 …)
- Uses Intel OpenVINO, including the integrated GPU when available
- Per camera: object types, minimum confidence, minimum size, exclusion zones, quiet period, multiple snapshots
- Notifications: **Pushbullet, Telegram, ntfy, email, webhook, MQTT** – with placeholders in texts and URLs
- Web UI in English and Swedish: setup wizard, event history with images, zone editor, test/live view with AI overlay,
  motion detection tuning, backup/restore, update check
- Login with your DSM account or Synology SSO (OpenID Connect)

> SynoArgus is an independent project and is not affiliated with, endorsed by or supported by Synology Inc.
> "Synology" and "Surveillance Station" are trademarks of Synology Inc.

Inspired by [SynoAI](https://github.com/djdd87/SynoAI) by djdd87 (archived). SynoArgus is a separate implementation
written from scratch; no code from SynoAI is used.

SynoArgus was developed with AI assistance (Claude) and tested on a DS918+ by the maintainer.
Issues and pull requests are welcome.

---

## Contents

1. [How it works](#how-it-works)
2. [Requirements](#requirements)
3. [Prepare DSM](#1-prepare-dsm)
4. [Install the container](#2-install-the-container)
5. [First start](#3-first-start)
6. [Connect Surveillance Station](#4-connect-surveillance-station)
7. [Configure cameras](#5-configure-cameras)
8. [Notifications](#6-notifications)
9. [Control cameras via webhook](#7-control-cameras-via-webhook)
10. [Login with Synology SSO](#8-login-with-synology-sso-optional)
11. [Own models (YOLO26 etc.)](#9-own-models-yolo26-etc)
12. [Updating](#10-updating)
13. [Backup and restore](#11-backup-and-restore)
14. [Troubleshooting](#troubleshooting)
15. [Building the image yourself](#building-the-image-yourself)
16. [Publishing a release (maintainers)](#publishing-a-release-maintainers)
17. [Licenses](#licenses)

---

## How it works

```
Camera ──► Surveillance Station ──(motion)──► Action Rule: webhook ──► SynoArgus
                                                                         │
                       snapshot via Surveillance Station Web API ◄──────┘
                                                                         │
                              AI (YOLOX / own model via OpenVINO) ◄─────┘
                                                                         │
             filters: type · confidence · size · zones · quiet period ◄─┘
                                                                         │
           Pushbullet · Telegram · ntfy · email · webhook · MQTT ◄──────┘
```

SynoArgus only analyses when Surveillance Station reports motion, so the NAS is not busy running
AI on video streams all the time.

## Requirements

- Synology NAS with **x86-64 CPU** (Intel/AMD) and **Container Manager** (DSM 7.2+)
- Surveillance Station with your cameras added
- About 400 MB RAM for SynoArgus

Rough speed on a DS918+ (Celeron J3455): YOLOX-S ≈ 0.3–0.6 s per image on the CPU, faster on the iGPU.

---

## 1. Prepare DSM

1. Install **Container Manager** from Package Center.
2. Create a **dedicated DSM user** for SynoArgus (e.g. `synoargus`):
   - no 2-step verification,
   - allowed to use Surveillance Station (Control Panel > User > Applications),
   - in Surveillance Station > Privilege settings: allowed to view the cameras (the "Spectator" profile is enough).
     To use [motion detection tuning](#motion-detection-tuning) the user also needs permission to change camera settings
     (e.g. the "Manager" profile).
3. In File Station, create the folder `docker/synoargus` and inside it an empty folder `data`.
4. Put `docker-compose.yml` from this repository in `docker/synoargus`.

## 2. Install the container

Container Manager > **Project** > **Create**:

| Field | Value |
|---|---|
| Project name | `synoargus` |
| Path | `docker/synoargus` |
| Source | *Use existing docker-compose.yml* |
| Web Station | not needed – leave unchecked |

Container Manager pulls the ready-made image `ghcr.io/mostlyflawles/synoargus:latest` and starts it.

Before creating the project you may want to edit `docker-compose.yml`:

- `TZ=` – your time zone (e.g. `Europe/Stockholm`, `America/New_York`). Can also be changed later under Settings.
- `devices: /dev/dri` – gives the AI access to an Intel iGPU. **Remove these two lines if the container does not start**
  (e.g. on AMD models); SynoArgus then uses the CPU.
- `ports:` – change the left number if port 8686 is taken.

## 3. First start

Open `http://<NAS-IP>:8686` **from your local network** (the setup wizard is only available from private addresses).

The wizard asks for:

- **NAS address**, e.g. `http://192.168.1.10:5000`
- the **SynoArgus DSM user** from step 1.2
- **your own DSM account** – this becomes the only account allowed to log in to SynoArgus.
  More accounts can be added later under Settings > Login. If you leave it empty, the service account becomes the
  only allowed login.

The language can be switched at the top of the wizard. Your cameras are fetched from Surveillance Station automatically.

## 4. Connect Surveillance Station

Do this **for each camera**:

**Automatic (experimental):** under each camera SynoArgus shows whether a matching Action Rule exists.

- **Create rule** copies an existing Action Rule that has a webhook action (for any camera) and adapts it:
  name `SynoArgus - <camera>`, event source = the camera, webhook URL = SynoArgus. So create **one** rule by hand
  (below) first; the rest can be created with the button. Check the result in Surveillance Station.
- **Update the address** fixes existing SynoArgus rules that point to an old address or token
  (e.g. after a fresh install).
- The SynoArgus DSM user needs permission to manage Action Rules in Surveillance Station.
- If something fails, *Show raw data from Surveillance Station* shows what the NAS returned – useful in an issue.

**Manual:**

1. In SynoArgus, open **Cameras**, select the camera and press **Copy** next to the address.
2. In Surveillance Station open **Action Rule** > **Add**:
   - Name: `SynoArgus – <camera>`, rule type *Triggered*, action type *Interruptible*
   - Event: source *Camera*, device *your camera*, event *Motion detected*
   - Action: device **Webhook**, URL = the copied address, method **GET**, times 1
   - Press **Send test**. A line appears in the log under **Status** in SynoArgus.
3. Make Surveillance Station's motion detection fairly sensitive – SynoArgus filters out the noise.
   See [motion detection tuning](#motion-detection-tuning).

**Home Mode:** in Surveillance Station > Home Mode > Settings > Action Rule, a rule that is *checked* stays active while
Home Mode is on; an unchecked rule is disabled while Home Mode is on. When Home Mode is off, the rule's own schedule applies.

## 5. Configure cameras

For each camera under **Cameras**:

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
source is *By Surveillance Station*, and the SynoArgus DSM user needs permission to change camera settings.

## 6. Notifications

Under **Notifiers** you can add as many as you like and limit each one to certain cameras and object types.
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
Set the address used in links under Settings > Storage.

## 7. Control cameras via webhook

Turn the analysis for a camera on or off from Homey, Home Assistant, a script …
(Surveillance Station itself is not affected):

```
GET http://<NAS-IP>:8686/api/control?token=<token>&camera=all&action=off
GET http://<NAS-IP>:8686/api/control?token=<token>&camera=Hallway&action=on
```

- `camera`: `all` or a camera name
- `action`: `on`, `off`, `toggle` or `status`
- The response is JSON with the current state of the affected cameras.

Settings > *Control cameras (webhook)* builds the URL (with your token) for you.

## 8. Login with Synology SSO (optional)

1. Install **SSO Server** from Package Center.
2. SSO Server > **Service**: enable **OIDC** and set a server URL (e.g. `https://192.168.1.10:5001`).
3. **Application list** > **Add** > OIDC:
   - Name: SynoArgus
   - Redirect URI: `http://<NAS-IP>:8686/auth/sso/callback` (shown in SynoArgus under Settings > Login)
4. Copy **Application ID** and **Application Secret** to SynoArgus, and the **well-known URL**
   (or just the part before `/.well-known/…`) to *Issuer*.
5. Check *Enable SSO* and save. The login page now shows *Log in with Synology SSO*.

If the NAS uses a self-signed certificate on that address, leave *Verify HTTPS certificate* unchecked under Surveillance Station.
**Allowed DSM accounts** apply to both password login and SSO.

## 9. Own models (YOLO26 etc.)

The built-in models are YOLOX tiny/s/m (Apache-2.0). You can add Ultralytics models such as **YOLO26** or **YOLO11**:

1. Download the `.pt` files (e.g. `yolo26s.pt`) from Ultralytics and put them in `docker/synoargus/modeller`.
2. In `docker-compose.yml`, remove the `#` in front of the `synoargus-converter` block.
3. Container Manager > Project > synoargus > **Action** > **Build**.
4. The converter (a large image with PyTorch, ~3 GB) runs once, converts new files to `data/models` and stops.
   Conversion takes a few minutes per model; follow it in the container log.
5. In SynoArgus: Settings > AI > Model – your models are listed as *own*. No restart needed.

To add more models later, put the files in `modeller` and start the `synoargus-converter` container again.
You can comment the block out afterwards to save space (and delete the converter image).

> Ultralytics models are licensed **AGPL-3.0**. Using them is your choice; SynoArgus itself (MIT) does not include them.

## 10. Updating

- SynoArgus checks GitHub for new versions once a day. A dot on **Status** means an update is available;
  you can also press *Check for update* there.
- To update: Container Manager > **Project** > synoargus > **Action** > **Build**. With `pull_policy: always`
  the newest image is pulled and the container is recreated. Settings, history and own models in `data` are kept.
- With Portainer: *Recreate* the container with *Re-pull image* enabled.

## 11. Backup and restore

Settings > *Backup*:

- **Export** downloads a JSON file with all settings: cameras, zones, notifiers and the trigger token
  (so your Action Rules keep working). With *Include passwords and keys* the file contains passwords in plain text – keep it safe.
- **Import** replaces all settings. Passwords missing from the file (export without secrets) keep their current values.

Images and history are not part of the export; they live in `data/captures` and `data/history.db`.

---

## Troubleshooting

**Locked out of SynoArgus**
Remove the `#` in front of `- SYNOARGUS_UNLOCK=1` in `docker-compose.yml` and build the project. All DSM accounts can now log in.
Add your account under Settings > Login, put the `#` back and build again.
(`data/config.json` is readable by root only, so it cannot be opened with Text Editor.)

**"pull access denied" / image not found**
The GitHub package must be public (see [publishing](#publishing-a-release-maintainers)), or you build the image yourself.

**Container does not start**
Remove the `devices: /dev/dri` lines (no Intel iGPU).

**Nothing happens when there is motion**
Check under Status > Log whether SynoArgus receives the trigger. If not: is the Action Rule enabled (also in Home Mode)?
Does *Send test* in the Action Rule work? Is the camera *Active* in SynoArgus?

**The AI finds nothing / too much**
Use *Take snapshot and analyse* to see all detections with confidence and the reason they are rejected.
Lower the minimum confidence or minimum size, try a larger model (yolox_m) or check the zones.

**Copy button does not work**
Browsers only allow automatic copying on HTTPS pages; over HTTP SynoArgus selects the text so you can press Ctrl+C.

**Logs**
Container Manager > Container > synoargus > Log.

---

## Building the image yourself

```bash
docker build -t synoargus:local .
```

The build downloads the YOLOX models from GitHub. To avoid that, put `yolox_tiny.onnx`, `yolox_s.onnx` and
`yolox_m.onnx` in `modeller/` first. Then use `image: synoargus:local` and `pull_policy: never` in `docker-compose.yml`.

On a Synology without SSH you can build with Task Scheduler (Control Panel > Task Scheduler > Create > Scheduled Task >
User-defined script, user **root**):

```bash
cd /volume1/docker/synoargus
DOCKER_BUILDKIT=0 docker build -t synoargus:local . > build.log 2>&1
```

The converter image: `docker build -f converter/Dockerfile -t synoargus-converter:local .`

## Publishing a release (maintainers)

1. Update `APP_VERSION` in `app/version.py` and `CHANGELOG.md`, commit and push.
2. Create and push a tag: `git tag v0.4 && git push origin v0.4`.
3. GitHub Actions (`.github/workflows/release.yml`) builds `synoargus` and `synoargus-converter`, pushes them to
   `ghcr.io/<owner>/…` with the tags `0.4` and `latest`, and creates a GitHub release.
4. **First time only:** on GitHub, open your profile > Packages > `synoargus` (and `synoargus-converter`) >
   Package settings > *Change visibility* > **Public**. Otherwise the NAS cannot pull the images without logging in.

The update check in SynoArgus compares `APP_VERSION` with the latest release/tag of the repository
(`SYNOARGUS_REPO` environment variable, default `mostlyflawles/synoargus`).

## Licenses

- SynoArgus: **MIT** – see [LICENSE](LICENSE).
- Built-in models: **YOLOX** by Megvii, Apache-2.0.
- Main dependencies: OpenVINO (Apache-2.0), FastAPI (MIT), Uvicorn (BSD), HTTPX (BSD), Pillow (MIT-CMU), NumPy (BSD),
  paho-mqtt (EPL-2.0 / EDL-1.0).
- Optional converter: Ultralytics (AGPL-3.0) and PyTorch (BSD) – only used if you enable it for your own models.
