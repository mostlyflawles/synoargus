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
- **Modes** (Home / Night / Away or your own): choose per camera and per notification when they are active; switch by hand, schedule (with return to Home Mode), webhook or Surveillance Station Home Mode
- Notifications: **Pushbullet, Telegram, ntfy, email, webhook, MQTT** – with placeholders in texts and URLs
- Web UI in English and Swedish: setup wizard, event history with images, zone editor, test/live view with AI overlay,
  motion detection tuning, **calibration** (measures a day and proposes sensitivity/threshold), built-in guide, backup/restore, update check
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
6. [Configuration](#4-configuration) → [configuration guide](docs/guide.md)
7. [Updating](#5-updating)
8. [Building the image yourself](#building-the-image-yourself)
9. [Publishing a release (maintainers)](#publishing-a-release-maintainers)
10. [Licenses](#licenses)

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
     To use [motion detection tuning](docs/guide.md#motion-detection-tuning) the user also needs permission to change camera settings
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

- `TZ=` – your time zone (e.g. `Europe/Stockholm`, `America/New_York`). Can also be changed later under Settings > Other.
- `devices: /dev/dri` – gives the AI access to an Intel iGPU. **Remove these two lines if the container does not start**
  (e.g. on AMD models); SynoArgus then uses the CPU.
- `ports:` – change the left number if port 8686 is taken.

## 3. First start

Open `http://<NAS-IP>:8686` **from your local network** (the setup wizard is only available from private addresses).

The wizard asks for:

- **NAS address**, e.g. `http://192.168.1.10:5000`
- the **SynoArgus DSM user** from step 1.2
- **your own DSM account** – this becomes the only account allowed to log in to SynoArgus.
  More accounts can be added later under Settings > Other > Login. If you leave it empty, the service account becomes the
  only allowed login.

The language can be switched at the top of the wizard. Your cameras are fetched from Surveillance Station automatically.

## 4. Configuration

Everything else is configured in the web UI. The **[configuration guide](docs/guide.md)** describes it in detail –
the same guide is built into SynoArgus under **Guide** (English and Swedish):

1. [Connect Surveillance Station](docs/guide.md#1-connect-surveillance-station) – an Action Rule per camera (*Create rule* or manually)
2. [Configure cameras](docs/guide.md#2-configure-cameras) – types, confidence, zones, test/live view, motion detection tuning
3. [Notifications](docs/guide.md#3-notifications) – Pushbullet, Telegram, ntfy, email, webhook, MQTT, placeholders, Homey example
4. [Modes and Home Mode](docs/guide.md#4-modes-and-home-mode) – manual, schedule, webhook, Home Mode
5. [Calibration](docs/guide.md#5-calibration) – measure a day, get a proposal for sensitivity/threshold
6. [Control cameras via webhook](docs/guide.md#6-control-cameras-via-webhook)
7. [Login with Synology SSO](docs/guide.md#7-login-with-synology-sso-optional)
8. [Own models (YOLO26 etc.)](docs/guide.md#8-own-models-yolo26-etc)
9. [Backup and restore](docs/guide.md#9-backup-and-restore)
10. [Troubleshooting](docs/guide.md#troubleshooting)

**Locked out of SynoArgus?** Remove the `#` in front of `- SYNOARGUS_UNLOCK=1` in `docker-compose.yml` and build the
project. All DSM accounts can now log in. Add your account under Settings > Other > Login, put the `#` back and build again.

## 5. Updating

- SynoArgus checks GitHub for new versions once a day. A dot on **Status** means an update is available;
  you can also press *Check for update* there.
- To update: Container Manager > **Project** > synoargus > **Action** > **Stop**, then **Action** > **Build**.
  With `pull_policy: always` the newest image is pulled and the container is recreated. Settings, history and own
  models in `data` are kept.
- Afterwards the previous image remains as `<none>` – that is normal Docker behaviour. Remove it with
  Container Manager > **Image** > **Remove Unused Images**.
- With Portainer: *Recreate* the container with *Re-pull image* enabled.

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
