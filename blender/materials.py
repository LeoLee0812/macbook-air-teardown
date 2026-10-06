# 材质库：天蓝色阳极氧化铝、内腔铝、PCB、金、铜、芯片、电芯、键帽（含背光）、屏幕等
# 可动画的参数（屏幕亮度、键盘背光、散热热力图）挂在材质节点上，用 keyframe 驱动
import os
import bpy

TEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tex")


def srgb(hexstr):
    """十六进制 sRGB → 线性 RGB（Blender 节点里的颜色是线性的）"""
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def new_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m, nt, bsdf


def setp(bsdf, **kw):
    names = {
        "base": "Base Color", "metal": "Metallic", "rough": "Roughness", "coat": "Coat Weight",
        "coat_rough": "Coat Roughness", "emit": "Emission Color", "emit_str": "Emission Strength",
        "spec": "Specular IOR Level", "ior": "IOR", "alpha": "Alpha", "trans": "Transmission Weight",
        "aniso": "Anisotropic", "sss": "Subsurface Weight",
    }
    for k, v in kw.items():
        bsdf.inputs[names[k]].default_value = v


def planar_uv(nt, w, d, cx=0.0, cy=0.0, loc=(-900, 0)):
    """物体坐标 XY → [0,1] UV：适用于贴在顶面的平面贴图"""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = loc
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (loc[0] + 200, loc[1])
    mp.vector_type = "POINT"
    mp.inputs["Scale"].default_value = (1.0 / w, 1.0 / d, 1.0)
    mp.inputs["Location"].default_value = (0.5 - cx / w, 0.5 - cy / d, 0.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    return mp.outputs["Vector"]


def image_node(nt, fname, vec, loc=(-500, 0), colorspace="sRGB", extension="CLIP"):
    path = os.path.join(TEX, fname)
    if not os.path.exists(path):
        return None
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = img
    tn.location = loc
    tn.extension = extension
    tn.interpolation = "Cubic"
    nt.links.new(vec, tn.inputs["Vector"])
    return tn


def micro_bump(nt, bsdf, scale=2500.0, strength=0.06, dist=0.0002, loc=(-500, -400)):
    """喷砂铝的细微颗粒感"""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (loc[0] - 400, loc[1])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.location = (loc[0] - 200, loc[1])
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.location = loc
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = dist
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return bp


def value_node(nt, name, val, loc=(-300, 300)):
    v = nt.nodes.new("ShaderNodeValue")
    v.name = name
    v.label = name
    v.location = loc
    v.outputs[0].default_value = val
    return v


def build_materials():
    M = {}

    # 机身：天蓝色阳极氧化铝（M4 MacBook Air 的「天蓝色」）
    m, nt, b = new_mat("alu_sky")
    setp(b, base=srgb("#9FB6C9"), metal=1.0, rough=0.42)
    micro_bump(nt, b)
    M["alu_sky"] = m

    # 铝件内壁：CNC 加工面，更亮更光
    m, nt, b = new_mat("alu_inner")
    setp(b, base=srgb("#B9BEC4"), metal=1.0, rough=0.32)
    micro_bump(nt, b, scale=900, strength=0.04)
    M["alu_inner"] = m

    m, nt, b = new_mat("alu_dark")  # 深灰铝（铰链、支架）
    setp(b, base=srgb("#5B6066"), metal=1.0, rough=0.3)
    M["alu_dark"] = m

    m, nt, b = new_mat("plastic_black")
    setp(b, base=srgb("#1A1B1D"), metal=0.0, rough=0.48)
    M["plastic_black"] = m

    m, nt, b = new_mat("plastic_gray")
    setp(b, base=srgb("#3A3D41"), metal=0.0, rough=0.5)
    M["plastic_gray"] = m

    m, nt, b = new_mat("rubber")
    setp(b, base=srgb("#141414"), metal=0.0, rough=0.85)
    M["rubber"] = m

    m, nt, b = new_mat("foam")
    setp(b, base=srgb("#0E0F10"), metal=0.0, rough=0.95)
    M["foam"] = m

    m, nt, b = new_mat("mylar_black")  # 黑色绝缘胶带
    setp(b, base=srgb("#121314"), metal=0.0, rough=0.55, coat=0.1)
    M["mylar_black"] = m

    m, nt, b = new_mat("graphite")  # 石墨导热片
    setp(b, base=srgb("#2A2C30"), metal=0.55, rough=0.42)
    micro_bump(nt, b, scale=600, strength=0.08)
    M["graphite"] = m

    m, nt, b = new_mat("gold")
    setp(b, base=srgb("#E9C27A"), metal=1.0, rough=0.22)
    M["gold"] = m

    m, nt, b = new_mat("copper")
    setp(b, base=srgb("#E8A07E"), metal=1.0, rough=0.28)
    M["copper"] = m

    m, nt, b = new_mat("steel")
    setp(b, base=srgb("#C9CBCE"), metal=1.0, rough=0.3)
    M["steel"] = m

    m, nt, b = new_mat("steel_dark")  # 黑色螺丝
    setp(b, base=srgb("#2B2D30"), metal=1.0, rough=0.35)
    M["steel_dark"] = m

    m, nt, b = new_mat("shield")  # 屏蔽罩：镀锡钢
    setp(b, base=srgb("#BFC3C6"), metal=1.0, rough=0.38)
    micro_bump(nt, b, scale=400, strength=0.03)
    M["shield"] = m

    m, nt, b = new_mat("flex_amber")  # 聚酰亚胺软排线
    setp(b, base=srgb("#9A4E12"), metal=0.15, rough=0.3, coat=0.6, coat_rough=0.15)
    M["flex_amber"] = m

    m, nt, b = new_mat("flex_black")
    setp(b, base=srgb("#16171A"), metal=0.1, rough=0.32, coat=0.4)
    M["flex_black"] = m

    m, nt, b = new_mat("chip_epoxy")  # 黑色封装
    setp(b, base=srgb("#1C1D1F"), metal=0.0, rough=0.55)
    M["chip_epoxy"] = m

    m, nt, b = new_mat("die")  # 裸硅片：近镜面的深灰带一点彩虹色
    setp(b, base=srgb("#4A4F5A"), metal=0.9, rough=0.08, coat=0.4, coat_rough=0.02)
    M["die"] = m

    m, nt, b = new_mat("substrate")  # 封装基板
    setp(b, base=srgb("#2B3A2E"), metal=0.1, rough=0.4, coat=0.5)
    M["substrate"] = m

    m, nt, b = new_mat("ceramic")  # 贴片电容（陶土色）
    setp(b, base=srgb("#6E5E48"), metal=0.0, rough=0.5)
    M["ceramic"] = m

    m, nt, b = new_mat("resistor")
    setp(b, base=srgb("#202122"), metal=0.0, rough=0.45)
    M["resistor"] = m

    m, nt, b = new_mat("magnet")
    setp(b, base=srgb("#AEB0B2"), metal=1.0, rough=0.25)
    M["magnet"] = m

    m, nt, b = new_mat("white_print")
    setp(b, base=srgb("#E8E8E8"), metal=0.0, rough=0.6)
    M["white_print"] = m

    m, nt, b = new_mat("tab_white")  # 易拉胶拉片（黑色带白字的拉片，取深灰）
    setp(b, base=srgb("#3B3D40"), metal=0.0, rough=0.45, sss=0.0)
    M["tab_white"] = m

    m, nt, b = new_mat("tab_clear")  # 透明背胶
    setp(b, base=srgb("#DCDCD4"), metal=0.0, rough=0.25, alpha=0.55)
    m.surface_render_method = "BLENDED"
    M["tab_clear"] = m

    # 屏幕边框黑玻璃
    m, nt, b = new_mat("glass_black")
    setp(b, base=srgb("#050607"), metal=0.0, rough=0.12, coat=1.0, coat_rough=0.06)
    M["glass_black"] = m

    # 摄像头镜头
    m, nt, b = new_mat("lens")
    setp(b, base=srgb("#0B0C14"), metal=0.6, rough=0.05, coat=1.0, coat_rough=0.01)
    M["lens"] = m

    m, nt, b = new_mat("lens_ring")
    setp(b, base=srgb("#222634"), metal=1.0, rough=0.18)
    M["lens_ring"] = m

    # 触控板玻璃：哑光
    m, nt, b = new_mat("trackpad_glass")
    setp(b, base=srgb("#C4CED6"), metal=0.0, rough=0.42, coat=0.3, coat_rough=0.35, spec=0.6)
    M["trackpad_glass"] = m

    # 扬声器网罩
    m, nt, b = new_mat("speaker_mesh")
    setp(b, base=srgb("#18191B"), metal=0.6, rough=0.55)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 1400.0
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.4
    bp.inputs["Distance"].default_value = 0.0002
    nt.links.new(vor.outputs["Distance"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    M["speaker_mesh"] = m

    m, nt, b = new_mat("taptic")  # 触感引擎金属外壳
    setp(b, base=srgb("#8E9398"), metal=1.0, rough=0.33)
    M["taptic"] = m

    m, nt, b = new_mat("coil")  # 线圈铜
    setp(b, base=srgb("#D9824B"), metal=1.0, rough=0.35)
    M["coil"] = m

    # 电池电芯：黑色缎面铝塑膜 + 白色印字（贴图）
    m, nt, b = new_mat("battery_cell")
    setp(b, base=srgb("#1D1E21"), metal=0.25, rough=0.42, coat=0.2)
    uv = planar_uv(nt, 1.0, 1.0)  # 每个电芯在建模时写 UV，这里先留默认
    M["battery_cell"] = m

    # PCB 由贴图驱动（颜色+金属度+粗糙度）
    for name in ("pcb_main", "pcb_ports", "pcb_audio", "pcb_battery", "pcb_trackpad"):
        m, nt, b = new_mat(name)
        setp(b, base=srgb("#16241D"), metal=0.0, rough=0.32, coat=0.55, coat_rough=0.12)
        M[name] = m

    # 屏幕：壁纸自发光，亮度由 screen_power 驱动
    m, nt, b = new_mat("screen")
    setp(b, base=srgb("#020203"), metal=0.0, rough=0.25, coat=0.25, coat_rough=0.12, spec=0.25)
    v = value_node(nt, "screen_power", 0.0)
    M["screen"] = m

    # 键帽：黑色键帽，字符透光（背光），亮度由 kb_backlight 驱动
    m, nt, b = new_mat("keycap")
    setp(b, base=srgb("#141516"), metal=0.0, rough=0.36, coat=0.15, coat_rough=0.3)
    value_node(nt, "kb_backlight", 0.0)
    M["keycap"] = m

    m, nt, b = new_mat("touchid")  # 触控 ID 键：亮面黑+金属圈
    setp(b, base=srgb("#0C0D0E"), metal=0.0, rough=0.08, coat=1.0, coat_rough=0.03)
    M["touchid"] = m

    # 散热片（铝）+ 热力图发光（heat_glow 驱动）
    m, nt, b = new_mat("heatspreader")
    setp(b, base=srgb("#C9CDD2"), metal=1.0, rough=0.48)
    value_node(nt, "heat_glow", 0.0)
    M["heatspreader"] = m

    # 高亮描边用的自发光（天蓝）
    m, nt, b = new_mat("glow_accent")
    setp(b, base=srgb("#000000"), emit=srgb("#9FD3FF"), emit_str=6.0)
    M["glow_accent"] = m

    m, nt, b = new_mat("led_white")
    setp(b, base=srgb("#000000"), emit=srgb("#FFFFFF"), emit_str=3.0)
    M["led_white"] = m

    return M


# ------------------------------------------------------------------ 贴图材质收尾（需要 layout 尺寸）
def planar_uv_2side(nt, w, d, cx=0.0, cy=0.0, loc=(-1100, 0)):
    """朝上的面正常映射，朝下的面左右镜像——整机绕 Y 轴翻面后从底部看，丝印/标签仍是正的"""
    top = planar_uv(nt, w, d, cx, cy, loc)
    bot = planar_uv(nt, -w, d, cx, cy, (loc[0], loc[1] - 300))
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (loc[0], loc[1] - 600)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (loc[0] + 200, loc[1] - 600)
    nt.links.new(tc.outputs["Normal"], sep.inputs[0])
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.location = (loc[0] + 400, loc[1] - 600)
    nt.links.new(sep.outputs["Z"], gt.inputs[0])
    gt.inputs[1].default_value = 0.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "VECTOR"
    mix.location = (loc[0] + 600, loc[1] - 200)
    nt.links.new(gt.outputs[0], mix.inputs["Factor"])
    nt.links.new(bot, mix.inputs[4])
    nt.links.new(top, mix.inputs[5])
    return mix.outputs[1], gt.outputs[0]


def _pcb_shader(mt, img, img_m, w, d, cx, cy, two_side=True, img_top=None, img_top_m=None):
    nt = mt.node_tree
    b = nt.nodes["Principled BSDF"]
    uv = planar_uv(nt, w, d, cx, cy)
    ext = "EXTEND" if two_side else "REPEAT"
    tn = image_node(nt, img, uv, (-450, 100), extension=ext)
    tm = image_node(nt, img_m, uv, (-450, -200), "Non-Color", extension=ext)
    if tn is None:
        return
    if img_top:
        # 朝上的面用顶面贴图，朝下的面用底面贴图（底面贴图的字已镜像）
        tt = image_node(nt, img_top, uv, (-450, 400), extension=ext)
        ttm = image_node(nt, img_top_m, uv, (-450, 700), "Non-Color", extension=ext)
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Normal"], sep.inputs[0])
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        nt.links.new(sep.outputs["Z"], gt.inputs[0])
        gt.inputs[1].default_value = 0.0
        mc = nt.nodes.new("ShaderNodeMix")
        mc.data_type = "RGBA"
        nt.links.new(gt.outputs[0], mc.inputs["Factor"])
        nt.links.new(tn.outputs["Color"], mc.inputs[6])
        nt.links.new(tt.outputs["Color"], mc.inputs[7])
        mm_ = nt.nodes.new("ShaderNodeMix")
        mm_.data_type = "RGBA"
        nt.links.new(gt.outputs[0], mm_.inputs["Factor"])
        nt.links.new(tm.outputs["Color"], mm_.inputs[6])
        nt.links.new(ttm.outputs["Color"], mm_.inputs[7])

        class _O:  # 伪装成图像节点输出，后面统一连线
            pass
        tn, tm = _O(), _O()
        tn.outputs = {"Color": mc.outputs[2]}
        tm.outputs = {"Color": mm_.outputs[2]}
    nt.links.new(tn.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tm.outputs["Color"], b.inputs["Metallic"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.location = (-150, -250)
    rr.inputs["To Min"].default_value = 0.34
    rr.inputs["To Max"].default_value = 0.2
    nt.links.new(tm.outputs["Color"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    inv = nt.nodes.new("ShaderNodeMapRange")
    inv.location = (-150, -450)
    inv.inputs["To Min"].default_value = 0.6
    inv.inputs["To Max"].default_value = 0.0
    nt.links.new(tm.outputs["Color"], inv.inputs["Value"])
    nt.links.new(inv.outputs["Result"], b.inputs["Coat Weight"])


def finish_materials(M):
    import layout as L
    from keyboard_layout import keys_mm
    MMf = 0.001
    B = L.LB
    _pcb_shader(M["pcb_main"], "pcb_main.png", "pcb_main_metal.png", B["w"] * MMf, B["d"] * MMf, B["cx"] * MMf, B["cy"] * MMf,
                img_top="pcb_main_top.png", img_top_m="pcb_main_top_metal.png")
    for n in ("pcb_ports", "pcb_audio", "pcb_battery", "pcb_trackpad"):
        _pcb_shader(M[n], "pcb_small.png", "pcb_small_metal.png", 0.04, 0.04, 0, 0, two_side=False)

    # 键帽：字符 + 背光
    keys, KW, KH = keys_mm()
    mt = M["keycap"]
    nt = mt.node_tree
    b = nt.nodes["Principled BSDF"]
    uv = planar_uv(nt, KW * MMf, KH * MMf)
    tn = image_node(nt, "kb_legend.png", uv, (-450, 100), "Non-Color")
    if tn:
        mixc = nt.nodes.new("ShaderNodeMix")
        mixc.data_type = "RGBA"
        mixc.location = (-150, 150)
        nt.links.new(tn.outputs["Color"], mixc.inputs["Factor"])
        mixc.inputs[6].default_value = srgb("#151617")
        mixc.inputs[7].default_value = srgb("#D9DCDF")
        nt.links.new(mixc.outputs[2], b.inputs["Base Color"])
        bl = nt.nodes["kb_backlight"]
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.location = (-150, -150)
        nt.links.new(tn.outputs["Color"], mul.inputs[0])
        nt.links.new(bl.outputs[0], mul.inputs[1])
        b.inputs["Emission Color"].default_value = srgb("#EAF2FF")
        nt.links.new(mul.outputs[0], b.inputs["Emission Strength"])

    # 屏幕：壁纸自发光（从正面看是正的：v 朝局部 -y 增加）
    mt = M["screen"]
    nt = mt.node_tree
    b = nt.nodes["Principled BSDF"]
    S = L.SCREEN
    uv = planar_uv(nt, S["w"] * MMf, -S["h"] * MMf)
    tn = image_node(nt, "wallpaper.png", uv, (-450, 100))
    if tn:
        nt.links.new(tn.outputs["Color"], b.inputs["Emission Color"])
        pw = nt.nodes["screen_power"]
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.location = (-150, -100)
        nt.links.new(pw.outputs[0], mul.inputs[0])
        mul.inputs[1].default_value = 2.2
        nt.links.new(mul.outputs[0], b.inputs["Emission Strength"])

    # 散热片热力图：以裸片为中心的径向渐变
    mt = M["heatspreader"]
    nt = mt.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1100, -300)
    vm = nt.nodes.new("ShaderNodeVectorMath")
    vm.operation = "DISTANCE"
    vm.location = (-900, -300)
    nt.links.new(tc.outputs["Object"], vm.inputs[0])
    vm.inputs[1].default_value = (L.DIE["dx"] * MMf, L.DIE["dy"] * MMf, 0.0)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.location = (-700, -300)
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 0.032
    mr.inputs["To Min"].default_value = 1.0
    mr.inputs["To Max"].default_value = 0.0
    nt.links.new(vm.outputs["Value"], mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-500, -300)
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0, 0, 0, 1)
    e = cr.elements.new(0.35)
    e.color = srgb("#B5250E")
    e = cr.elements.new(0.65)
    e.color = srgb("#F07A1A")
    cr.elements[-1].position = 1.0
    cr.elements[-1].color = srgb("#FFE7A8")
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Emission Color"])
    hg = nt.nodes["heat_glow"]
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.location = (-300, -500)
    nt.links.new(mr.outputs["Result"], mul.inputs[0])
    nt.links.new(hg.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], b.inputs["Emission Strength"])

    # 底壳刻字（凹刻：轻微凹凸 + 略亮）——单独复制一份底壳材质，不影响其它铝件
    mt = M["alu_sky"].copy()
    mt.name = "alu_bottom"
    M["alu_bottom"] = mt
    nt = mt.node_tree
    b = nt.nodes["Principled BSDF"]
    uv, is_top = planar_uv_2side(nt, 0.120, 0.030, 0.0, 0.0, (-1500, 600))
    tn = image_node(nt, "bottom_engrave.png", uv, (-700, 500), "Non-Color")
    if tn:
        # 只作用在底面（法线朝 -z）且在底壳附近：用 1-is_top 做遮罩
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.location = (-500, 700)
        inv.inputs[0].default_value = 1.0
        nt.links.new(is_top, inv.inputs[1])
        msk = nt.nodes.new("ShaderNodeMath")
        msk.operation = "MULTIPLY"
        msk.location = (-350, 600)
        nt.links.new(tn.outputs["Color"], msk.inputs[0])
        nt.links.new(inv.outputs[0], msk.inputs[1])
        # 叠加到现有凹凸
        bump_old = [n for n in nt.nodes if n.bl_idname == "ShaderNodeBump"][0]
        bp = nt.nodes.new("ShaderNodeBump")
        bp.location = (-150, 500)
        bp.inputs["Strength"].default_value = 0.25
        bp.inputs["Distance"].default_value = 0.00008
        bp.invert = True
        nt.links.new(msk.outputs[0], bp.inputs["Height"])
        nt.links.new(bump_old.outputs["Normal"], bp.inputs["Normal"])
        nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.location = (-150, 300)
        rr.inputs["To Min"].default_value = 0.34
        rr.inputs["To Max"].default_value = 0.2
        nt.links.new(msk.outputs[0], rr.inputs["Value"])
        nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
