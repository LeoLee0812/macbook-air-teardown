# 拆解动画编排：13 个镜头，全部卡在配乐的小节线上（music/sections.json）
# 顺序按 Apple 官方 M5 维修手册：底壳 → 断开电池 → 电池 → 触控板 → 雷雳接口板 → MagSafe 3 → 扬声器与天线
#   → 主板 → 触控 ID 与耳机孔 → 显示屏 → 剩下顶壳与键盘 → 全部零件平铺 → 爆炸图 → 合体
import math, json, os
import bpy
from mathutils import Vector
import layout as L
from tl import Timeline, CamRig, bar as b, BEAT, BAR, F, FPS, SEC

HERE = os.path.dirname(os.path.abspath(__file__))
PI = math.pi
MMf = 0.001
REST = {}
TL = None


def rest(o):
    if o not in REST:
        REST[o] = (o.location.copy(), Vector(o.rotation_euler[:]), o.scale.copy())
    return REST[o]


def KL(o, t, off=(0, 0, 0), ease="bez"):
    """位置关键帧：off 是相对静止位置的局部偏移（米）"""
    l0 = rest(o)[0]
    TL.set(o, "location", t, tuple(l0 + Vector(off)), ease)


def KR(o, t, rot=(0, 0, 0), ease="bez"):
    r0 = rest(o)[1]
    TL.set(o, "rotation_euler", t, tuple(r0 + Vector(rot)), ease)


def KS(o, t, s=(1, 1, 1), ease="bez"):
    TL.set(o, "scale", t, tuple(s), ease)


def fw(dx=0.0, dy=0.0, dz=0.0):
    """翻面状态下：世界坐标位移 → 底座局部位移（绕 Y 轴翻面：x、z 取反）"""
    return (-dx, dy, -dz)


def meshes(o):
    return [x for x in [o] + list(o.children_recursive) if x.type == "MESH"]


def vis(o, t, on, force=False):
    """显隐关键帧。重新显示整件时，默认跳过已拆掉的螺丝和易拉胶（force=True 才显示）"""
    for x in meshes(o):
        if on and not force and (x.get("is_screw") or x.get("skip_restore")):
            continue
        TL.set(x, "hide_render", t, 0.0 if on else 1.0, "const")


def unscrew(s, t, turns=3, back=0.0032, dur=0.8):
    """螺丝逆时针拧出（翻面时从上往下看）并退出 back 米"""
    KR(s, t, (0, 0, 0), "cubic")
    KR(s, t + dur, (0, 0, -2 * PI * turns))
    KL(s, t, (0, 0, 0), "cubic")
    KL(s, t + dur, (0, 0, -back))


def fly(o, t0, t1, off0, off1, rot0=None, rot1=None, ease="cubic_in", hide=True):
    KL(o, t0, off0, ease)
    KL(o, t1, off1)
    if rot0 is not None:
        KR(o, t0, rot0, ease)
        KR(o, t1, rot1)
    if hide:
        vis(o, t1 + 1.0 / FPS, False)


def value_socket(mat, name):
    return mat.node_tree.nodes[name].outputs[0]


# ------------------------------------------------------------------ 叠加层数据（字幕/标注/章节卡），导出给 HyperFrames
OVER = {"chapters": [], "callouts": [], "texts": [], "knoll": [], "explode": []}


def chapter(num, cn, en, t0, t1):
    OVER["chapters"].append(dict(num=num, cn=cn, en=en, t0=round(t0, 3), t1=round(t1, 3)))


def callout(anchor, t0, t1, title, sub="", dx=180, dy=-110):
    OVER["callouts"].append(dict(anchor=anchor, t0=round(t0, 3), t1=round(t1, 3), title=title, sub=sub, dx=dx, dy=dy))


def text(kind, t0, t1, main, sub="", pos="left"):
    OVER["texts"].append(dict(kind=kind, t0=round(t0, 3), t1=round(t1, 3), main=main, sub=sub, pos=pos))


def build(P, ANCH, cam, tgt, LIGHTS, M):
    global TL
    TL = Timeline()
    sc = bpy.context.scene
    END = SEC["duration"]
    sc.frame_start = 0
    sc.frame_end = F(END) - 1
    try:
        sc.render.motion_blur_position = "START"
    except Exception:  # noqa: BLE001
        pass
    cr = CamRig(TL, cam, tgt)
    rig, base, lid = P["rig"], P["base"], P["lid"]
    O = bpy.data.objects

    # 所有会动的东西先在第 0 帧记下静止位姿
    movers = [rig, base, lid] + [v for k, v in P.items() if isinstance(v, bpy.types.Object) and v.name.startswith("A_")]
    for o in movers:
        KL(o, 0.0, (0, 0, 0), "bez")
        KR(o, 0.0, (0, 0, 0), "bez")
    for o in movers:
        if o is not rig and o is not base:
            vis(o, 0.0, True, force=True)

    # ---------------------------------------------------------------- 灯光
    E0 = {k: LIGHTS[k].data.energy for k in LIGHTS}
    from stage import area_light
    sweep = area_light("L_sweep", (-0.5, -0.05, 0.22), (-0.5, -0.05, 0.0), 0.012, 0.7, 0.0, "#FFFFFF")
    sweep.rotation_euler = (0, 0, 0)
    for k, lo in LIGHTS.items():
        TL.set(lo.data, "energy", 0.0, 0.0, "const")
        TL.set(lo.data, "energy", b(2) - 0.05, 0.0, "quart_out")
        TL.set(lo.data, "energy", b(2) + 0.7, E0[k], "bez")
    TL.set(sweep.data, "energy", 0.0, 0.0, "sine")
    TL.set(sweep.data, "energy", 0.5, 26.0, "bez")
    TL.set(sweep.data, "energy", b(2) + 0.2, 26.0, "quart_out")
    TL.set(sweep.data, "energy", b(2) + 1.0, 0.0, "const")
    TL.set(sweep, "location", 0.0, (-0.42, -0.05, 0.20), "sine")
    TL.set(sweep, "location", b(2) + 0.2, (0.42, -0.05, 0.20), "const")
    # 片尾第二记重音：再扫一道光
    hit2 = SEC["hits"][2]
    TL.set(sweep, "location", hit2 - 0.05, (-0.40, -0.05, 0.20), "cubic")
    TL.set(sweep.data, "energy", hit2 - 0.05, 0.0, "quart_out")
    TL.set(sweep.data, "energy", hit2 + 0.15, 30.0, "sine")
    TL.set(sweep, "location", hit2 + 1.4, (0.40, -0.05, 0.20), "const")
    TL.set(sweep.data, "energy", hit2 + 1.4, 0.0, "const")

    # ================================================================ A 冷开场  0 → B2
    cr.cut(0.0, (-0.30, -0.30, 0.05), (-0.05, -0.06, 0.004), lens=60, fstop=5.6)
    cr.move(0.0, b(2) - 1 / FPS, (-0.18, -0.36, 0.06), (0.02, -0.07, 0.004), ease="sine")

    # ================================================================ B 标题  B2 → B7
    cr.cut(b(2), (0.40, -0.44, 0.24), (0.0, 0.0, 0.004), lens=50, fstop=5.6)
    cr.move(b(2), b(5), (0.10, -0.56, 0.19), (0.0, 0.0, 0.004), ease="sine", arc=True)
    cr.move(b(5), b(7) - 1 / FPS, (0.52, -0.36, 0.03), (0.0, -0.02, 0.005), lens=90, fstop=8.0, ease="sine")
    text("title", b(2) + 0.25, b(5) - 0.2, "拆开一台 MacBook Air", "13 英寸 · M5", "left")
    text("stat", b(5) + 0.4, b(7) - 0.15, "1.13 cm", "厚度 · 重 1.23 kg", "right")

    # ================================================================ C 翻面 + 拧螺丝  B7 → B12
    cr.cut(b(7), (0.0, -0.40, 0.26), (0.0, 0.0, 0.0), lens=45, fstop=8)
    cr.move(b(7), b(8.3), (0.04, -0.31, 0.33), (0.0, 0.004, 0.0), ease="cubic")
    sw = (0.132, 0.089, 0.0)   # 第一颗（机身左后角，翻面后在画面右上）
    cr.move(b(8.3), b(8.9), (0.18, 0.02, 0.07), sw, lens=70, fstop=4.0, ease="cubic")
    cr.move(b(8.9), b(9.6), (0.175, 0.025, 0.068), sw, ease="sine")
    cr.move(b(9.6), b(10.4), (0.03, -0.29, 0.31), (0.0, 0.006, 0.0), lens=45, fstop=8, ease="cubic")
    cr.move(b(10.4), b(12), (0.03, -0.27, 0.30), (0.0, 0.006, 0.0), ease="sine")
    t_f0, t_f1 = b(7) + 0.15, b(8) + 0.35
    KR(rig, t_f0, (0, 0, 0), "quart")
    KR(rig, t_f1, (0, PI, 0), "bez")
    KL(rig, t_f0, (0, 0, 0), "sine")
    KL(rig, (t_f0 + t_f1) / 2, (0, 0, 0.03), "sine")
    KL(rig, t_f1, (0, 0, 0), "bez")
    order = [0, 1, 3, 2]
    for k, i in enumerate(order):
        s = P[f"screw_b{i}"]
        ts = b(8.6) + k * 2 * BEAT
        unscrew(s, ts, turns=3, back=0.0034, dur=0.85)
        fly(s, b(11) + k * 0.07, b(11) + 0.75 + k * 0.07, fw(dz=0.0034), fw(dy=0.05, dz=0.30), ease="expo_in")
    chapter("01", "底壳", "BOTTOM CASE", b(8), b(16))
    callout("screw_b0", b(8.75), b(9.55), "五角螺丝", "P5 · 前后角各 2 颗", dx=-260, dy=-130)
    text("note", b(9.6), b(11.8), "内侧还有 4 个卡扣", "用吸盘拉起底壳，抬起不超过 1 cm", "left")
    # 底壳：预抬 → 掀开（贝斯进入的那一拍）→ 飞走
    bc = P["bottomcase"]
    KR(bc, b(11.5), (0, 0, 0), "quad_out")
    KR(bc, b(11.5) + 0.3, (0.01, 0, 0), "cubic")
    KR(bc, b(12), (0.01, 0, 0), "quart_out")
    KR(bc, b(12) + 0.45, (0, 0, 0), "bez")
    KL(bc, b(12), (0, 0, 0), "quart_out")
    KL(bc, b(12) + 0.45, fw(dz=0.03), "bez")
    fly(bc, b(12.75), b(13.5), fw(dz=0.03), fw(dy=0.10, dz=0.45), (0, 0, 0), (-0.5, 0, 0), ease="cubic_in")

    # ================================================================ D 内部一览 + 断开电池  B12 → B16
    cr.move(b(12), b(13), (0.0, -0.25, 0.40), (0.0, 0.0, -0.003), lens=40, fstop=8, ease="cubic")
    cr.move(b(13), b(14), (0.0, -0.24, 0.39), (0.0, 0.002, -0.003), ease="sine")
    cr.move(b(14), b(14.6), (0.0, -0.035, 0.12), (0.0, 0.047, -0.002), lens=55, fstop=4.0, ease="cubic")
    cr.move(b(14.6), b(16), (0.012, -0.030, 0.115), (0.0, 0.046, -0.002), ease="sine")
    over = [("battery", "电池", -260, 90), ("logicboard", "主板", -230, -120), ("trackpad", "触控板", 220, 110),
            ("speaker_R_ant", "扬声器 + 天线", -200, -130), ("usbc0", "雷雳 4 接口", 200, 60),
            ("magsafe", "MagSafe 3", 200, -110)]
    for k, (an, ti, dx, dy) in enumerate(over):
        callout(an, b(13) + k * BEAT / 2, b(14) - 0.05, ti, "", dx=dx, dy=dy)
    text("note", b(12) + 0.3, b(13) - 0.1, "打开底壳", "", "center")
    cov = P["batcover"]
    for k in range(2):
        s = P[f"bcs{k}"]
        unscrew(s, b(14.6) + k * 0.3, turns=2, back=0.0025, dur=0.55)
        fly(s, b(15.1) + k * 0.05, b(15.6) + k * 0.05, fw(dz=0.0025), fw(dz=0.12), ease="expo_in")
    fly(cov, b(15.15), b(15.75), (0, 0, 0), fw(dy=0.03, dz=0.14), ease="cubic_in")
    plug = P["batplug"]
    KL(plug, b(15.6), (0, 0, 0), "back_out")
    KL(plug, b(15.95), fw(dz=0.0028), "bez")
    callout("batcover", b(14.6), b(16) - 0.1, "第一步：断开电池", "拆下盖板（2 颗螺丝），拔掉电池排线", dx=230, dy=-120)

    # ================================================================ E 电池  B16 → B21
    cr.move(b(16), b(16.8), (0.0, -0.31, 0.21), (0.0, -0.025, -0.003), lens=40, fstop=8, ease="cubic")
    cr.move(b(16.8), b(18.8), (0.03, -0.30, 0.20), (0.0, -0.028, -0.003), ease="sine")
    chapter("02", "电池", "BATTERY", b(16), b(21))
    for k in range(4):
        ta = P[f"pulltab_{k}"]
        tp = b(16.8) + k * BEAT / 2
        fly(ta, tp, tp + 0.9, (0, 0, 0), fw(dy=-0.09, dz=0.014), ease="cubic")
    callout("pulltab", b(16.85), b(18.6), "易拉胶 ×4", "拉片在前沿，抽出即松开", dx=-240, dy=-150)
    for k in range(4):
        s = P[f"trs{k}"]
        ts = b(18) + k * 0.12
        unscrew(s, ts, turns=2, back=0.0028, dur=0.5)
        fly(s, ts + 0.55, ts + 1.0, fw(dz=0.0028), fw(dz=0.20), ease="expo_in")
    callout("tray_screw", b(18), b(18.8), "托盘螺丝 ×4", "", dx=200, dy=-100)
    bat = P["battery"]
    KL(bat, b(18.8), (0, 0, 0), "quart_out")
    KL(bat, b(19.5), fw(dz=0.045), "bez")
    KR(bat, b(18.8), (0, 0, 0), "sine")
    KR(bat, b(20.6), (-0.30, 0.0, 0.10), "bez")
    cr.move(b(18.8), b(20.6), (0.05, -0.32, 0.27), (0.0, -0.025, 0.035), ease="sine")
    callout("cell_WL", b(19.3), b(20.7), "4 块电芯 · Π 形排布", "粘在金属托盘上，整件更换", dx=-250, dy=-140)
    text("stat", b(19.0), b(20.8), "53.8 Wh", "锂聚合物电池 · 最长 18 小时", "right")
    fly(bat, b(20.6), b(21) - 0.03, fw(dz=0.045), fw(dy=0.05, dz=0.5), (-0.30, 0, 0.10), (-0.30, 0, 0.10), ease="cubic_in")

    # ================================================================ F 触控板  B21 → B24
    cr.move(b(21), b(21) + 0.5, (0.0, -0.21, 0.17), (0.0, -0.062, -0.003), lens=45, fstop=6.3, ease="cubic")
    cr.move(b(21) + 0.5, b(24) - 1 / FPS, (-0.03, -0.20, 0.16), (0.0, -0.062, 0.012), ease="sine")
    chapter("03", "触控板", "FORCE TOUCH TRACKPAD", b(21), b(24))
    for k in range(10):
        s = P[f"tps{k}"]
        ts = b(21.25) + k * BEAT / 2
        unscrew(s, ts, turns=2, back=0.0022, dur=0.35)
        fly(s, b(22.25) + k * 0.025, b(22.25) + 0.5 + k * 0.025, fw(dz=0.0022), fw(dz=0.15), ease="expo_in")
    text("note", b(21.3), b(22.4), "10 颗螺丝固定", "", "left")
    tp = P["trackpad"]
    KL(tp, b(22.25), (0, 0, 0), "quart_out")
    KL(tp, b(22.8), fw(dz=0.035), "bez")
    KR(tp, b(22.25), (0, 0, 0), "sine")
    KR(tp, b(23.6), (0.22, 0.0, 0.10), "bez")
    te, coil = O["taptic"], O["taptic_coil"]
    for k in range(5):
        tk = b(22.75) + k * BEAT
        for ob in (te, coil):
            KL(ob, tk - 0.02, (0, 0, 0), "quad_out")
            KL(ob, tk + 0.05, (0, 0, -0.0007), "quad")
            KL(ob, tk + 0.2, (0, 0, 0), "bez")
    callout("taptic", b(22.8), b(23.85), "触感引擎", "Taptic Engine · 模拟按压的反馈", dx=230, dy=-120)
    callout("tp_block", b(23.0), b(23.85), "压力感应", "Force Touch：按多重都知道", dx=-240, dy=110)
    fly(tp, b(23.8), b(24) - 0.03, fw(dz=0.035), fw(dy=-0.08, dz=0.40), (0.22, 0, 0.10), (0.22, 0, 0.10), ease="cubic_in")

    # ================================================================ G 雷雳 4 接口板  B24 → B26
    cr.move(b(24), b(24) + 0.45, (0.27, -0.03, 0.15), (0.14, 0.056, 0.004), lens=55, fstop=5.6, ease="cubic")
    cr.move(b(24) + 0.45, b(26), (0.265, -0.02, 0.145), (0.145, 0.058, 0.018), ease="sine")
    chapter("04", "雷雳 4 接口板", "THUNDERBOLT 4 · USB-C", b(24), b(26))
    for k in range(2):
        s = P[f"ucs{k}"]
        unscrew(s, b(24.2) + k * 0.25, turns=2, back=0.0022, dur=0.35)
        fly(s, b(24.2) + 0.4 + k * 0.25, b(24.2) + 0.8 + k * 0.25, fw(dz=0.0022), fw(dz=0.15), ease="expo_in")
        u = P[f"usbc{k}"]
        t0 = b(24.5) + k * BEAT
        KL(u, t0, (0, 0, 0), "quart_out")
        KL(u, t0 + 0.45, fw(dx=0.018, dz=0.018 + 0.006 * k), "bez")
        KR(u, t0, (0, 0, 0), "sine")
        KR(u, t0 + 1.2, (0.0, 0.35, 0.0), "bez")
        fly(u, b(25.7) + k * 0.06, b(26) - 0.02, fw(dx=0.018, dz=0.018 + 0.006 * k), fw(dx=0.05, dz=0.30), (0, 0.35, 0),
            (0, 0.35, 0), ease="cubic_in")
    callout("usbc0", b(24.65), b(25.9), "雷雳 4 接口 ×2", "40Gb/s · 每个口一块独立小板", dx=-250, dy=-120)

    # ================================================================ H 铰链盖 + MagSafe 3  B26 → B27
    cr.move(b(26), b(26) + 0.4, (0.26, 0.0, 0.15), (0.14, 0.082, 0.006), ease="cubic")
    cr.move(b(26) + 0.4, b(27), (0.255, 0.005, 0.145), (0.145, 0.08, 0.016), ease="sine")
    chapter("05", "MagSafe 3", "MAGSAFE 3 BOARD", b(26), b(27))
    for i in range(2):
        s = P[f"hcs{i}"]
        unscrew(s, b(26) + i * 0.1, turns=2, back=0.002, dur=0.28)
        fly(s, b(26) + 0.3 + i * 0.1, b(26) + 0.6 + i * 0.1, fw(dz=0.002), fw(dz=0.12), ease="expo_in")
        hc = P[f"hingecover{i}"]
        fly(hc, b(26) + 0.32 + i * 0.1, b(26) + 0.75 + i * 0.1, (0, 0, 0), fw(dy=0.02, dz=0.16), ease="cubic_in")
    s = P["mss0"]
    unscrew(s, b(26) + 0.25, turns=2, back=0.002, dur=0.28)
    fly(s, b(26) + 0.55, b(26) + 0.85, fw(dz=0.002), fw(dz=0.12), ease="expo_in")
    ms = P["magsafe"]
    KL(ms, b(26) + 0.6, (0, 0, 0), "quart_out")
    KL(ms, b(26) + 1.0, fw(dx=0.012, dz=0.02), "bez")
    fly(ms, b(26.85), b(27) - 0.02, fw(dx=0.012, dz=0.02), fw(dx=0.04, dz=0.30), ease="cubic_in")
    callout("magsafe", b(26) + 0.6, b(27) - 0.05, "MagSafe 3", "先拆左侧铰链盖", dx=-260, dy=-110)

    # ================================================================ I 扬声器 + 天线  B27 → B29（低频抽空，55.40s 一记重击）
    cr.move(b(27), b(27) + 0.5, (0.0, -0.03, 0.27), (0.0, 0.088, -0.003), lens=38, fstop=8, ease="cubic")
    cr.move(b(27) + 0.5, b(29), (0.0, -0.02, 0.255), (0.0, 0.09, 0.008), ease="sine")
    chapter("06", "扬声器与天线", "SPEAKERS + ANTENNAS", b(27), b(29))
    hit = SEC["hits"][0]
    for j, nm in enumerate(("speaker_L", "speaker_R")):
        for k in range(2):
            s = P[f"{nm}_s{k}"]
            unscrew(s, b(27.1) + j * 0.2 + k * 0.1, turns=2, back=0.002, dur=0.3)
            fly(s, b(27.1) + 0.35 + j * 0.2 + k * 0.1, b(27.1) + 0.7 + j * 0.2 + k * 0.1, fw(dz=0.002), fw(dz=0.12), ease="expo_in")
        sp = P[nm]
        sgn = -1 if nm == "speaker_L" else 1   # 机身左侧 = 翻面后画面右侧
        KL(sp, b(27.75), (0, 0, 0), "cubic")
        KL(sp, hit - 0.05, fw(dz=0.008), "back_out")
        KL(sp, hit + 0.45, fw(dz=0.028), "bez")
        KR(sp, hit - 0.05, (0, 0, 0), "back_out")
        KR(sp, hit + 0.45, (0, 0, 0.18 * sgn), "bez")
        fly(sp, b(28.75), b(29) - 0.02, fw(dz=0.028), fw(dx=-0.30 * sgn, dz=0.05), (0, 0, 0.18 * sgn), (0, 0, 0.18 * sgn),
            ease="cubic_in")
    callout("speaker_L", b(27.6), b(28.9), "四扬声器 · 杜比全景声", "声音从屏幕与机身的缝隙传出", dx=-260, dy=120)
    callout("speaker_R_ant", hit, b(28.9), "天线就在扬声器模块里", "左右成对，同轴线接主板", dx=200, dy=120)

    # ================================================================ J 主板 · M5  B29 → B35
    cr.move(b(29), b(29) + 0.6, (0.0, -0.06, 0.23), (-0.005, 0.067, -0.003), lens=40, fstop=8, ease="cubic")
    cr.move(b(29) + 0.6, b(30.5), (0.01, -0.055, 0.22), (-0.005, 0.067, 0.0), ease="sine")
    chapter("07", "主板", "LOGIC BOARD · M5", b(29), b(35))
    for k in range(8):
        s = P[f"lbs{k}"]
        ts = b(29.5) + k * BEAT / 2
        unscrew(s, ts, turns=2, back=0.0024, dur=0.35)
        fly(s, b(30.5) + k * 0.03, b(30.5) + 0.45 + k * 0.03, fw(dz=0.0024), fw(dz=0.15), ease="expo_in")
    callout("logicboard", b(29.6), b(30.6), "主板 · 8 颗螺丝", "细长一条，横贯铰链一侧", dx=-230, dy=-120)
    lb = P["logicboard"]
    KL(lb, b(30.5), (0, 0, 0), "quart_out")
    KL(lb, b(31.25), fw(dz=0.025), "bez")
    for nm in ("thermal_plate", "thermal_tape", "thermal_ear", "thermal_ear.001"):
        if nm in O:
            ob = O[nm]
            KL(ob, b(31.25), (0, 0, 0), "cubic")
            KL(ob, b(31.85), fw(dy=0.048, dz=0.010), "bez")
            KL(ob, b(34.4), fw(dy=0.048, dz=0.010), "cubic")
            KL(ob, b(34.8), (0, 0, 0), "bez")
    hg = value_socket(M["heatspreader"], "heat_glow")
    TL.set(hg, "default_value", b(31.4), 0.0, "sine")
    TL.set(hg, "default_value", b(32.1), 5.0, "sine")
    TL.set(hg, "default_value", b(33.0), 0.0, "bez")
    cr.move(b(30.5), b(31.5), (-0.03, 0.0, 0.17), (-0.07, 0.067, 0.02), lens=45, ease="cubic")
    cr.move(b(31.5), b(32.5), (-0.068, 0.03, 0.10), (-0.098, 0.067, 0.024), lens=60, fstop=4.0, ease="cubic")
    cr.move(b(32.5), b(33.5), (-0.074, 0.028, 0.095), (-0.095, 0.068, 0.024), ease="sine")
    cr.move(b(33.5), b(34.5), (0.0, 0.005, 0.17), (-0.02, 0.07, 0.024), lens=45, fstop=6.3, ease="cubic")
    callout("thermal", b(31.4), b(32.45), "热模块 · 与主板一体", "无风扇，安静无声", dx=230, dy=-120)
    callout("soc", b(32.45), b(33.6), "M5 芯片", "10 核 CPU · 最高 10 核 GPU", dx=-250, dy=-120)
    callout("mem", b(32.8), b(33.6), "统一内存 16GB 起", "带宽 153GB/s", dx=240, dy=110)
    callout("nand", b(33.7), b(34.6), "固态硬盘 512GB 起", "", dx=-220, dy=-110)
    callout("n1", b(33.9), b(34.6), "N1 无线芯片", "Wi-Fi 7 · 蓝牙 6", dx=220, dy=-110)
    fly(lb, b(34.6), b(35) - 0.02, fw(dz=0.025), fw(dy=0.06, dz=0.35), ease="cubic_in")

    # ================================================================ K 触控 ID + 耳机孔  B35 → B37
    cr.move(b(35), b(35) + 0.5, (-0.20, 0.015, 0.115), (-0.13, 0.085, 0.006), lens=58, fstop=5.6, ease="cubic")
    cr.move(b(35) + 0.5, b(37), (-0.205, 0.022, 0.11), (-0.13, 0.086, 0.012), ease="sine")
    chapter("08", "触控 ID 与耳机孔", "TOUCH ID · AUDIO", b(35), b(37))
    tid = P["touchidboard"]
    KL(tid, b(35.25), (0, 0, 0), "quart_out")
    KL(tid, b(35.75), fw(dz=0.016), "bez")
    fly(tid, b(36.6), b(37) - 0.02, fw(dz=0.016), fw(dz=0.3), ease="cubic_in")
    af = P["audioflex"]
    KL(af, b(35.75), (0, 0, 0), "quart_out")
    KL(af, b(36.25), fw(dx=-0.008, dz=0.012), "bez")
    fly(af, b(36.75), b(37) - 0.02, fw(dx=-0.008, dz=0.012), fw(dx=-0.05, dz=0.3), ease="cubic_in")
    callout("touchidboard", b(35.4), b(36.8), "触控 ID 小板", "与主板配对", dx=240, dy=-110)
    callout("jack", b(35.9), b(36.9), "3.5 mm 耳机孔", "支持高阻抗耳机", dx=200, dy=110)
    callout("lid_sensor", b(36.1), b(36.9), "开合角度传感器", "", dx=-200, dy=-100)

    # ================================================================ L 显示屏  B37 → B43
    KR(rig, b(37), (0, PI, 0), "cubic")
    KR(rig, b(38.2), (0, 0, 0), "bez")
    KR(lid, b(37.3), (0, 0, 0), "cubic")
    KR(lid, b(38.5), (-1.85, 0, 0), "bez")
    cr.move(b(37), b(38.3), (0.20, -0.52, 0.22), (0.0, 0.06, 0.08), lens=45, fstop=5.6, ease="cubic")
    cr.move(b(38.3), b(40), (0.0, -0.50, 0.17), (0.0, 0.075, 0.105), lens=50, ease="sine")
    chapter("09", "显示屏", "LIQUID RETINA DISPLAY", b(37), b(43))
    sp = value_socket(M["screen"], "screen_power")
    TL.set(sp, "default_value", 0.0, 0.0, "const")
    TL.set(sp, "default_value", b(38), 0.0, "sine")
    TL.set(sp, "default_value", b(39.6), 1.0, "bez")
    # 摄像头特写：屏幕法线方向往外 16 cm
    th = -1.85
    cy_l, cz_l = (-(L.D / 2 + L.HINGE_Y) + 1.1 + 6.2 - 2.6) * MMf, L.LID_GAP * MMf
    cam_w = Vector((0.0, L.HINGE_Y * MMf + cy_l * math.cos(th) - cz_l * math.sin(th),
                    L.HINGE_Z * MMf + cy_l * math.sin(th) + cz_l * math.cos(th)))
    nrm = Vector((0.0, math.sin(th), -math.cos(th)))
    cr.move(b(40), b(40.6), tuple(cam_w + nrm * 0.17), tuple(cam_w), lens=110, fstop=4.0, ease="cubic")
    cr.move(b(40.6), b(41.3), tuple(cam_w + nrm * 0.15), tuple(cam_w), ease="sine")
    cr.move(b(41.3), b(41.85), (0.12, -0.46, 0.25), (0.0, 0.07, 0.10), lens=45, fstop=5.6, ease="cubic")
    # 屏幕往上飞走的同时，镜头低头看向键盘
    cr.move(b(41.85), b(43.3), (-0.12, -0.27, 0.15), (-0.02, 0.03, 0.006), lens=50, fstop=4.5, ease="cubic")
    callout("screen", b(38.6), b(39.95), "13.6 英寸 Liquid Retina", "2560 × 1664 · 224 ppi", dx=-260, dy=-130)
    text("stat", b(39.0), b(39.95), "500 尼特", "10 亿色 · P3 广色域", "right")
    callout("camera", b(40.55), b(41.3), "1200 万像素人物居中摄像头", "支持桌上视角", dx=230, dy=110)
    text("note", b(41.8), b(42.9), "铰链 6 颗螺丝 · 屏幕与摄像头各一根排线", "", "left")
    hm = P["hingemounts"]
    for o in (lid, hm):
        KL(o, b(41.85), (0, 0, 0), "cubic_in")
        KL(o, b(43) - 0.03, (0, 0.25, 0.32), "bez")
    vis(lid, b(43), False)
    vis(hm, b(43), False)

    # ================================================================ M 顶壳 + 键盘  B43 → B47
    cr.move(b(43.3), b(44), (-0.11, -0.272, 0.148), (-0.02, 0.031, 0.006), ease="sine")
    cr.move(b(44), b(46), (0.10, -0.28, 0.14), (0.02, 0.035, 0.006), ease="sine", arc=True)
    cr.move(b(46), b(47) - 1 / FPS, (0.15, -0.20, 0.10), (0.09, 0.065, 0.006), lens=60, ease="sine")
    chapter("10", "顶壳与键盘", "TOP CASE + KEYBOARD", b(43), b(47))
    kb = value_socket(M["keycap"], "kb_backlight")
    TL.set(kb, "default_value", 0.0, 0.0, "const")
    TL.set(kb, "default_value", b(43.5), 0.0, "sine")
    TL.set(kb, "default_value", b(45), 1.6, "bez")
    callout("keyboard", b(44), b(45.9), "妙控键盘 · 背光", "剪刀式结构 · 78 键", dx=-240, dy=-130)
    callout("fnrow", b(44.5), b(45.9), "12 个全高功能键", "", dx=200, dy=-120)
    callout("touchid", b(46), b(46.95), "触控 ID", "就在电源键里", dx=-220, dy=-110)
    text("note", b(45.9), b(46.95), "键盘与顶壳一体", "换键盘要换整个顶壳", "left")

    # ================================================================ N 全部零件平铺  B47 → B53
    cr.cut(b(47), (0.0, 0.009, 1.30), (0.0, 0.01, 0.0), lens=40, fstop=16)
    cr.move(b(47), b(53) - 1 / FPS, (0.0, 0.009, 1.18), (0.0, 0.01, 0.0), ease="sine")
    TL.set(kb, "default_value", b(47), 1.0, "const")
    # 顶壳（整个底座）切过来时已经在格子里
    KL(base, b(47) - 1 / FPS, (0, 0, 0), "const")
    knoll = knolling_slots(P)
    BASE_SLOT = Vector(knoll["topcase"][0])
    KL(base, b(47), tuple(BASE_SLOT), "bez")
    kb_items = [k for k in knoll if k != "topcase"]
    for k, name in enumerate(kb_items):
        o = P[name]
        pos, rot = knoll[name]
        t_in = b(47) + 0.15 + k * BEAT * 0.62
        target = Vector(pos) - (BASE_SLOT if o.parent == base else Vector((0, 0, 0)))
        if o.parent == base:
            target = target - rest(o)[0]  # KL 用相对静止位置的偏移
        elif o is lid:
            target = Vector(pos) - rest(o)[0]
        vis(o, t_in - 1 / FPS, True, force=name.startswith("screw_b"))
        KL(o, t_in - 1 / FPS, tuple(target + Vector((0, 0, 0.45))), "quart_out")
        KR(o, t_in - 1 / FPS, tuple(Vector(rot) + Vector((0.4, 0.0, 0.3))), "quart_out")
        KL(o, t_in + 0.75, tuple(target), "bez")
        KR(o, t_in + 0.75, tuple(rot), "bez")
        OVER["knoll"].append(dict(part=name, t0=round(t_in + 0.45, 3), t1=round(b(53) - 0.05, 3)))
    TL.set(sp, "default_value", b(47), 1.0, "const")
    OVER["knoll"].insert(0, dict(part="topcase", t0=round(b(47) + 0.35, 3), t1=round(b(53) - 0.05, 3)))
    chapter("", "全部零件", "ALL PARTS", b(47), b(53))

    # ================================================================ O 爆炸图  B53 → B59
    chapter("", "爆炸图", "EXPLODED VIEW", b(53), b(59))
    ex = exploded_offsets(P)
    KL(base, b(53), tuple(BASE_SLOT), "cubic")
    KL(base, b(53) + 1.3, (0, 0, 0), "bez")
    for k, name in enumerate(ex):
        o = P[name] if name in P else O[name]
        off, rot = ex[name]
        t0 = b(53) + 0.05 + (k % 9) * 0.06
        if name not in knoll:
            vis(o, b(53), True, force=name.startswith("screw_b"))
        if name in knoll:
            pos, krot = knoll[name]
            cur = Vector(pos) - (BASE_SLOT if o.parent == base else Vector((0, 0, 0))) - rest(o)[0]
            KL(o, t0, tuple(cur), "cubic")
            KR(o, t0, tuple(krot), "cubic")
        else:
            KL(o, t0, (0, 0, 0), "cubic")
            KR(o, t0, (0, 0, 0), "cubic")
        KL(o, t0 + 1.35, tuple(off), "bez")
        KR(o, t0 + 1.35, tuple(rot), "bez")
    cr.cut(b(53), (0.0, 0.009, 1.18), (0.0, 0.01, 0.0), lens=40, fstop=16)
    cr.move(b(53), b(54.4), (0.62, -0.78, 0.42), (0.0, 0.035, 0.085), lens=40, fstop=11, ease="cubic")
    cr.move(b(54.4), b(57), (-0.42, -0.86, 0.36), (0.0, 0.035, 0.09), ease="sine", arc=True)
    cr.move(b(57), b(59) - 1 / FPS, (-0.64, -0.42, 0.15), (0.0, 0.04, 0.095), lens=40, ease="cubic", arc=True)
    for k, (part, ti) in enumerate([("lid", "屏幕总成"), ("keyboard", "键帽"), ("topcase", "顶壳"), ("trackpad", "触控板"),
                                    ("battery", "电池"), ("logicboard", "主板"), ("bottomcase", "底壳")]):
        OVER["explode"].append(dict(part=part, title=ti, t0=round(b(54.2) + k * BEAT, 3), t1=round(b(58.8), 3)))

    # ================================================================ P 合体 + 片尾  B59 → 结束
    for k, name in enumerate(ex):
        o = P[name] if name in P else O[name]
        off, rot = ex[name]
        t0 = b(59) + (k % 7) * 0.04
        KL(o, t0, tuple(off), "cubic")
        KR(o, t0, tuple(rot), "cubic")
        KL(o, b(60) + 0.05, (0, 0, 0), "bez")
        KR(o, b(60) + 0.05, (-1.75, 0, 0) if o is lid else (0, 0, 0), "bez")
    hit1 = SEC["hits"][1]
    KR(lid, b(60) + 0.06, (-1.75, 0, 0), "cubic_in")
    KR(lid, hit1, (0, 0, 0), "bez")
    TL.set(sp, "default_value", hit1 - 0.45, 1.0, "quad_in")
    TL.set(sp, "default_value", hit1, 0.0, "const")
    TL.set(kb, "default_value", b(59), 1.0, "quad_in")
    TL.set(kb, "default_value", hit1, 0.0, "const")
    cr.move(b(59), b(60.5), (0.36, -0.40, 0.20), (0.0, 0.0, 0.006), lens=50, fstop=5.6, ease="cubic")
    cr.move(b(60.5), END - 1 / FPS, (0.30, -0.36, 0.165), (0.0, 0.0, 0.005), ease="sine")
    text("end", hit2 + 0.2, END, "MacBook Air", "13 英寸 · M5", "center")
    text("disclaimer", hit2 + 0.9, END, "3D 示意模型 · 内部布局依据 Apple 官方维修手册与公开拆解资料", "", "bottom")

    TL.commit()
    # 导出叠加层数据
    od = os.path.join(HERE, "..", "overlay")
    os.makedirs(od, exist_ok=True)
    OVER["fps"] = FPS
    OVER["duration"] = END
    OVER["bars"] = [round(b(i), 4) for i in range(0, 64)]
    json.dump(OVER, open(os.path.join(od, "overlay.json"), "w"), ensure_ascii=False, indent=1)
    print("ANIM keys:", len(TL.keys), "frames", sc.frame_start, sc.frame_end)


# ------------------------------------------------------------------ 平铺格子（俯视，世界坐标）：位置 + 局部旋转
def knolling_slots(P):
    FL = (0.0, PI, 0.0)      # 翻过来，露出朝底壳的那面
    UP = (0.0, 0.0, 0.0)
    S = {}
    S["topcase"] = ((0.0, 0.185, 0.0), UP)
    S["lid"] = ((-0.345, 0.185 + 0.1075 + L.HINGE_Y * MMf - L.D / 2 * MMf + 0.0, 0.0), (0.0, PI, 0.0))
    S["bottomcase"] = ((0.345, 0.185, 0.0), UP)
    S["battery"] = ((-0.30, -0.03, 0.0), FL)
    S["logicboard"] = ((0.10, -0.035, 0.0), FL)
    S["trackpad"] = ((0.385, -0.02, 0.0), FL)
    S["speaker_L"] = ((-0.40, -0.205, 0.0), FL)
    S["speaker_R"] = ((-0.32, -0.205, 0.0), FL)
    S["usbc0"] = ((-0.22, -0.205, 0.0), FL)
    S["usbc1"] = ((-0.17, -0.205, 0.0), FL)
    S["magsafe"] = ((-0.115, -0.205, 0.0), FL)
    S["audioflex"] = ((-0.04, -0.205, 0.0), FL)
    S["touchidboard"] = ((0.03, -0.205, 0.0), FL)
    S["batcover"] = ((0.085, -0.205, 0.0), FL)
    S["hingecover0"] = ((0.14, -0.205, 0.0), FL)
    S["hingecover1"] = ((0.19, -0.205, 0.0), FL)
    for i in range(4):
        S[f"screw_b{i}"] = ((0.25 + i * 0.022, -0.205, 0.0), (PI, 0.0, 0.0))
    return S


# ------------------------------------------------------------------ 爆炸图偏移（正常摆放，相对静止位置，米）+ 旋转
def exploded_offsets(P):
    E = {}
    z = lambda v: (0.0, 0.0, v)  # noqa: E731
    E["bottomcase"] = (z(-0.050), (0, 0, 0))
    for i in range(4):
        E[f"screw_b{i}"] = (z(-0.075), (0, 0, 0))
    E["hingecover0"] = ((-0.01, 0.0, -0.030), (0, 0, 0))
    E["hingecover1"] = ((0.01, 0.0, -0.030), (0, 0, 0))
    E["logicboard"] = ((0.0, 0.012, -0.010), (0, 0, 0))
    E["batcover"] = (z(-0.022), (0, 0, 0))
    E["touchidboard"] = ((0.0, 0.012, 0.012), (0, 0, 0))
    E["usbc0"] = ((-0.035, 0.0, -0.010), (0, 0, 0))
    E["usbc1"] = ((-0.035, 0.0, -0.010), (0, 0, 0))
    E["magsafe"] = ((-0.035, 0.0, -0.010), (0, 0, 0))
    E["audioflex"] = ((0.035, 0.0, -0.010), (0, 0, 0))
    E["speaker_L"] = ((-0.01, 0.028, 0.0), (0, 0, 0))
    E["speaker_R"] = ((0.01, 0.028, 0.0), (0, 0, 0))
    E["battery"] = ((0.0, -0.015, 0.004), (0, 0, 0))
    E["trackpad"] = ((0.0, -0.02, 0.024), (0, 0, 0))
    for nm in ("topcase", "kb_backplate", "kb_flex", "kb_light_flex", "mics", "mic_flex"):
        E[nm] = (z(0.052), (0, 0, 0))
    E["keyboard"] = (z(0.080), (0, 0, 0))
    E["hingemounts"] = ((0.0, 0.03, 0.045), (0, 0, 0))
    E["lid"] = ((0.0, 0.06, 0.075), (-1.75, 0, 0))
    return E
