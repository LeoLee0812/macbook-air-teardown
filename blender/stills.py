# 抽帧试渲：blender -b blender/macbook.blend --python blender/stills.py -- <输出目录> <宽> <高> <采样> t1 t2 ...（秒）
import sys, os
import bpy
argv = sys.argv[sys.argv.index("--") + 1:]
out, w, h, spp = argv[0], int(argv[1]), int(argv[2]), int(argv[3])
ts = [float(x) for x in argv[4:]]
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = w, h
sc.eevee.taa_render_samples = spp
for t in ts:
    f = int(round(t * 30))
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, f"f{f:05d}.png")
    bpy.ops.render.render(write_still=True)
    print("STILL", f, flush=True)
