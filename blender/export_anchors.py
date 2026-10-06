# 导出标注锚点的屏幕坐标（1920×1080 像素），只导出叠加层用得到的时间窗口
# blender -b blender/macbook.blend --python blender/export_anchors.py
import sys, os, json
import bpy
from bpy_extras.object_utils import world_to_camera_view
HERE = os.path.dirname(os.path.abspath(__file__))
OV = os.path.join(HERE, "..", "overlay", "overlay.json")
ov = json.load(open(OV))
sc = bpy.context.scene
cam = sc.camera
W, H = 1920, 1080
FPS = 30
# 平铺/爆炸图标签对应的锚点
PART_ANCHOR = {"lid": "screen", "topcase": "topcase", "bottomcase": "bottomcase", "battery": "battery",
               "logicboard": "logicboard", "trackpad": "trackpad", "speaker_L": "speaker_L", "speaker_R": "speaker_R",
               "usbc0": "usbc0", "usbc1": "usbc1", "magsafe": "magsafe", "audioflex": "jack", "touchidboard": "touchidboard",
               "batcover": "batcover", "hingecover0": "hingecover", "hingecover1": "hingecover", "screw_b0": "screw_b0",
               "keyboard": "keyboard"}
need = {}  # anchor -> set(frames)
def want(anchor, t0, t1, pad=0.4):
    f0, f1 = max(0, int((t0 - pad) * FPS)), min(sc.frame_end, int((t1 + pad) * FPS) + 1)
    need.setdefault(anchor, set()).update(range(f0, f1 + 1))
for c in ov["callouts"]:
    want(c["anchor"], c["t0"], c["t1"])
for k in ov["knoll"]:
    k["anchor"] = PART_ANCHOR.get(k["part"], k["part"])
    want(k["anchor"], k["t0"], k["t1"])
for e in ov["explode"]:
    e["anchor"] = PART_ANCHOR.get(e["part"], e["part"])
    want(e["anchor"], e["t0"], e["t1"])
frames = sorted(set().union(*need.values()))
O = bpy.data.objects
tracks = {a: {} for a in need}
for f in frames:
    sc.frame_set(f)
    for a, fs in need.items():
        if f not in fs:
            continue
        ob = O.get("anc_" + a)
        if ob is None:
            continue
        co = world_to_camera_view(sc, cam, ob.matrix_world.translation)
        tracks[a][f] = [round(co.x * W, 1), round((1 - co.y) * H, 1), 1 if co.z > 0 else 0]
ov["tracks"] = {a: {str(f): v for f, v in sorted(d.items())} for a, d in tracks.items()}
missing = [a for a in need if O.get("anc_" + a) is None]
json.dump(ov, open(OV, "w"), ensure_ascii=False)
print("ANCHORS", len(need), "frames", len(frames), "missing", missing)
