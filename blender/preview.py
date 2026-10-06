# 试渲几个静态姿态检查模型：closed / open / bottom / inside / exploded / lbclose
# blender -b blender/model_test.blend --python blender/preview.py -- <姿态> <输出png> [宽 高 采样]
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
pose, out = argv[0], argv[1]
w, h, spp = (int(argv[2]), int(argv[3]), int(argv[4])) if len(argv) > 4 else (1280, 720, 24)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = w, h
sc.eevee.taa_render_samples = spp
O = bpy.data.objects
cam, tgt = O["CAM"], O["CAM_target"]
rig, lid = O["RIG"], O["LID"]


def A(n):
    return O["A_" + n]


def hide(n, v=True):
    for o in [A(n)] + list(A(n).children_recursive):
        o.hide_render = v


def flip():
    rig.rotation_euler = (0, math.pi, 0)


if pose == "closed":
    cam.location = (0.36, -0.42, 0.26)
    tgt.location = (0, 0, 0.004)
elif pose == "open":
    lid.rotation_euler = (math.radians(-112), 0, 0)
    cam.location = (0.12, -0.55, 0.32)
    tgt.location = (0, 0.02, 0.06)
elif pose == "bottom":
    flip()
    cam.location = (0.25, -0.38, 0.36)
    tgt.location = (0, 0, 0)
elif pose == "inside":
    flip()
    hide("bottomcase")
    for i in range(4):
        hide(f"screw_b{i}")
    cam.location = (0.0, -0.26, 0.42)
    tgt.location = (0, 0.005, 0)
    cam.data.dof.aperture_fstop = 11
elif pose == "lbclose":
    flip()
    hide("bottomcase")
    for i in range(4):
        hide(f"screw_b{i}")
    hide("logicboard_thermal_dummy") if "A_logicboard_thermal_dummy" in O else None
    O["thermal_plate"].hide_render = True
    O["thermal_tape"].hide_render = True
    cam.location = (-0.06, -0.02, 0.15)
    tgt.location = (-0.098, 0.066, 0)
    cam.data.dof.aperture_fstop = 5.6
elif pose == "exploded":
    lid.rotation_euler = (math.radians(-100), 0, 0)
    lid.location.z += 0.06
    lid.location.y += 0.05
    order = [("bottomcase", -0.0), ("logicboard", 0.04), ("speaker_L", 0.055),
             ("speaker_R", 0.055), ("usbc0", 0.05), ("usbc1", 0.05), ("magsafe", 0.05), ("audioflex", 0.05),
             ("battery", 0.085), ("trackpad", 0.115), ("keyboard", 0.16)]
    for n, dz in order:
        A(n).location.z += dz
    O["topcase"].location.z += 0.14
    O["kb_backplate"].location.z += 0.14
    for i in range(4):
        A(f"screw_b{i}").location.z -= 0.02
    cam.location = (0.45, -0.55, 0.42)
    tgt.location = (0, 0.03, 0.08)
    cam.data.lens = 50
    cam.data.dof.aperture_fstop = 16
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("DONE", out)
