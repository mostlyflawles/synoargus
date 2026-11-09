"""Build step: fetch the built-in YOLOX models (Apache-2.0) and convert them to OpenVINO IR.

For each model the ONNX file is taken from ./modeller/<name>.onnx if present, otherwise it is
downloaded from the official YOLOX release. Output: /models/<name>/<name>.xml + .bin + synoargus.json
"""
import json
import os
import shutil
import sys
import time
import urllib.request

import openvino as ov

OUT = sys.argv[1] if len(sys.argv) > 1 else "/models"
LOCAL = os.environ.get("LOCAL_MODELS", "/build/modeller")
MODELS = [m.strip() for m in (os.environ.get("MODELS") or "yolox_tiny,yolox_s,yolox_m").split(",") if m.strip()]
URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/{name}.onnx"


def log(msg):
    print(f"[SynoArgus] {msg}", flush=True)


def fetch(name):
    local = os.path.join(LOCAL, f"{name}.onnx")
    if os.path.isfile(local) and os.path.getsize(local) > 100_000:
        log(f"{name}: using local file {local}")
        return local
    target = f"/tmp/{name}.onnx"
    url = URL.format(name=name)
    for attempt in range(1, 6):
        try:
            log(f"{name}: downloading {url} (attempt {attempt}/5)")
            req = urllib.request.Request(url, headers={"User-Agent": "SynoArgus-build"})
            with urllib.request.urlopen(req, timeout=180) as r, open(target, "wb") as f:
                shutil.copyfileobj(r, f)
            if os.path.getsize(target) > 100_000:
                return target
        except Exception as e:
            log(f"{name}: failed: {e}")
        time.sleep(5 * attempt)
    return None


done = []
for name in MODELS:
    onnx = fetch(name)
    if not onnx:
        log(f"{name}: SKIPPED (could not be downloaded; put {name}.onnx in ./modeller)")
        continue
    model = ov.convert_model(onnx)
    target = os.path.join(OUT, name)
    os.makedirs(target, exist_ok=True)
    ov.save_model(model, os.path.join(target, f"{name}.xml"), compress_to_fp16=True)
    with open(os.path.join(target, "synoargus.json"), "w") as f:
        json.dump({"family": "yolox", "license": "Apache-2.0", "source": "Megvii-BaseDetection/YOLOX"}, f)
    log(f"{name}: saved to {target}")
    done.append(name)

log(f"Done: {', '.join(done) or 'none'}")
if not done:
    sys.exit(1)
