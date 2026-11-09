"""SynoArgus converter: turns your own Ultralytics models (.pt, e.g. YOLO26 or YOLO11) into OpenVINO.

Runs as a separate container (see docker-compose.yml). Reads /in/*.pt and writes
/out/<name>/ (mounted as ./data/models). Models that already exist are skipped.
SynoArgus picks up new models automatically; choose them under Settings > AI.

Note: Ultralytics models are licensed AGPL-3.0. Using them is your own choice.
"""
import glob
import json
import os
import shutil
import sys

IN = sys.argv[1] if len(sys.argv) > 1 else "/in"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/out"
IMGSZ = int(os.environ.get("IMGSZ", "640"))
INT8 = os.environ.get("INT8", "1") not in ("0", "false", "no")


def log(msg):
    print(f"[SynoArgus converter] {msg}", flush=True)


pts = sorted(glob.glob(os.path.join(IN, "*.pt")))
if not pts:
    log(f"No .pt files in {IN}. Put e.g. yolo26s.pt in the 'modeller' folder.")
    sys.exit(0)

from ultralytics import YOLO  # noqa: E402  (import is slow, only when needed)

os.makedirs(OUT, exist_ok=True)
work = "/work"
os.makedirs(work, exist_ok=True)
done, failed = [], []
for pt in pts:
    name = os.path.splitext(os.path.basename(pt))[0]
    target = os.path.join(OUT, name)
    if glob.glob(os.path.join(target, "*.xml")):
        log(f"{name}: already converted, skipping")
        continue
    try:
        local = os.path.join(work, os.path.basename(pt))
        shutil.copy(pt, local)  # export writes next to the .pt file; /in may be read-only
        model = YOLO(local)
        path = None
        if INT8:
            try:
                path = model.export(format="openvino", imgsz=IMGSZ, int8=True, data="coco128.yaml", fraction=0.5)
                log(f"{name}: INT8 done")
            except Exception as e:
                log(f"{name}: INT8 failed ({e}), using FP16")
        if not path:
            path = model.export(format="openvino", imgsz=IMGSZ, half=True)
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(path, target)
        with open(os.path.join(target, "synoargus.json"), "w") as f:
            json.dump({"family": "ultralytics", "license": "AGPL-3.0", "origin": os.path.basename(pt)}, f)
        log(f"{name}: saved to {target}")
        done.append(name)
    except Exception as e:
        log(f"{name}: FAILED: {e}")
        failed.append(name)

log(f"Converted: {', '.join(done) or 'none'}" + (f" · Failed: {', '.join(failed)}" if failed else ""))
log("Restart SynoArgus is not needed – choose the model under Settings > AI.")
