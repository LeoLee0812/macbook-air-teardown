# Blender 建模工具函数：圆角矩形棱柱、倒角、布尔、圆柱、平滑、集合管理
# 单位：米。layout.py 里的尺寸是毫米，用 MM 换算
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

MM = 0.001


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def link(obj, c=None):
    for uc in list(obj.users_collection):
        uc.objects.unlink(obj)
    (c or bpy.context.scene.collection).objects.link(obj)
    return obj


def empty(name, loc=(0, 0, 0), parent=None, c=None, size=0.01):
    o = bpy.data.objects.new(name, None)
    o.empty_display_size = size
    o.location = loc
    link(o, c)
    if parent is not None:
        o.parent = parent
    return o


def rrect_pts(w, d, r, seg=10, cx=0.0, cy=0.0):
    """圆角矩形轮廓点（逆时针），w/d/r 单位米"""
    r = max(0.0, min(r, w / 2 - 1e-6, d / 2 - 1e-6))
    pts = []
    corners = [(w / 2 - r, d / 2 - r, 0), (-w / 2 + r, d / 2 - r, 90), (-w / 2 + r, -d / 2 + r, 180), (w / 2 - r, -d / 2 + r, 270)]
    for (x, y, a0) in corners:
        if r <= 0:
            pts.append((cx + x, cy + y))
            continue
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + x + r * math.cos(a), cy + y + r * math.sin(a)))
    return pts


def mesh_from_bm(name, bm, c=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link(o, c)
    if mat is not None:
        set_mat(o, mat)
    return o


def prism(name, pts, h, z0=0.0, c=None, mat=None):
    """把二维轮廓沿 Z 拉伸成棱柱（底面 z0，顶面 z0+h）"""
    bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z0 + h)) for x, y in pts]
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_from_bm(name, bm, c, mat)


def set_mat(o, mat, slot=None):
    if slot is None:
        o.data.materials.clear()
        o.data.materials.append(mat)
    else:
        while len(o.data.materials) <= slot:
            o.data.materials.append(None)
        o.data.materials[slot] = mat


def add_mat(o, mat):
    o.data.materials.append(mat)
    return len(o.data.materials) - 1


def bevel(o, width, segs=3, angle=40, harden=True, limit="ANGLE"):
    m = o.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segs
    m.limit_method = limit
    if limit == "ANGLE":
        m.angle_limit = math.radians(angle)
    m.harden_normals = harden
    m.miter_outer = "MITER_ARC"
    m.profile = 0.5
    return m


def smooth(o, angle=35):
    """面平滑 + 按角度标硬边（替代旧版 auto smooth）"""
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    for f in bm.faces:
        f.smooth = True
    lim = math.radians(angle)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0) < lim
        else:
            e.smooth = False
    bm.to_mesh(me)
    bm.free()


def rbox(name, w, d, h, r=0.0, loc=(0, 0, 0), c=None, mat=None, bev=0.0, bev_seg=3, seg=10, smooth_angle=35):
    """圆角盒子：w×d 的圆角矩形拉高 h，loc 是底面中心"""
    o = prism(name, rrect_pts(w, d, r, seg), h, 0.0, c, mat)
    o.location = loc
    if bev > 0:
        bevel(o, bev, bev_seg)
    smooth(o, smooth_angle)
    return o


def box(name, w, d, h, loc=(0, 0, 0), c=None, mat=None, bev=0.0, bev_seg=2):
    return rbox(name, w, d, h, 0.0, loc, c, mat, bev, bev_seg)


def cyl(name, rad, h, seg=48, loc=(0, 0, 0), c=None, mat=None, bev=0.0, bev_seg=2, axis="Z"):
    """圆柱，loc 是底面中心；axis 决定朝向"""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=rad, radius2=rad, depth=h)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, h / 2))
    if axis == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-90), 3, "X"))
    o = mesh_from_bm(name, bm, c, mat)
    o.location = loc
    if bev > 0:
        bevel(o, bev, bev_seg)
    smooth(o, 40)
    return o


def apply_mods(o):
    with bpy.context.temp_override(object=o, active_object=o, selected_objects=[o], selected_editable_objects=[o]):
        for m in list(o.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)


def boolean(target, cutter, op="DIFFERENCE", apply=True, solver="EXACT", delete_cutter=True):
    m = target.modifiers.new("Bool", "BOOLEAN")
    m.operation = op
    m.object = cutter
    m.solver = solver
    if apply:
        # 先把目标上已有的修改器（倒角等）留到布尔之后：把布尔挪到第一个再应用
        with bpy.context.temp_override(object=target, active_object=target, selected_objects=[target],
                                       selected_editable_objects=[target]):
            bpy.ops.object.modifier_move_to_index(modifier=m.name, index=0)
            bpy.ops.object.modifier_apply(modifier=m.name)
        if delete_cutter:
            bpy.data.objects.remove(cutter, do_unlink=True)
    return target


def join(objs, name=None):
    objs = [o for o in objs if o is not None]
    if not objs:
        return None
    base = objs[0]
    with bpy.context.temp_override(object=base, active_object=base, selected_objects=objs, selected_editable_objects=objs):
        bpy.ops.object.join()
    if name:
        base.name = name
        base.data.name = name
    return base


def merge_meshes(name, parts, c=None):
    """把多个 (bmesh 生成器) 合成一个网格对象，保留各自材质槽索引"""
    pass


def parent_keep(child, parent):
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = mw


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
