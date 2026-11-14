"""A model the GPU cannot compile is remembered: the next load goes straight to the CPU (YOLO26 on Intel HD 500)."""
import os, sys, tempfile, types, json
import _env; HERE = _env.setup()
data = tempfile.mkdtemp(); os.environ["SYNOARGUS_DATA"] = data
models = tempfile.mkdtemp()
for name in ("yolo26s", "yolox_s"):
    os.makedirs(os.path.join(models, name))
    open(os.path.join(models, name, "model.xml"), "w").write("<net/>")

CALLS = []
class Dim:
    def get_length(self): return 640
class Shape:
    def __getitem__(self, i): return Dim()
class Inp:
    def get_partial_shape(self): return Shape()
class Net:
    def __init__(self, path): self.path = path; self.inputs = [Inp()]
class Core:
    available_devices = ["CPU", "GPU"]
    def set_property(self, p): pass
    def read_model(self, path): return Net(path)
    def compile_model(self, net, dev, cfg):
        CALLS.append((os.path.basename(os.path.dirname(net.path)), dev))
        if dev == "GPU" and "yolo26" in net.path:
            raise RuntimeError("Exception from src/inference/src/cpp/core.cpp:114:\nProgram build failed")
        return object()
ov = types.ModuleType("openvino"); ov.Core = Core; ov.get_version = lambda: "2025.1"
sys.modules["openvino"] = ov

from app.detector import Detector
d = Detector(models)
d.ensure("yolo26s", "AUTO")
assert CALLS == [("yolo26s", "GPU"), ("yolo26s", "CPU")] and d.device == "CPU" and d.gpu_skipped, (CALLS, d.device)
saved = json.load(open(os.path.join(data, "gpu_unsupported.json")))
assert len(saved) == 1 and list(saved.values())[0]["model"] == "yolo26s" and "core.cpp" in list(saved.values())[0]["error"], saved
assert d.gpu_blocked("yolo26s") and not d.gpu_blocked("yolox_s")
print("A failure remembered OK")

# a new Detector (e.g. after a restart or in the evaluation) does not try the GPU again
CALLS.clear()
d2 = Detector(models); d2.ensure("yolo26s", "AUTO")
assert CALLS == [("yolo26s", "CPU")] and d2.gpu_skipped and d2.status()["gpu_skipped"], CALLS
# models that work on the GPU are unaffected
CALLS.clear(); d2.ensure("yolox_s", "AUTO")
assert CALLS == [("yolox_s", "GPU")] and d2.device == "GPU" and not d2.gpu_skipped
# CPU chosen explicitly: no GPU attempt and nothing marked
CALLS.clear(); d2.ensure("yolox_s", "CPU"); assert CALLS == [("yolox_s", "CPU")]
print("B skip OK")

# a new OpenVINO version (new driver) or a new model file: try the GPU again
ov.get_version = lambda: "2026.0"
CALLS.clear(); Detector(models).ensure("yolo26s", "AUTO")
assert CALLS[0] == ("yolo26s", "GPU"), CALLS
print("C retry on new version OK")

# no GPU in the machine: nothing is marked
ov.get_version = lambda: "2027.0"; Core.available_devices = ["CPU"]
CALLS.clear(); d3 = Detector(models); d3.ensure("yolo26s", "GPU")
assert CALLS[-1] == ("yolo26s", "CPU") and not any("2027.0" in k for k in json.load(open(os.path.join(data, "gpu_unsupported.json"))))
print("ALL gpu OK")
