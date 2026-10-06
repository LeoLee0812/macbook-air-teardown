# 渲染序列帧（JPEG 96，跳过已存在的帧，可断点续渲）
# blender -b blender/macbook.blend --python blender/render_frames.py -- <输出目录> <起始帧> <结束帧> [采样]
import sys, os, time
import bpy
argv = sys.argv[sys.argv.index("--") + 1:]
out, f0, f1 = argv[0], int(argv[1]), int(argv[2])
spp = int(argv[3]) if len(argv) > 3 else 32
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.eevee.taa_render_samples = spp
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 96
t_start = time.time()
done = 0
for f in range(f0, f1 + 1):
    p = os.path.join(out, f"f{f:05d}.jpg")
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        continue
    sc.frame_set(f)
    sc.render.filepath = p
    t = time.time()
    bpy.ops.render.render(write_still=True)
    done += 1
    el = time.time() - t_start
    print(f"FRAME {f} {time.time() - t:.2f}s avg {el / done:.2f}s", flush=True)
print("RENDER_DONE", f0, f1, flush=True)
