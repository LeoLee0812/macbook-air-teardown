# 材质/灯光试渲：一块合盖机身 + 一组键帽，验证 API 和观感
# blender -b --factory-startup --python blender/lookdev.py -- <输出png>
import sys, os, time, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from lib import *  # noqa
from materials import build_materials
import stage

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "/tmp/lookdev.png"
clear_scene()
M = build_materials()
stage.render_settings(res=(1280,720), samples=24)
stage.world()
stage.lights()
cam, tgt = stage.camera(lens=55)
stage.compositor()

W, D = 304.1 * MM, 215 * MM
base = rbox("base", W, D, 7.2 * MM, 14 * MM, (0, 0, 0), mat=M["alu_sky"], bev=1.6 * MM, bev_seg=4)
lid = rbox("lid", W, D, 3.9 * MM, 14 * MM, (0, 0, 7.4 * MM), mat=M["alu_sky"], bev=1.2 * MM, bev_seg=4)
# 打开盖子露出键盘：把 lid 移走，在 base 上放键帽
lid.location = (0, 0.25, 0.0)
lid.rotation_euler = (math.radians(70), 0, 0)
from keyboard_layout import keys_mm
keys, KW, KH = keys_mm()
well = box("well", KW * MM + 2 * MM, KH * MM + 2 * MM, 0.4 * MM, (0, 30 * MM, 6.9 * MM), mat=M["plastic_black"])
for k in keys:
    o = rbox("key", k["w"] * MM, k["h"] * MM, 0.9 * MM, 1.6 * MM, (k["x"] * MM, (k["y"] + 30) * MM, 7.0 * MM),
             mat=M["keycap"], bev=0.35 * MM, bev_seg=2)
cam.location = (0.32, -0.42, 0.30)
tgt.location = (0, 0.0, 0.0)
cam.data.dof.aperture_fstop = 5.6
bpy.context.scene.render.filepath = out
t = time.time()
bpy.ops.render.render(write_still=True)
print("RENDER_SEC", round(time.time() - t, 2))
