# 一键重建场景：材质 → 舞台 → 模型 →（动画）→ 存 .blend
# blender -b --factory-startup --python blender/build.py -- [--no-anim] [--out blender/macbook.blend]
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib
import bpy
import lib, materials, stage, model, layout
for mod in (lib, materials, stage, model, layout):
    importlib.reload(mod)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = os.path.join(HERE, "macbook.blend")
if "--out" in argv:
    out = argv[argv.index("--out") + 1]

t0 = time.time()
lib.clear_scene()
M = materials.build_materials()
materials.finish_materials(M)
stage.render_settings()
stage.world()
L = stage.lights(lib.coll("Lights"))
cam, tgt = stage.camera(lens=50, c=lib.coll("Camera"))
stage.compositor()
P, ANCH = model.build(M)
print("MODEL_SEC", round(time.time() - t0, 1), "objects", len(bpy.data.objects))
if "--no-anim" not in argv:
    import anim
    importlib.reload(anim)
    anim.build(P, ANCH, cam, tgt, L, M)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("SAVED", out, round(time.time() - t0, 1), "s")
