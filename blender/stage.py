# 舞台：暗场背景 + 摄影棚环境反射 + 主光/轮廓光 + 摄像机 + Eevee 渲染设置 + 合成（辉光、暗角）
import math
import bpy
from mathutils import Vector
from lib import link, coll, empty
from materials import srgb

FPS = 30


def render_settings(res=(1920, 1080), samples=64, motion_blur=True):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    ee = sc.eevee
    ee.taa_render_samples = samples
    ee.use_raytracing = True
    ee.ray_tracing_method = "SCREEN"
    ee.ray_tracing_options.resolution_scale = "1"
    ee.ray_tracing_options.use_denoise = True
    ee.ray_tracing_options.trace_max_roughness = 0.6
    ee.use_shadows = True
    ee.shadow_ray_count = 2
    ee.shadow_step_count = 8
    ee.shadow_resolution_scale = 1.0
    ee.use_fast_gi = True
    ee.fast_gi_method = "GLOBAL_ILLUMINATION"
    ee.fast_gi_distance = 0.05
    ee.fast_gi_resolution = "2"
    ee.gi_diffuse_bounces = 2
    sc.render.use_motion_blur = motion_blur
    sc.render.motion_blur_shutter = 0.45
    ee.motion_blur_steps = 1
    sc.render.film_transparent = False
    sc.render.use_high_quality_normals = True
    # 色彩管理：AgX + 稍高对比
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception as e:  # noqa: BLE001
        print("color mgmt fallback", e)
    sc.view_settings.exposure = -0.3
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"
    sc.render.image_settings.compression = 15
    sc.render.use_persistent_data = True


def world():
    """相机看到的是近黑的冷灰背景；反射/照明看到的是带几条柔光条的摄影棚环境"""
    w = bpy.data.worlds.new("Studio")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (900, 0)
    lp = nt.nodes.new("ShaderNodeLightPath")
    lp.location = (300, 300)
    # 相机射线：深色背景
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.location = (300, 100)
    bg_cam.inputs["Color"].default_value = srgb("#07090C")
    bg_cam.inputs["Strength"].default_value = 1.0
    # 环境：基于视线方向的渐变 + 柔光条
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, -200)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-700, -200)
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])

    def mapr(src, a, b, c, d_, loc):
        m = nt.nodes.new("ShaderNodeMapRange")
        m.location = loc
        m.inputs["From Min"].default_value = a
        m.inputs["From Max"].default_value = b
        m.inputs["To Min"].default_value = c
        m.inputs["To Max"].default_value = d_
        m.clamp = True
        nt.links.new(src, m.inputs["Value"])
        return m.outputs["Result"]

    # 顶部大柔光（z>0.6 更亮）
    top = mapr(sep.outputs["Z"], 0.35, 0.95, 0.0, 0.84, (-450, -100))   # 顶部穹顶：只留约 25% 亮度
    # 两条竖向柔光条：用 x 方向窄带
    def band(axis_out, center, width, loc):
        sub = nt.nodes.new("ShaderNodeMath")
        sub.operation = "SUBTRACT"
        sub.location = loc
        nt.links.new(axis_out, sub.inputs[0])
        sub.inputs[1].default_value = center
        ab = nt.nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        ab.location = (loc[0] + 150, loc[1])
        nt.links.new(sub.outputs[0], ab.inputs[0])
        return mapr(ab.outputs[0], width * 1.6, 0.0, 0.0, 1.0, (loc[0] + 300, loc[1]))

    b1 = band(sep.outputs["X"], 0.92, 0.06, (-700, -450))
    b2 = band(sep.outputs["X"], 0.08, 0.05, (-700, -650))
    b3 = band(sep.outputs["Y"], 0.85, 0.05, (-700, -850))
    hz = mapr(sep.outputs["Z"], 0.40, 0.62, 0.0, 1.0, (-450, -1050))  # 只在中高位
    def mul(a, b, loc):
        m = nt.nodes.new("ShaderNodeMath")
        m.operation = "MULTIPLY"
        m.location = loc
        nt.links.new(a, m.inputs[0])
        nt.links.new(b, m.inputs[1])
        return m.outputs[0]

    def add(a, b, loc, scale_b=1.0):
        m = nt.nodes.new("ShaderNodeMath")
        m.operation = "MULTIPLY_ADD"
        m.location = loc
        nt.links.new(b, m.inputs[0])
        m.inputs[1].default_value = scale_b
        nt.links.new(a, m.inputs[2])
        return m.outputs[0]

    top2 = mul(top, top, (-250, -100))
    top4 = mul(top2, top2, (-250, -200))
    s = add(mul(top4, top4, (-100, -150)), mul(b1, hz, (-250, -450)), (0, -300), 0.45)
    s = add(s, mul(b2, hz, (-250, -650)), (150, -400), 0.28)
    s = add(s, mul(b3, hz, (-250, -850)), (300, -500), 0.18)
    base = nt.nodes.new("ShaderNodeMath")
    base.operation = "ADD"
    base.location = (450, -500)
    nt.links.new(s, base.inputs[0])
    base.inputs[1].default_value = 0.004
    bg_env = nt.nodes.new("ShaderNodeBackground")
    bg_env.location = (600, -300)
    bg_env.inputs["Color"].default_value = srgb("#DCE6F0")
    nt.links.new(base.outputs[0], bg_env.inputs["Strength"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.location = (750, 0)
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg_env.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return w


def area_light(name, loc, target, size, size_y, energy, color="#FFFFFF", c=None, shape="RECTANGLE", spread=180):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = shape
    ld.size = size
    ld.size_y = size_y
    ld.energy = energy
    ld.color = srgb(color)[:3]
    ld.spread = math.radians(spread)
    ld.use_shadow = True
    try:
        ld.use_shadow_jitter = True
        ld.shadow_jitter_overblur = 10.0
    except Exception:  # noqa: BLE001
        pass
    o = bpy.data.objects.new(name, ld)
    link(o, c)
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return o


def lights(c=None):
    L = {}
    # 主光：左上方大柔光箱
    L["key"] = area_light("L_key", (-0.6, 0.5, 1.0), (0, 0, 0), 1.5, 1.0, 7, "#FFF6EC", c)
    # 补光：右前方低强度
    L["fill"] = area_light("L_fill", (0.7, -0.6, 0.35), (0, 0, 0), 0.8, 0.8, 4, "#DCE8FF", c)
    # 两条轮廓光：后方左右窄长条，勾边
    L["rimL"] = area_light("L_rimL", (-0.6, 0.65, 0.35), (0, 0, 0.0), 0.08, 1.0, 30, "#CFE4FF", c)
    L["rimR"] = area_light("L_rimR", (0.65, 0.6, 0.30), (0, 0, 0.0), 0.08, 1.0, 24, "#FFE9D6", c)
    # 顶光：给内部腔体照亮
    L["top"] = area_light("L_top", (0.0, 0.0, 1.1), (0, 0, 0), 1.2, 1.2, 1.0, "#FFFFFF", c)
    return L


def camera(name="CAM", lens=50, c=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.002
    cd.clip_end = 20
    cd.sensor_width = 36
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = 4.0
    cd.dof.aperture_blades = 7
    cam = bpy.data.objects.new(name, cd)
    link(cam, c)
    tgt = empty(name + "_target", (0, 0, 0), c=c)
    con = cam.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    cd.dof.focus_object = tgt
    bpy.context.scene.camera = cam
    return cam, tgt


def compositor(glare=True, vignette=True):
    sc = bpy.context.scene
    ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
    sc.compositing_node_group = ng
    nodes, links = ng.nodes, ng.links
    rl = nodes.new("CompositorNodeRLayers")
    rl.location = (0, 0)
    last = rl.outputs["Image"]
    if glare:
        g = nodes.new("CompositorNodeGlare")
        g.location = (250, 0)
        # Blender 5.x 起类型和参数都改成了输入插槽（Type 是菜单插槽）
        g.inputs["Type"].default_value = "Bloom"
        g.inputs["Quality"].default_value = "High"
        for key, val in (("Threshold", 2.2), ("Strength", 0.07), ("Size", 0.5), ("Smoothness", 0.4)):
            if key in g.inputs:
                try:
                    g.inputs[key].default_value = val
                except Exception:  # noqa: BLE001
                    pass
        links.new(last, g.inputs["Image"])
        last = g.outputs["Image"]
    # 输出：Group Output（5.x 合成器节点组）
    out = nodes.new("NodeGroupOutput")
    out.location = (700, 0)
    if "Image" not in [s.name for s in ng.interface.items_tree]:
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    links.new(last, out.inputs[0])
    return ng
