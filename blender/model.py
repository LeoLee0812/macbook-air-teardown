# 程序化建模：13 英寸 MacBook Air 全部零件
# 所有尺寸来自 layout.py（mm），这里换算成米。层级：
#   RIG ─ BASE ─ 顶壳/键盘/触控板/电池/主板/散热片/扬声器/接口板/排线/底壳/螺丝
#       └ LID（原点在铰链轴）─ 外壳/屏幕/刘海摄像头/铰链/显示排线
import math, random
import bpy, bmesh
from mathutils import Vector, Matrix
import layout as L
from lib import (MM, coll, link, empty, rrect_pts, prism, rbox, box, cyl, bevel, smooth, boolean, join, set_mat,
                 add_mat, apply_mods, mesh_from_bm)
from keyboard_layout import keys_mm

P = {}      # 零件 / 装配体 empty：名字 → 对象
ANCH = {}   # 标注锚点 empty：名字 → 对象


def m(v):
    return v * MM


def v3(x, y, z):
    return (x * MM, y * MM, z * MM)


# ------------------------------------------------------------------ bmesh 小工具
def bm_rbox(bm, cx, cy, z0, w, d, h, r=0.0, seg=6, mat_index=0):
    """往已有 bmesh 里加一个圆角盒（单位 mm），返回新建的面"""
    pts = rrect_pts(m(w), m(d), m(r), seg, m(cx), m(cy)) if r > 0 else [
        (m(cx - w / 2), m(cy - d / 2)), (m(cx + w / 2), m(cy - d / 2)), (m(cx + w / 2), m(cy + d / 2)), (m(cx - w / 2), m(cy + d / 2))]
    bot = [bm.verts.new((x, y, m(z0))) for x, y in pts]
    top = [bm.verts.new((x, y, m(z0 + h))) for x, y in pts]
    faces = [bm.faces.new(list(reversed(bot))), bm.faces.new(top)]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((bot[i], bot[j], top[j], top[i])))
    for f in faces:
        f.material_index = mat_index
    return faces


def bm_cyl(bm, cx, cy, z0, r, h, seg=24, mat_index=0, axis="Z"):
    ret = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=m(r), radius2=m(r), depth=m(h))
    vs = ret["verts"]
    bmesh.ops.translate(bm, verts=vs, vec=(0, 0, m(h) / 2))
    if axis == "X":
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-90), 3, "X"))
    bmesh.ops.translate(bm, verts=vs, vec=(m(cx), m(cy), m(z0)))
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mat_index
    return vs


def new_obj(name, bm, c, mats):
    o = mesh_from_bm(name, bm, c)
    for mt in mats:
        o.data.materials.append(mt)
    return o


def ribbon(name, pts, w, t, c, mat, up=(0, 0, 1)):
    """沿折线扫出扁平软排线（单位 mm），pts 是 3D 点列"""
    bm = bmesh.new()
    P3 = [Vector(v3(*p)) for p in pts]
    upv = Vector(up)
    rings = []
    for i, p in enumerate(P3):
        if i == 0:
            d = (P3[1] - P3[0]).normalized()
        elif i == len(P3) - 1:
            d = (P3[-1] - P3[-2]).normalized()
        else:
            d = ((P3[i] - P3[i - 1]).normalized() + (P3[i + 1] - P3[i]).normalized()).normalized()
        side = d.cross(upv)
        if side.length < 1e-6:
            side = Vector((1, 0, 0))
        side.normalize()
        nrm = side.cross(d).normalized()
        hw, ht = m(w) / 2, m(t) / 2
        ring = [bm.verts.new(p + side * hw + nrm * ht), bm.verts.new(p - side * hw + nrm * ht),
                bm.verts.new(p - side * hw - nrm * ht), bm.verts.new(p + side * hw - nrm * ht)]
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = new_obj(name, bm, c, [mat])
    smooth(o, 50)
    return o


def anchor(name, parent, loc_mm):
    """标注锚点：挂在装配体上（loc_mm 是机身坐标），渲染时导出屏幕坐标"""
    e = empty("anc_" + name, (0, 0, 0), c=coll("Anchors"), size=0.003)
    e.parent = parent
    e.location = Vector(v3(*loc_mm)) - parent.location  # 建模时装配体的父级都是单位变换
    ANCH[name] = e
    return e


def assembly(name, parent, c, origin_mm=(0, 0, 0)):
    a = empty("A_" + name, v3(*origin_mm), c=c, size=0.02)
    a.parent = parent
    P[name] = a
    return a


def parent_to(objs, a):
    """挂到装配体下并保持位置（建模时装配体的父级都是单位变换，只需减去装配体原点）"""
    for o in objs:
        o.parent = a
        o.location = o.location - a.location


# ------------------------------------------------------------------ 底壳
def make_bottom_case(M, base, c):
    a = assembly("bottomcase", base, c)
    pts = rrect_pts(m(L.W), m(L.D), m(L.R_CORNER), 14)
    o = prism("bottom_plate", pts, m(L.BOTTOM_T), 0.0, c, M["alu_bottom"])
    bevel(o, m(0.7), 3, 40)
    apply_mods(o)
    add_mat(o, M["alu_inner"])
    for f in o.data.polygons:
        if f.normal.z > 0.9 and f.center.z > m(L.BOTTOM_T) * 0.9:
            f.material_index = 1
    for (x, y) in L.SCREWS_BOTTOM:
        boolean(o, cyl("cut", m(1.45), m(3), loc=v3(x, y, -1)))
    smooth(o, 35)
    objs = [o]
    for i, (x, y) in enumerate(L.FEET):
        objs.append(cyl(f"foot_{i}", m(L.FOOT_R), m(0.9), 48, v3(x, y, -0.85), c, M["rubber"], bev=m(0.35), bev_seg=3))
    # 内侧卡扣（4 个）
    for i, (x, y) in enumerate(L.CLIPS):
        sgn = 1 if y > 0 else -1
        clip = rbox(f"clip_{i}", m(14), m(2.2), m(2.6), m(0.6), v3(x, y - sgn * 2.2, L.BOTTOM_T), c, M["alu_inner"])
        hook = rbox(f"clip_hook_{i}", m(14), m(1.2), m(0.8), m(0.3), v3(x, y - sgn * 1.0, L.BOTTOM_T + 1.8), c, M["alu_inner"])
        objs += [clip, hook]
    # 内侧导热/绝缘贴片
    objs.append(rbox("bottom_graphite", m(64), m(40), m(0.12), m(3), v3(L.SOC["cx"] - 2, L.SOC["cy"], L.BOTTOM_T), c,
                     M["graphite"]))
    objs.append(rbox("bottom_mylar", m(120), m(36), m(0.08), m(2), v3(0, 19.5, L.BOTTOM_T), c, M["mylar_black"]))
    parent_to(objs, a)
    anchor("bottomcase", a, (60, -40, 0))
    anchor("clip", a, (L.CLIPS[1][0], L.CLIPS[1][1] - 2.2, L.BOTTOM_T + 2.6))
    return a


def pentalobe_cutter(r=0.75, depth=0.6):
    pts = []
    for i in range(10):
        ang = math.radians(90 + i * 36)
        rr = r if i % 2 == 0 else r * 0.55
        pts.append((m(rr) * math.cos(ang), m(rr) * math.sin(ang)))
    return prism("pent_cut", pts, m(depth + 0.2), -m(0.2))


def make_screw(name, M, c, kind="P5", head_r=1.35, shaft_r=0.7, length=2.8, mat="steel_dark"):
    """螺丝：头部在 z=0 朝 -z（朝外），螺杆沿 +z"""
    head = cyl(name, m(head_r), m(0.55), 40, (0, 0, -m(0.55)), c, M[mat], bev=m(0.18), bev_seg=3)
    apply_mods(head)
    if kind == "P5":
        cut = pentalobe_cutter(head_r * 0.53, 0.45)
    else:  # Torx Plus：六瓣星
        pts = []
        for i in range(12):
            ang = math.radians(i * 30)
            rr = head_r * 0.42 if i % 2 == 0 else head_r * 0.28
            pts.append((m(rr) * math.cos(ang), m(rr) * math.sin(ang)))
        cut = prism("torx_cut", pts, m(0.65), -m(0.2))
    cut.location.z = -m(0.62)
    boolean(head, cut)
    bm = bmesh.new()
    bm_cyl(bm, 0, 0, 0, shaft_r, length, 20)
    for i in range(int(length / 0.34) - 1):
        bm_cyl(bm, 0, 0, 0.3 + i * 0.34, shaft_r + 0.12, 0.12, 20)
    sh = new_obj(name + "_shaft", bm, c, [M[mat]])
    smooth(sh, 40)
    j = join([head, sh], name)
    smooth(j, 40)
    j["is_screw"] = True   # 拆下的螺丝：平铺/爆炸图里默认不再显示
    return j


def screw_at(name, M, base, c, x, y, z, kind="T", head_r=1.0, flip_up=False, mat="steel_dark", parent=None):
    """在机身坐标 (x,y,z) 放一颗螺丝。默认头朝 -z（从底部拧入），返回它的装配体"""
    a = assembly(name, parent or base, c, (x, y, z))
    if parent is not None:
        a.location = Vector(v3(x, y, z)) - parent.location
    s = make_screw(name + "_mesh", M, c, kind, head_r=head_r, shaft_r=head_r * 0.5, length=1.6, mat=mat)
    s.parent = a
    s.location = (0, 0, 0)
    if flip_up:
        s.rotation_euler = (math.pi, 0, 0)
    return a


def make_bottom_screws(M, base, c):
    out = []
    for i, (x, y) in enumerate(L.SCREWS_BOTTOM):
        a = assembly(f"screw_b{i}", base, c, (x, y, 0.0))
        s = make_screw(f"screw_b{i}_mesh", M, c, "P5")
        s.parent = a
        s.location = (0, 0, 0)
        out.append(a)
    anchor("screw_b0", P["screw_b0"], (L.SCREWS_BOTTOM[0][0], L.SCREWS_BOTTOM[0][1], -0.6))
    anchor("screw_b1", P["screw_b1"], (L.SCREWS_BOTTOM[1][0], L.SCREWS_BOTTOM[1][1], -0.6))
    return out


# ------------------------------------------------------------------ 顶壳（含键盘区、触控板开孔、接口孔、铰链缺口、麦克风）
def _bool_transfer(target, cutter):
    mo = target.modifiers.new("Bool", "BOOLEAN")
    mo.operation = "DIFFERENCE"
    mo.object = cutter
    mo.solver = "EXACT"
    mo.material_mode = "TRANSFER"
    with bpy.context.temp_override(object=target, active_object=target, selected_objects=[target],
                                   selected_editable_objects=[target]):
        bpy.ops.object.modifier_apply(modifier=mo.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def make_top_case(M, base, c):
    pts = rrect_pts(m(L.W), m(L.D), m(L.R_CORNER), 14)
    o = prism("topcase", pts, m(L.BASE_H - L.BOTTOM_T), m(L.BOTTOM_T), c, M["alu_sky"])
    bevel(o, m(1.1), 4, 40)
    apply_mods(o)
    inner = M["alu_inner"]

    def cutter(obj):
        set_mat(obj, inner)
        return obj

    ip = rrect_pts(m(L.W - 2 * L.WALL_T), m(L.D - 2 * L.WALL_T), m(L.R_CORNER - L.WALL_T), 14)
    _bool_transfer(o, cutter(prism("cav", ip, m(L.Z_IN_TOP + 1.0), -m(1.0))))
    keys, KW, KH = keys_mm()
    _bool_transfer(o, cutter(rbox("kbcut", m(KW + 2 * L.KB_WELL_MARGIN), m(KH + 2 * L.KB_WELL_MARGIN), m(4), m(2.2),
                                  v3(0, L.KB_CY, L.BASE_H - 2.0))))
    _bool_transfer(o, cutter(rbox("tpcut", m(L.TP["w"] + 0.6), m(L.TP["d"] + 0.6), m(4), m(L.TP["r"] + 0.3),
                                  v3(L.TP["cx"], L.TP["cy"], L.BASE_H - 2.0))))
    _bool_transfer(o, cutter(rbox("hingecut", m(238), m(17), m(5.5), m(2.5), v3(0, L.D / 2, L.BASE_H - 2.75))))
    xL = -L.W / 2
    pm = L.PORT_MAGSAFE
    _bool_transfer(o, cutter(rbox("ms", m(6), m(pm["w"]), m(pm["h"]), m(1.2), v3(xL, pm["cy"], L.PORT_Z - pm["h"] / 2))))
    for i, pu in enumerate(L.PORT_USBC):
        _bool_transfer(o, cutter(rbox(f"usb{i}", m(6), m(pu["w"]), m(pu["h"]), m(1.45), v3(xL, pu["cy"], L.PORT_Z - pu["h"] / 2))))
    _bool_transfer(o, cutter(cyl("jack", m(L.PORT_JACK["r"]), m(8), 32, v3(L.W / 2 - 4, L.PORT_JACK["cy"], L.PORT_Z), axis="X")))
    smooth(o, 32)
    P["topcase"] = o
    o.parent = base
    # 内侧：键盘背板（黑色，铆钉阵列），从底部打开后能看到
    bm = bmesh.new()
    bm_rbox(bm, 0, L.KB_CY, L.Z_IN_TOP - 0.45, KW + 2, KH + 2, 0.45, 2.0, 4, 0)
    for k in keys:
        if k["w"] > 10:
            for sx in (-0.32, 0.32):
                bm_cyl(bm, k["x"] + k["w"] * sx, k["y"] + L.KB_CY, L.Z_IN_TOP - 0.6, 0.55, 0.16, 10, 1)
    bp = new_obj("kb_backplate", bm, c, [M["mylar_black"], M["steel"]])
    bp.parent = base
    P["kb_backplate"] = bp
    # 键盘排线 + 背光排线（顶壳上预装，连到主板前沿）
    kf = ribbon("kb_flex", [(30, 26, L.Z_IN_TOP - 0.55), (30, 44.0, L.Z_IN_TOP - 0.55), (30, 46.6, L.LB["z0"] + 0.85)],
                10.0, 0.12, c, M["flex_amber"])
    kl = ribbon("kb_light_flex", [(48, 26, L.Z_IN_TOP - 0.6), (48, 44.0, L.Z_IN_TOP - 0.6), (48, 46.6, L.LB["z0"] + 0.85)],
                6.0, 0.12, c, M["flex_black"])
    # 三麦克风阵列（键盘上方靠铰链中部，示意位置）+ 麦克风排线
    bm = bmesh.new()
    for (x, y) in L.MICS:
        bm_rbox(bm, x, y, L.Z_IN_TOP - 0.9, 4.5, 3.5, 0.9, 0.6, 3, 0)
        bm_cyl(bm, x, y, L.Z_IN_TOP - 1.0, 0.8, 0.1, 16, 1)
    mic = new_obj("mics", bm, c, [M["plastic_black"], M["steel"]])
    mf = ribbon("mic_flex", [(L.MICS[0][0], 95.5, L.Z_IN_TOP - 0.95), (L.MICS[-1][0], 95.5, L.Z_IN_TOP - 0.95),
                             (24, 95.5, L.Z_IN_TOP - 0.95), (24, 88.5, L.LB["z0"] + 0.85)], 3.0, 0.1, c, M["flex_amber"])
    for ob in (kf, kl, mic, mf):
        ob.parent = base
    P["topcase_extras"] = [bp, kf, kl, mic, mf]
    anchor("kb_backplate", base, (-60, L.KB_CY, L.Z_IN_TOP - 0.5))
    anchor("mics", base, (L.MICS[1][0], L.MICS[1][1], L.Z_IN_TOP - 1.0))
    anchor("topcase", base, (-120, -60, L.BASE_H))
    return o


# ------------------------------------------------------------------ 键盘
def make_keyboard(M, base, c):
    a = assembly("keyboard", base, c, (0, L.KB_CY, 0))
    keys, KW, KH = keys_mm()
    well = rbox("kb_well", m(KW + 2 * L.KB_WELL_MARGIN - 0.2), m(KH + 2 * L.KB_WELL_MARGIN - 0.2), m(0.3), m(2.0),
                v3(0, L.KB_CY, L.BASE_H - 1.25), c, M["plastic_black"])
    bm = bmesh.new()
    tid = None
    for k in keys:
        if k["kind"] == "t":
            tid = k
            continue
        bm_rbox(bm, k["x"], k["y"], 0.0, k["w"], k["h"], 0.95, 1.55, 5, 0)
    o = new_obj("keyboard_keys", bm, c, [M["keycap"]])
    bevel(o, m(0.32), 2, 40, harden=True)
    smooth(o, 40)
    o.location = v3(0, L.KB_CY, L.BASE_H - 0.98)
    t = rbox("touchid", m(tid["w"]), m(tid["h"]), m(0.95), m(1.55), v3(tid["x"], tid["y"] + L.KB_CY, L.BASE_H - 0.98),
             c, M["touchid"], bev=m(0.32), bev_seg=2)
    ring = rbox("touchid_ring", m(tid["w"] + 0.5), m(tid["h"] + 0.5), m(0.9), m(1.8),
                v3(tid["x"], tid["y"] + L.KB_CY, L.BASE_H - 1.0), c, M["steel"])
    boolean(ring, rbox("cut", m(tid["w"] + 0.05), m(tid["h"] + 0.05), m(2), m(1.6), v3(tid["x"], tid["y"] + L.KB_CY, L.BASE_H - 1.5)))
    parent_to([well, o, t, ring], a)
    P["keys"] = o
    P["touchid"] = t
    P["touchid_xy"] = (tid["x"], tid["y"] + L.KB_CY)
    anchor("touchid", a, (tid["x"], tid["y"] + L.KB_CY, L.BASE_H))
    anchor("keyboard", a, (-40, L.KB_CY + 10, L.BASE_H))
    anchor("fnrow", a, (-60, L.KB_CY + KH / 2 - 9.3, L.BASE_H))
    return a


# ------------------------------------------------------------------ 触控板
def make_trackpad(M, base, c):
    T = L.TP
    a = assembly("trackpad", base, c, (T["cx"], T["cy"], 0))
    glass = rbox("tp_glass", m(T["w"]), m(T["d"]), m(0.9), m(T["r"]), v3(T["cx"], T["cy"], L.BASE_H - 0.9), c,
                 M["trackpad_glass"], bev=m(0.35), bev_seg=3)
    frame = rbox("tp_frame", m(T["w"] - 1.0), m(T["d"] - 1.0), m(0.75), m(T["r"] - 0.5), v3(T["cx"], T["cy"], L.BASE_H - 1.65),
                 c, M["alu_dark"], bev=m(0.2))
    # 钢框上的加强筋
    bm = bmesh.new()
    for i in range(5):
        bm_rbox(bm, T["cx"] - 44 + i * 22, T["cy"] - 18, L.BASE_H - 1.95, 2.0, 30, 0.3, 0.6, 2, 0)
    ribs = new_obj("tp_ribs", bm, c, [M["alu_dark"]])
    # 触感引擎（Taptic Engine）：长条金属壳 + 线圈窗口
    te = rbox("taptic", m(64), m(11), m(2.4), m(2.0), v3(T["cx"], T["cy"] + 14, L.BASE_H - 4.05), c, M["taptic"],
              bev=m(0.35), bev_seg=3)
    bm = bmesh.new()
    for i in range(10):
        bm_rbox(bm, T["cx"] - 18 + i * 4.0, T["cy"] + 14, L.BASE_H - 4.2, 2.6, 8.5, 0.2, 0.6, 3, 0)
    coil = new_obj("taptic_coil", bm, c, [M["coil"]])
    # 4 个铜色块（压力感应相关，用途未公开）
    blocks = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            blocks.append(rbox("tp_block", m(10), m(7), m(0.9), m(1.0),
                               v3(T["cx"] + sx * (T["w"] / 2 - 9), T["cy"] + sy * (T["d"] / 2 - 8), L.BASE_H - 2.55), c,
                               M["copper"]))
    pcb = rbox("tp_pcb", m(36), m(9), m(0.6), m(1.0), v3(T["cx"] - 32, T["cy"] - 24, L.BASE_H - 2.25), c, M["pcb_trackpad"])
    chip = rbox("tp_chip", m(6), m(5), m(0.6), m(0.4), v3(T["cx"] - 32, T["cy"] - 24, L.BASE_H - 2.85), c, M["chip_epoxy"])
    flex = ribbon("tp_flex", [(T["cx"] - 32, T["cy"] - 20, L.BASE_H - 2.5), (-30, T["cy"] + 36, L.BASE_H - 2.5),
                              (-30, -6.0, L.BASE_H - 2.1), (-30, 43.0, L.Z_IN_TOP - 0.15), (-30, 46.6, L.LB["z0"] - 0.25)],
                  6.0, 0.12, c, M["flex_amber"])
    parent_to([glass, frame, ribs, te, coil, pcb, chip, flex] + blocks, a)
    # 10 颗固定螺丝（单独可动画）
    for i, (x, y) in enumerate(L.TP_SCREWS):
        screw_at(f"tps{i}", M, base, c, x, y, L.BASE_H - 2.0, "T", head_r=0.9, mat="steel_dark", parent=a)
    anchor("trackpad", a, (T["cx"] + 30, T["cy"] - 20, L.BASE_H - 1.65))
    anchor("taptic", a, (T["cx"] + 20, T["cy"] + 14, L.BASE_H - 4.05))
    anchor("tp_block", a, (T["cx"] + T["w"] / 2 - 9, T["cy"] - T["d"] / 2 + 8, L.BASE_H - 2.55))
    anchor("tp_glass", a, (T["cx"] - 30, T["cy"] + 10, L.BASE_H))
    return a


# ------------------------------------------------------------------ 电池（4 电芯 Π 形 + 金属托盘）
def battery_mat(M, cdef):
    import materials as MT
    mt, nt, b = MT.new_mat("battery_" + cdef["name"])
    MT.setp(b, base=MT.srgb("#232427"), metal=0.25, rough=0.42, coat=0.25, coat_rough=0.2)
    lw, ld = min(cdef["w"] - 10, 70), min(cdef["d"] - 10, 34)
    uv, is_top = MT.planar_uv_2side(nt, m(lw), m(ld), 0.0, 0.0)
    tn = MT.image_node(nt, "battery_label.png", uv)
    if tn:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        # 标签只在底面中部：贴图外是 CLIP（透明黑），用 alpha 混
        nt.links.new(tn.outputs["Alpha"], mix.inputs["Factor"])
        mix.inputs[6].default_value = MT.srgb("#232427")
        nt.links.new(tn.outputs["Color"], mix.inputs[7])
        mix2 = nt.nodes.new("ShaderNodeMix")
        mix2.data_type = "RGBA"
        nt.links.new(is_top, mix2.inputs["Factor"])
        nt.links.new(mix.outputs[2], mix2.inputs[6])
        mix2.inputs[7].default_value = MT.srgb("#232427")
        nt.links.new(mix2.outputs[2], b.inputs["Base Color"])
    MT.micro_bump(nt, b, scale=300, strength=0.05)
    return mt


def make_battery(M, base, c):
    a = assembly("battery", base, c, (0, -10, 0))
    objs = []
    # 金属托盘（Π 形，贴在顶壳内侧）
    bm = bmesh.new()
    for cd in L.CELLS:
        bm_rbox(bm, cd["cx"], cd["cy"], L.Z_IN_TOP - L.TRAY_T, cd["w"] + 3, cd["d"] + 3, L.TRAY_T, 3.5, 4, 0)
    tray = new_obj("bat_tray", bm, c, [M["alu_dark"]])
    objs.append(tray)
    for cd in L.CELLS:
        z0 = L.Z_IN_TOP - L.TRAY_T - cd["h"]
        cell = rbox(cd["name"], m(cd["w"]), m(cd["d"]), m(cd["h"]), m(3.0), v3(cd["cx"], cd["cy"], z0), c,
                    M["battery_cell"], bev=m(1.3), bev_seg=4)
        cell.data.materials.clear()
        cell.data.materials.append(battery_mat(M, cd))
        objs.append(cell)
        P[cd["name"]] = cell
        anchor(cd["name"], a, (cd["cx"], cd["cy"], z0))
    # 易拉胶：拉片从前沿伸出（每块前角电芯两条，马蹄形回折）
    for i, (x, y) in enumerate(L.PULL_TABS):
        cd = L.CELLS[2] if x < 0 else L.CELLS[3]
        z0 = L.Z_IN_TOP - L.TRAY_T - cd["h"] - 0.12
        zs = L.Z_IN_TOP - 0.08
        strip = rbox(f"adhesive_{i}", m(8), m(70), m(0.06), m(1.5), v3(x, y + 38, zs), c, M["tab_clear"])
        tab = ribbon(f"pulltab_{i}", [(x, y + 3, zs + 0.02), (x, y - 1.5, zs + 0.02), (x, y - 3.0, zs - 1.2),
                                       (x, y - 3.0, z0 + 0.6), (x, y + 6.0, z0 - 0.1)], 9.0, 0.16, c, M["tab_white"])
        ta = assembly(f"pulltab_{i}", a, c, (x, y, zs))
        ta.location = Vector(v3(x, y, zs)) - a.location
        tab.parent = ta
        tab.location = -Vector(v3(x, y, zs))
        strip.parent = ta
        strip.location = Vector(v3(x, y + 38, zs)) - Vector(v3(x, y, zs))
        tab["skip_restore"] = True
        strip["skip_restore"] = True
    anchor("pulltab", a, (L.PULL_TABS[1][0], L.PULL_TABS[1][1] - 4, L.Z_IN_TOP - 5.2))
    # 电池排线（从中部电芯后沿插到主板前沿下方）
    fl = ribbon("bat_flex", [(0, 38.0, L.Z_IN_TOP - 2.0), (0, 43.0, L.Z_IN_TOP - 2.0), (0, 44.5, L.LB["z0"] - 0.6)],
                13.0, 0.15, c, M["flex_amber"])
    objs.append(fl)
    parent_to(objs, a)
    # 电池排线插头（插在主板前沿的电池接口里）
    pa = assembly("batplug", a, c, (0, 46.6, L.LB["z0"] - 0.85))
    pa.location = Vector(v3(0, 46.6, L.LB["z0"] - 0.85)) - a.location
    plug = rbox("bat_plug", m(15), m(4.4), m(0.6), m(0.6), v3(0, 46.6, L.LB["z0"] - 1.45), c, M["plastic_black"], bev=m(0.1))
    plugflex = rbox("bat_plug_flex", m(13), m(2.6), m(0.15), m(0.3), v3(0, 44.6, L.LB["z0"] - 0.75), c, M["flex_amber"])
    for ob in (plug, plugflex):
        ob.parent = pa
        ob.location = ob.location - Vector(v3(0, 46.6, L.LB["z0"] - 0.85))
    # 托盘螺丝 4 颗（挂在电池装配体下，可单独动画）
    for i, (x, y) in enumerate(L.TRAY_SCREWS):
        screw_at(f"trs{i}", M, base, c, x, y, L.Z_IN_TOP - L.TRAY_T - 0.2, "T", head_r=1.1, parent=a)
    anchor("battery", a, (-68.5, 19.5, L.Z_IN_TOP - L.TRAY_T - 4.3))
    anchor("tray_screw", P["trs0"], (L.TRAY_SCREWS[0][0], L.TRAY_SCREWS[0][1], L.Z_IN_TOP - L.TRAY_T - 0.8))
    return a


def make_bat_cover(M, base, c):
    """电池接口小盖板（2 颗螺丝）：拆底壳后第一步先拿掉它、断开电池"""
    B = L.BAT_COVER
    zc = L.LB["z0"] - 1.3
    a = assembly("batcover", base, c, (B["cx"], B["cy"], zc))
    cov = rbox("bat_cover", m(B["w"]), m(B["d"]), m(0.5), m(1.2), v3(B["cx"], B["cy"], zc), c, M["steel"], bev=m(0.15))
    parent_to([cov], a)
    for i, sx in enumerate((-7.5, 7.5)):
        screw_at(f"bcs{i}", M, base, c, B["cx"] + sx, B["cy"], zc, "T", head_r=0.85, parent=a)
    anchor("batcover", a, (B["cx"], B["cy"], zc))
    return a


# ------------------------------------------------------------------ 主板（含 M5、统一内存、闪存、N1、热模块）
def lb_outline():
    B = L.LB
    return rrect_pts(m(B["w"]), m(B["d"]), m(3.0), 6, m(B["cx"]), m(B["cy"]))


def make_logic_board(M, base, c):
    B = L.LB
    a = assembly("logicboard", base, c, (B["cx"], B["cy"], B["z0"]))
    z0, t = B["z0"], B["t"]
    pcb = prism("lb_pcb", lb_outline(), m(t), m(z0), c, M["pcb_main"])
    bevel(pcb, m(0.12), 1, 40)
    for (x, y) in L.LB_SCREWS:
        boolean(pcb, cyl("h", m(1.1), m(3), loc=v3(x, y, z0 - 1)))
    smooth(pcb, 40)
    objs = [pcb]
    zb = z0
    S = L.SOC
    sub = rbox("soc_substrate", m(S["w"]), m(S["d"]), m(0.7), m(1.2), v3(S["cx"], S["cy"], zb - 0.7), c, M["substrate"], bev=m(0.12))
    die = rbox("soc_die", m(L.DIE["w"]), m(L.DIE["d"]), m(0.45), m(0.4), v3(S["cx"] + L.DIE["dx"], S["cy"] + L.DIE["dy"], zb - 1.15),
               c, M["die"], bev=m(0.08))
    objs += [sub, die]
    for i, md in enumerate(L.MEM):
        objs.append(rbox(f"soc_mem{i}", m(md["w"]), m(md["d"]), m(0.8), m(0.5), v3(S["cx"] + md["dx"], S["cy"] + md["dy"], zb - 1.5),
                         c, M["chip_epoxy"], bev=m(0.1)))
    bm = bmesh.new()
    rng = random.Random(5)
    for i in range(70):
        side = rng.randrange(4)
        if side < 2:
            x = S["cx"] + rng.uniform(-S["w"] / 2 + 1.2, S["w"] / 2 - 1.2)
            y = S["cy"] + (S["d"] / 2 - 1.0) * (1 if side == 0 else -1)
        else:
            y = S["cy"] + rng.uniform(-S["d"] / 2 + 1.2, S["d"] / 2 - 1.2)
            x = S["cx"] + (S["w"] / 2 - 1.0) * (1 if side == 2 else -1)
        bm_rbox(bm, x, y, zb - 0.92, 0.6, 0.3, 0.2, 0, 1, 0)
    objs.append(new_obj("soc_caps", bm, c, [M["ceramic"]]))
    P["soc_die"] = die
    for i, nd in enumerate(L.NAND):
        objs.append(rbox(f"nand{i}", m(nd["w"]), m(nd["d"]), m(1.0), m(0.5), v3(nd["cx"], nd["cy"], zb - 1.0), c,
                         M["chip_epoxy"], bev=m(0.1)))
    for i, pd in enumerate(L.PMIC + L.SMALL_CHIPS):
        objs.append(rbox(f"chip{i}", m(pd["w"]), m(pd["d"]), m(0.7), m(0.3), v3(pd["cx"], pd["cy"], zb - 0.7), c,
                         M["chip_epoxy"], bev=m(0.06)))
    for i, sd in enumerate(L.SHIELDS):
        objs.append(rbox(f"shield{i}", m(sd["w"]), m(sd["d"]), m(1.2), m(0.6), v3(sd["cx"], sd["cy"], zb - 1.2), c, M["shield"],
                         bev=m(0.15), bev_seg=2))
    for cd in L.CONNECTORS:
        objs.append(rbox(cd["name"], m(cd["w"]), m(cd["d"]), m(0.8), m(0.3), v3(cd["cx"], cd["cy"], zb - 0.8), c,
                         M["plastic_black"], bev=m(0.08)))
    bm = bmesh.new()
    for (x, y) in L.COAX:
        bm_cyl(bm, x, y, zb - 0.9, 1.0, 0.9, 20)
    objs.append(new_obj("coax_sockets", bm, c, [M["gold"]]))
    objs += scatter_passives(M, c, zb)
    objs += scatter_passives(M, c, z0 + t, top=True)
    bm = bmesh.new()
    for (x, y) in L.LB_SCREWS:
        bm_cyl(bm, x, y, zb - 0.02, 2.0, 0.04, 28)
    objs.append(new_obj("lb_screwpads", bm, c, [M["gold"]]))
    # 热模块：金属散热板压在 SoC/内存上 + 黑色导热胶带（与主板一体，不单独更换）
    H = L.THERMAL
    zt = zb - 1.55
    plate = rbox("thermal_plate", m(H["w"]), m(H["d"]), m(H["t"]), m(4.0), v3(H["cx"], H["cy"], zt - H["t"]), c,
                 M["heatspreader"], bev=m(0.15))
    tape = rbox("thermal_tape", m(H["w"] - 6), m(H["d"] - 6), m(0.06), m(2.5), v3(H["cx"] + 1, H["cy"], zt - H["t"] - 0.06), c,
                M["mylar_black"])
    ears = []
    for sx in (-1, 1):
        e = rbox("thermal_ear", m(8), m(7), m(H["t"]), m(2.5), v3(H["cx"] + sx * (H["w"] / 2 + 2.5), H["cy"] - 12, zt - H["t"]), c,
                 M["heatspreader"])
        ears.append(e)
    objs += [plate, tape] + ears
    P["thermal_plate"] = plate
    parent_to(objs, a)
    for i, (x, y) in enumerate(L.LB_SCREWS):
        screw_at(f"lbs{i}", M, base, c, x, y, zb, "T", head_r=1.05, parent=a)
    anchor("soc", a, (S["cx"] + L.DIE["dx"], S["cy"] + L.DIE["dy"], zb - 1.2))
    anchor("mem", a, (S["cx"] + L.MEM[0]["dx"], S["cy"] + L.MEM[0]["dy"], zb - 1.5))
    anchor("nand", a, (L.NAND[0]["cx"], L.NAND[0]["cy"], zb - 1.0))
    anchor("n1", a, (L.N1["cx"], L.N1["cy"], zb - 1.2))
    anchor("pmic", a, (L.PMIC[1]["cx"], L.PMIC[1]["cy"], zb - 0.7))
    # 热模块锚点挂在散热板上（散热板会单独错开展示，标注要跟着它走）
    e = empty("anc_thermal", (0, 0, 0), c=coll("Anchors"), size=0.003)
    e.parent = plate
    e.location = Vector(v3(H["cx"] - 14, H["cy"] + 10, zt - H["t"])) - (a.location + plate.location)   # 散热板此时已挂在主板装配体下
    ANCH["thermal"] = e
    anchor("logicboard", a, (-60, B["cy"] - 12, zb))
    anchor("lb_connectors", a, (0, 46.6, zb - 0.8))
    return a


def _rect_hits(x, y, w, d, rects, pad=0.6):
    for (cx, cy, rw, rd) in rects:
        if abs(x - cx) < (w + rw) / 2 + pad and abs(y - cy) < (d + rd) / 2 + pad:
            return True
    return False


def scatter_passives(M, c, z, top=False):
    B = L.LB
    S = L.SOC
    chips = [(S["cx"], S["cy"], S["w"], S["d"])]
    chips += [(n["cx"], n["cy"], n["w"], n["d"]) for n in L.NAND]
    chips += [(p["cx"], p["cy"], p["w"], p["d"]) for p in L.PMIC + L.SMALL_CHIPS]
    rects = list(chips)
    rects += [(s["cx"], s["cy"], s["w"], s["d"]) for s in L.SHIELDS]
    rects += [(cd["cx"], cd["cy"], cd["w"], cd["d"]) for cd in L.CONNECTORS]
    rects += [(x, y, 4.5, 4.5) for (x, y) in L.LB_SCREWS]
    rects += [(x, y, 3.0, 3.0) for (x, y) in L.COAX]
    if not top:  # 热模块覆盖区不放
        H = L.THERMAL
        rects.append((H["cx"], H["cy"], H["w"] + 2, H["d"] + 2))
    rng = random.Random(21 if top else 42)
    bms = [bmesh.new(), bmesh.new(), bmesh.new()]
    placed = []
    n_target = 700 if not top else 420
    tries = 0
    while len(placed) < n_target and tries < 40000:
        tries += 1
        if rng.random() < 0.65 and not top:
            r0 = rng.choice(chips[1:] + [(L.N1["cx"], L.N1["cy"], 18, 15)])
            x = r0[0] + rng.uniform(-r0[2] / 2 - 7, r0[2] / 2 + 7)
            y = r0[1] + rng.uniform(-r0[3] / 2 - 7, r0[3] / 2 + 7)
        else:
            x = rng.uniform(B["cx"] - B["w"] / 2 + 3, B["cx"] + B["w"] / 2 - 3)
            y = rng.uniform(B["cy"] - B["d"] / 2 + 3, B["cy"] + B["d"] / 2 - 3)
        kind = rng.random()
        if kind < 0.55:
            w, d, h, mi = 1.0, 0.5, 0.45, 0
        elif kind < 0.85:
            w, d, h, mi = 0.6, 0.3, 0.3, 1
        elif kind < 0.95:
            w, d, h, mi = 1.6, 0.8, 0.8, 0
        else:
            w, d, h, mi = 2.5, 2.0, 1.0, 2
        if rng.random() < 0.5:
            w, d = d, w
        if _rect_hits(x, y, w, d, rects, 0.5) or _rect_hits(x, y, w, d, placed, 0.25):
            continue
        if abs(x - B["cx"]) > B["w"] / 2 - 2 or abs(y - B["cy"]) > B["d"] / 2 - 2:
            continue
        placed.append((x, y, w, d))
        bm_rbox(bms[mi], x, y, z if top else z - h, w, d, h, 0, 1, 0)
    names = ["caps", "res", "ind"]
    mats = [M["ceramic"], M["resistor"], M["plastic_gray"]]
    return [new_obj(f"lb_{names[k]}_{'top' if top else 'bot'}", bms[k], c, [mats[k]]) for k in range(3)]


# ------------------------------------------------------------------ 扬声器 + 天线模块
def make_speakers(M, base, c):
    out = []
    for sd in L.SPEAKERS:
        a = assembly(sd["name"], base, c, (sd["cx"], sd["cy"], 0))
        z0 = L.Z_IN_TOP - sd["h"]
        o = sd["outer"]
        body = rbox(sd["name"] + "_body", m(sd["w"]), m(sd["d"]), m(sd["h"]), m(3.0), v3(sd["cx"], sd["cy"], z0), c,
                    M["plastic_black"], bev=m(0.6), bev_seg=3)
        # 外端银色矩形发声单元
        drv = rbox(sd["name"] + "_driver", m(14), m(10), m(0.5), m(1.0), v3(sd["cx"] + o * (sd["w"] / 2 - 9), sd["cy"], z0 - 0.45),
                   c, M["steel"], bev=m(0.15))
        drv2 = rbox(sd["name"] + "_driver2", m(9), m(6), m(0.3), m(0.8), v3(sd["cx"] + o * (sd["w"] / 2 - 9), sd["cy"], z0 - 0.7),
                    c, M["alu_inner"])
        # 出声口（朝铰链缝）
        grille = rbox(sd["name"] + "_grille", m(sd["w"] - 12), m(2.4), m(2.2), m(0.8), v3(sd["cx"], sd["cy"] + sd["d"] / 2 + 0.5, z0 + 1.4),
                      c, M["speaker_mesh"])
        # 金色天线走线（模块表面）
        bm = bmesh.new()
        x0 = sd["cx"] - o * (sd["w"] / 2 - 4)
        for k in range(6):
            xx = x0 + o * k * 4.2
            bm_rbox(bm, xx, sd["cy"], z0 - 0.04, 0.8, sd["d"] - 4, 0.04, 0.2, 1, 0)
            if k < 5:
                yy = sd["cy"] + (sd["d"] / 2 - 2.4) * (1 if k % 2 == 0 else -1)
                bm_rbox(bm, xx + o * 2.1, yy, z0 - 0.04, 4.2, 0.8, 0.04, 0.2, 1, 0)
        ant = new_obj(sd["name"] + "_antenna", bm, c, [M["gold"]])
        # 同轴线：从模块内端接到主板
        cx_in = sd["cx"] - o * (sd["w"] / 2 - 3)
        sock = L.COAX[0] if o < 0 else L.COAX[1]
        coax = ribbon(sd["name"] + "_coax", [(cx_in, sd["cy"] - 3, z0 - 0.5), (cx_in, sd["cy"] - 6.5, z0 - 0.6),
                                              (sock[0], sock[1] + 2.5, L.LB["z0"] - 1.3), (sock[0], sock[1], L.LB["z0"] - 1.0)],
                      1.1, 1.1, c, M["plastic_black"])
        # 固定螺丝耳
        ear = rbox(sd["name"] + "_ear", m(6), m(6), m(0.6), m(2.0), v3(sd["cx"] - o * (sd["w"] / 2 + 1.5), sd["cy"] - 2, z0), c,
                   M["plastic_black"])
        parent_to([body, drv, drv2, grille, ant, coax, ear], a)
        screw_at(sd["name"] + "_s0", M, base, c, sd["cx"] - o * (sd["w"] / 2 + 1.5), sd["cy"] - 2, z0, "T", head_r=1.0, parent=a)
        screw_at(sd["name"] + "_s1", M, base, c, sd["cx"] + o * 2, sd["cy"] - 4.5, z0, "T", head_r=1.0, parent=a)
        anchor(sd["name"], a, (sd["cx"] + o * (sd["w"] / 2 - 9), sd["cy"], z0 - 0.6))
        anchor(sd["name"] + "_ant", a, (x0 + o * 10, sd["cy"], z0 - 0.05))
        out.append(a)
    return out


# ------------------------------------------------------------------ 铰链盖（两侧）
def make_hinge_covers(M, base, c):
    out = []
    for i, hm in enumerate(L.HINGE_MOUNTS):
        a = assembly(f"hingecover{i}", base, c, (hm["cx"], hm["cy"], 1.0))
        cov = rbox(f"hingecover{i}_plate", m(hm["w"]), m(hm["d"]), m(0.5), m(2.0), v3(hm["cx"], hm["cy"], 1.0), c, M["alu_inner"],
                   bev=m(0.15))
        parent_to([cov], a)
        screw_at(f"hcs{i}", M, base, c, hm["cx"] - 9 * (1 if hm["cx"] > 0 else -1), hm["cy"], 1.0, "T", head_r=0.9, parent=a)
        out.append(a)
    anchor("hingecover", out[0], (L.HINGE_MOUNTS[0]["cx"], L.HINGE_MOUNTS[0]["cy"], 1.0))
    return out


# ------------------------------------------------------------------ 接口：MagSafe 3 板、两块 USB-C 板、音频/传感器排线
def usbc_receptacle(name, M, c, cy, z, xL):
    shell = rbox(name + "_shell", m(7.4), m(8.3), m(2.7), m(1.3), v3(xL + 3.7, cy, z - 1.35), c, M["steel"], bev=m(0.15))
    tongue = rbox(name + "_tongue", m(5.0), m(6.0), m(0.7), m(0.3), v3(xL + 3.0, cy, z - 0.35), c, M["plastic_black"])
    back = rbox(name + "_back", m(1.2), m(8.6), m(3.0), m(1.4), v3(xL + 7.6, cy, z - 1.5), c, M["steel_dark"])
    return [shell, tongue, back]


def make_ports(M, base, c):
    z = L.PORT_Z
    xL = -L.W / 2 + L.WALL_T + 0.1
    out = {}
    # 两块 USB-C 板
    for i, (ub, pu) in enumerate(zip(L.USBC_BOARDS, L.PORT_USBC)):
        a = assembly(f"usbc{i}", base, c, (ub["cx"], ub["cy"], 0))
        pcb = rbox(f"usbc{i}_pcb", m(ub["w"]), m(ub["d"]), m(0.7), m(1.5), v3(ub["cx"] + 1, ub["cy"], z - 2.2), c, M["pcb_ports"])
        chip = rbox(f"usbc{i}_chip", m(4), m(4), m(0.6), m(0.3), v3(ub["cx"] + 5, ub["cy"], z - 2.8), c, M["chip_epoxy"])
        objs = [pcb, chip] + usbc_receptacle(f"usbc{i}", M, c, pu["cy"], z, xL)
        objs.append(ribbon(f"usbc{i}_flex", [(ub["cx"] + 9, ub["cy"] - 1, z - 2.0), (-128, ub["cy"] - 1, z - 2.0),
                                             (-121, L.CONNECTORS[9 + i]["cy"], L.LB["z0"] - 0.25)], 6.0, 0.12, c, M["flex_black"]))
        parent_to(objs, a)
        screw_at(f"ucs{i}", M, base, c, ub["cx"] + 6, ub["cy"] + 3.5, z - 2.2, "T", head_r=0.9, parent=a)
        anchor(f"usbc{i}", a, (-L.W / 2, pu["cy"], z))
        out[f"usbc{i}"] = a
    # MagSafe 3 板（带金属楔块）
    mb, pm = L.MAGSAFE_BOARD, L.PORT_MAGSAFE
    a = assembly("magsafe", base, c, (mb["cx"], mb["cy"], 0))
    pcb = rbox("magsafe_pcb", m(mb["w"]), m(mb["d"]), m(0.7), m(1.5), v3(mb["cx"] + 1, mb["cy"], z - 2.3), c, M["pcb_ports"])
    frame = rbox("magsafe_frame", m(5.0), m(pm["w"]), m(pm["h"]), m(1.2), v3(xL + 2.5, pm["cy"], z - pm["h"] / 2), c, M["magnet"],
                 bev=m(0.12))
    face = rbox("magsafe_face", m(0.4), m(pm["w"] - 1.4), m(pm["h"] - 1.0), m(0.6), v3(xL + 0.25, pm["cy"], z - (pm["h"] - 1.0) / 2),
                c, M["plastic_black"])
    pins = [rbox("magsafe_pin", m(0.5), m(0.9), m(0.9), m(0.4), v3(xL + 0.05, pm["cy"] - 3.0 + k * 1.5, z - 0.45), c, M["gold"])
            for k in range(5)]
    led = rbox("magsafe_led", m(0.3), m(1.2), m(0.6), m(0.2), v3(xL + 0.2, pm["cy"] + 4.6, z - 0.3), c, M["led_white"])
    wedge = rbox("magsafe_wedge", m(9), m(14), m(1.6), m(0.8), v3(mb["cx"] + 6, mb["cy"], z + 1.5), c, M["steel"], bev=m(0.2))
    fl = ribbon("magsafe_flex", [(mb["cx"] + 9, mb["cy"] + 2, z - 2.1), (-128, mb["cy"] + 2, z - 2.1),
                                 (-121, 77.5, L.LB["z0"] - 0.25)], 8.0, 0.12, c, M["flex_black"])
    parent_to([pcb, frame, face, led, wedge, fl] + pins, a)
    screw_at("mss0", M, base, c, mb["cx"] + 6, mb["cy"] + 5, z - 2.3, "T", head_r=0.9, parent=a)
    anchor("magsafe", a, (-L.W / 2, pm["cy"], z))
    anchor("magsafe_wedge", a, (mb["cx"] + 6, mb["cy"], z + 1.5))
    out["magsafe"] = a
    # 音频/传感器排线：耳机孔 + 开合角度传感器，接主板
    a = assembly("audioflex", base, c, (140, L.PORT_JACK["cy"], z))
    jx = L.W / 2 - L.WALL_T
    jack = cyl("jack_body", m(2.5), m(11.5), 36, v3(jx - 12.0, L.PORT_JACK["cy"], z), c, M["plastic_black"], axis="X", bev=m(0.3))
    jring = cyl("jack_ring", m(2.2), m(1.0), 36, v3(jx - 1.0, L.PORT_JACK["cy"], z), c, M["steel"], axis="X")
    boolean(jring, cyl("h", m(1.75), m(3), 32, v3(jx - 2.0, L.PORT_JACK["cy"], z), axis="X"))
    jpcb = rbox("jack_stiffener", m(12), m(7), m(0.5), m(1.0), v3(jx - 7, L.PORT_JACK["cy"], z - 3.0), c, M["pcb_audio"])
    ls = L.LID_SENSOR
    sensor = rbox("lid_sensor", m(6), m(5), m(1.6), m(0.8), v3(ls["cx"], ls["cy"], L.Z_IN_TOP - 2.4), c, M["chip_epoxy"])
    smag = cyl("lid_sensor_mag", m(1.2), m(0.6), 24, v3(ls["cx"], ls["cy"], L.Z_IN_TOP - 3.0), c, M["magnet"])
    afl = ribbon("audio_flex", [(jx - 7, L.PORT_JACK["cy"] - 3, z - 2.8), (ls["cx"], 90.5, z - 2.8),
                                (ls["cx"], ls["cy"] - 2.5, L.Z_IN_TOP - 2.6)], 5.0, 0.12, c, M["flex_amber"])
    afl2 = ribbon("audio_flex2", [(jx - 9, L.PORT_JACK["cy"] - 3.5, z - 2.8), (128, 86.5 + 2.5, z - 2.8),
                                  (128, 86.5, L.LB["z0"] - 0.25)], 5.0, 0.12, c, M["flex_amber"])
    parent_to([jack, jring, jpcb, sensor, smag, afl, afl2], a)
    anchor("jack", a, (L.W / 2, L.PORT_JACK["cy"], z))
    anchor("lid_sensor", a, (ls["cx"], ls["cy"], L.Z_IN_TOP - 2.4))
    out["audioflex"] = a
    return out


def make_touchid_board(M, base, c):
    T = L.TOUCHID_BOARD
    zt = L.LB["z0"] + L.LB["t"] + 0.9
    a = assembly("touchidboard", base, c, (T["cx"], T["cy"], zt))
    pcb = rbox("tid_pcb", m(T["w"]), m(T["d"]), m(0.6), m(1.2), v3(T["cx"], T["cy"], zt), c, M["pcb_battery"])
    chip = rbox("tid_chip", m(5), m(5), m(0.6), m(0.4), v3(T["cx"] - 3, T["cy"], zt - 0.6), c, M["chip_epoxy"])
    fl = ribbon("tid_flex", [(T["cx"] + 2, T["cy"] - 5, zt + 0.3), (T["cx"] + 2, T["cy"] - 12, zt + 0.3),
                             (T["cx"] + 2, T["cy"] - 14, L.LB["z0"] + L.LB["t"] + 0.1)], 4.0, 0.1, c, M["flex_black"])
    parent_to([pcb, chip, fl], a)
    anchor("touchidboard", a, (T["cx"], T["cy"], zt))
    return a


# ------------------------------------------------------------------ 屏幕总成
def anchor_l(name, parent, loc_mm):
    e = empty("anc_" + name, v3(*loc_mm), parent=parent, c=coll("Anchors"), size=0.003)
    ANCH[name] = e
    return e


def make_lid(M, rig, c):
    lid = empty("LID", v3(0, L.HINGE_Y, L.HINGE_Z), c=c, size=0.03)
    lid.parent = rig
    P["lid"] = lid
    y_far = -(L.D / 2 + L.HINGE_Y)
    y_near = L.D / 2 - L.HINGE_Y
    cy = (y_far + y_near) / 2
    z0 = L.LID_GAP
    shell = prism("lid_shell", rrect_pts(m(L.W), m(L.D), m(L.R_CORNER), 14, 0.0, m(cy)), m(L.LID_H), m(z0), c, M["alu_sky"])
    bevel(shell, m(1.0), 4, 40)
    apply_mods(shell)
    cav = prism("cav", rrect_pts(m(L.W - 2.0), m(L.D - 2.0), m(L.R_CORNER - 1.0), 14, 0.0, m(cy)), m(L.LID_H - 0.75 + 1.0), m(z0 - 1.0))
    set_mat(cav, M["alu_inner"])
    _bool_transfer(shell, cav)
    smooth(shell, 32)
    S = L.SCREEN
    glass = rbox("disp_glass", m(L.W - 2.2), m(L.D - 2.2), m(0.55), m(L.R_CORNER - 1.1), v3(0, cy, z0 + 0.05), c, M["glass_black"],
                 bev=m(0.15))
    top_edge = y_far + 1.1 + 6.2
    scy = top_edge + S["h"] / 2
    scr = rbox("screen", m(S["w"]), m(S["h"]), m(0.02), m(4.0), v3(0, scy, z0 + 0.02), c, M["screen"])
    boolean(scr, rbox("notchcut", m(L.NOTCH["w"]), m(L.NOTCH["h"] * 2), m(1), m(3.0), v3(0, top_edge, z0 - 0.5)))
    lens = cyl("cam_lens", m(L.CAM["r"]), m(0.08), 40, v3(0, top_edge - 2.6, z0), c, M["lens"])
    lring = cyl("cam_ring", m(L.CAM["r"] + 0.5), m(0.06), 40, v3(0, top_edge - 2.6, z0 + 0.005), c, M["lens_ring"])
    als = cyl("cam_als", m(0.45), m(0.06), 24, v3(5.0, top_edge - 2.6, z0 + 0.005), c, M["lens"])
    cammod = rbox("cam_module", m(16), m(6), m(1.6), m(1.0), v3(0, top_edge - 2.8, z0 + 0.65), c, M["plastic_black"])
    camflex = ribbon("cam_flex", [(8, top_edge - 2.8, z0 + 1.6), (8, -14, z0 + 2.7), (8, -2, 0.4), (8, 3.0, -2.6)],
                     4.0, 0.1, c, M["flex_amber"])
    lcd = rbox("disp_lcd", m(S["w"] + 4), m(S["h"] + 4), m(0.5), m(4), v3(0, scy, z0 + 0.62), c, M["glass_black"])
    bl_diff = rbox("disp_diffuser", m(S["w"] + 4), m(S["h"] + 4), m(0.2), m(4), v3(0, scy, z0 + 1.14), c, M["white_print"])
    bl_guide = rbox("disp_lightguide", m(S["w"] + 4), m(S["h"] + 4), m(0.6), m(4), v3(0, scy, z0 + 1.36), c, M["tab_clear"])
    bl_refl = rbox("disp_reflector", m(S["w"] + 4), m(S["h"] + 4), m(0.12), m(4), v3(0, scy, z0 + 1.98), c, M["steel"])
    led_strip = rbox("disp_ledstrip", m(S["w"]), m(2.2), m(0.6), m(0.5), v3(0, scy + S["h"] / 2 + 3.0, z0 + 1.36), c, M["led_white"])
    backplate = rbox("disp_backplate", m(S["w"] + 6), m(S["h"] + 8), m(0.3), m(4), v3(0, scy - 1, z0 + 2.15), c, M["steel"])
    # 铰链：整条离合式转轴罩 + 两端铰链臂
    barrel = cyl("hinge_barrel", m(2.6), m(236), 48, v3(-118, 0, 0), c, M["alu_dark"], axis="X", bev=m(0.4))
    arms = [rbox("hinge_arm", m(22), m(16), m(1.4), m(2.0), v3(sx * 131, -9.0, z0 + 2.3), c, M["alu_dark"]) for sx in (-1, 1)]
    dflex = ribbon("display_flex", [(-10, -16, z0 + 2.6), (-10, -2, 0.5), (-10, 3.0, -2.6)], 12.0, 0.12, c, M["flex_black"])
    parts = [shell, glass, scr, lens, lring, als, cammod, camflex, lcd, bl_diff, bl_guide, bl_refl, led_strip, backplate, barrel,
             dflex] + arms
    for o in parts:
        o.parent = lid
    for k, o in (("lid_shell", shell), ("disp_glass", glass), ("screen", scr), ("disp_lcd", lcd), ("disp_diffuser", bl_diff),
                 ("disp_lightguide", bl_guide), ("disp_reflector", bl_refl), ("disp_ledstrip", led_strip),
                 ("disp_backplate", backplate), ("cam_module", cammod), ("hinge_barrel", barrel)):
        P[k] = o
    P["lid_cam_parts"] = [lens, lring, als]
    anchor_l("camera", lid, (0, top_edge - 2.6, z0))
    anchor_l("screen", lid, (70, scy - 30, z0))
    anchor_l("hinge", lid, (110, 0, 0))
    anchor_l("backlight", lid, (S["w"] / 2 - 20, scy + S["h"] / 2 + 3, z0 + 1.4))
    anchor_l("lcd", lid, (-S["w"] / 2 + 30, scy, z0 + 0.62))
    return lid


def make_hinge_mounts(M, base, c):
    """铰链在底座一侧的固定座（6 颗 8IP 螺丝，随屏幕一起拆下）"""
    a = assembly("hingemounts", base, c, (0, L.HINGE_MOUNTS[0]["cy"], 4.5))
    objs = []
    for hm in L.HINGE_MOUNTS:
        objs.append(rbox("hinge_mount", m(hm["w"]), m(hm["d"]), m(1.4), m(2.0), v3(hm["cx"], hm["cy"], 4.6), c, M["alu_dark"],
                         bev=m(0.2)))
    parent_to(objs, a)
    for i, hm in enumerate(L.HINGE_MOUNTS):
        for k, dx in enumerate((-9, 0, 9)):
            screw_at(f"hms{i}{k}", M, base, c, hm["cx"] + dx, hm["cy"] - 2.5, 4.6, "T", head_r=1.2, parent=a)
    return a


# ------------------------------------------------------------------ 总装
def build(M):
    c = coll("MBA")
    rig = empty("RIG", (0, 0, 0), c=c, size=0.05)
    base = empty("BASE", (0, 0, 0), c=c, size=0.04)
    base.parent = rig
    P["rig"], P["base"] = rig, base
    make_top_case(M, base, c)
    make_keyboard(M, base, c)
    make_trackpad(M, base, c)
    make_battery(M, base, c)
    make_bat_cover(M, base, c)
    make_logic_board(M, base, c)
    make_touchid_board(M, base, c)
    make_speakers(M, base, c)
    make_hinge_covers(M, base, c)
    make_hinge_mounts(M, base, c)
    make_ports(M, base, c)
    make_bottom_case(M, base, c)
    make_bottom_screws(M, base, c)
    make_lid(M, rig, c)
    return P, ANCH
