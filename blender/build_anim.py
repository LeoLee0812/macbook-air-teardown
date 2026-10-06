# 只重做动画：载入已建好的模型 .blend，按名字找回零件/锚点/灯光，再跑 anim.build
# blender -b blender/model.blend --python blender/build_anim.py -- [--out blender/macbook.blend]
import sys, os, time, importlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
import tl, anim
importlib.reload(tl)
importlib.reload(anim)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(HERE, "macbook.blend")
t0 = time.time()
O = bpy.data.objects
P = {}
for o in O:
    if not o.name.startswith(("A_", "anc_", "L_", "CAM")):
        P[o.name] = o
for o in O:
    if o.name.startswith("A_"):
        P[o.name[2:]] = o
P["rig"], P["base"], P["lid"] = O["RIG"], O["BASE"], O["LID"]
ANCH = {o.name[4:]: o for o in O if o.name.startswith("anc_")}
LIGHTS = {k: O["L_" + k] for k in ("key", "fill", "rimL", "rimR", "top")}
M = {m.name: m for m in bpy.data.materials}
anim.build(P, ANCH, O["CAM"], O["CAM_target"], LIGHTS, M)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("SAVED", out, round(time.time() - t0, 1), "s")
