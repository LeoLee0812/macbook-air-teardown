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
    e["anchor"] = e.get("anchor") or PART_ANCHOR.get(e["part"], e["part"])
    want(e["anchor"], e["t0"], e["t1"])
# 平铺图标签用的「虚拟锚点」：世界坐标里的固定点（零件落定后静止，镜头缓慢推近）
VIRTUAL = {"kn_lid": (-0.345, 0.056), "kn_topcase": (0.0, 0.056), "kn_bottomcase": (0.345, 0.056),
           "kn_battery": (-0.30, -0.085), "kn_logicboard": (0.10, -0.079), "kn_trackpad": (0.385, -0.082),
           "kn_speaker_L": (-0.36, -0.172), "kn_usbc0": (-0.195, -0.238), "kn_magsafe": (-0.115, -0.172),
           "kn_audioflex": (-0.04, -0.238), "kn_touchidboard": (0.03, -0.172), "kn_batcover": (0.085, -0.238),
           "kn_hingecover0": (0.165, -0.172), "kn_screw_b0": (0.283, -0.238)}
for k in ov["knoll"]:
    v = "kn_" + k["part"]
    if v in VIRTUAL:
        k["anchor"] = v
        want(v, k["t0"], k["t1"])
frames = sorted(set().union(*need.values()))
O = bpy.data.objects
tracks = {a: {} for a in need}
for f in frames:
    sc.frame_set(f)
    for a, fs in need.items():
        if f not in fs:
            continue
        if a in VIRTUAL:
            from mathutils import Vector
            wp = Vector((VIRTUAL[a][0], VIRTUAL[a][1], 0.0))
        else:
            ob = O.get("anc_" + a)
            if ob is None:
                continue
            wp = ob.matrix_world.translation
        co = world_to_camera_view(sc, cam, wp)
        tracks[a][f] = [round(co.x * W, 1), round((1 - co.y) * H, 1), 1 if co.z > 0 else 0]
ov["tracks"] = {a: {str(f): v for f, v in sorted(d.items())} for a, d in tracks.items()}
missing = [a for a in need if O.get("anc_" + a) is None and a not in VIRTUAL]
json.dump(ov, open(OV, "w"), ensure_ascii=False)
print("ANCHORS", len(need), "frames", len(frames), "missing", missing)
