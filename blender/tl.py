# 时间线工具：先收集关键帧，最后统一写入并设置插值/缓动；摄像机走球面插值采样
import math, json, os
import bpy
from mathutils import Vector

FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
SEC = json.load(open(os.path.join(HERE, "..", "music", "sections.json")))
BAR = SEC["bar"]
BEAT = SEC["beat"]
PH = SEC["phase"]


def bar(b):
    """第 b 小节起点的秒数（可带小数，如 12.5 = 第 12 小节第 3 拍）"""
    return PH + b * BAR


def F(t):
    return int(round(t * FPS))


# Blender 内置的 Penner 缓动：插值类型 + 缓动方向
EASE = {
    # "bez" 用在每段运动的终点：之后保持不动直到下一段运动开始（常量插值）
    "lin": ("LINEAR", "AUTO"), "const": ("CONSTANT", "AUTO"), "bez": ("CONSTANT", "AUTO"), "smooth": ("BEZIER", "AUTO"),
    "sine": ("SINE", "EASE_IN_OUT"), "sine_in": ("SINE", "EASE_IN"), "sine_out": ("SINE", "EASE_OUT"),
    "quad": ("QUAD", "EASE_IN_OUT"), "quad_in": ("QUAD", "EASE_IN"), "quad_out": ("QUAD", "EASE_OUT"),
    "cubic": ("CUBIC", "EASE_IN_OUT"), "cubic_in": ("CUBIC", "EASE_IN"), "cubic_out": ("CUBIC", "EASE_OUT"),
    "quart": ("QUART", "EASE_IN_OUT"), "quart_out": ("QUART", "EASE_OUT"), "quart_in": ("QUART", "EASE_IN"),
    "quint": ("QUINT", "EASE_IN_OUT"), "quint_out": ("QUINT", "EASE_OUT"), "quint_in": ("QUINT", "EASE_IN"),
    "expo": ("EXPO", "EASE_IN_OUT"), "expo_out": ("EXPO", "EASE_OUT"), "expo_in": ("EXPO", "EASE_IN"),
    "circ": ("CIRC", "EASE_IN_OUT"), "circ_out": ("CIRC", "EASE_OUT"),
    "back_out": ("BACK", "EASE_OUT"), "back": ("BACK", "EASE_IN_OUT"),
}


# Python 侧缓动（摄像机采样用）
def ease_fn(name):
    def sine(t):
        return 0.5 - 0.5 * math.cos(math.pi * t)

    def cubic(t):
        return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2

    def quart(t):
        return 8 * t ** 4 if t < 0.5 else 1 - (-2 * t + 2) ** 4 / 2

    def quint(t):
        return 16 * t ** 5 if t < 0.5 else 1 - (-2 * t + 2) ** 5 / 2

    def expo(t):
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0
        return 2 ** (20 * t - 10) / 2 if t < 0.5 else (2 - 2 ** (-20 * t + 10)) / 2

    def cubic_out(t):
        return 1 - (1 - t) ** 3

    def quart_out(t):
        return 1 - (1 - t) ** 4

    def quint_out(t):
        return 1 - (1 - t) ** 5

    def expo_out(t):
        return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)

    def cubic_in(t):
        return t ** 3

    def lin(t):
        return t

    return {"sine": sine, "cubic": cubic, "quart": quart, "quint": quint, "expo": expo, "cubic_out": cubic_out,
            "quart_out": quart_out, "quint_out": quint_out, "expo_out": expo_out, "cubic_in": cubic_in,
            "lin": lin}[name]


class Timeline:
    def __init__(self):
        self.keys = {}  # (id_block, data_path, index) -> {frame: (value, ease)}

    def set(self, owner, path, t, value, ease="bez", index=None):
        """在时间 t（秒）把 owner.path 设为 value；ease 决定从这一帧到下一帧的插值"""
        self.setf(owner, path, F(t), value, ease, index)

    def setf(self, owner, path, fr, value, ease="bez", index=None):
        """同 set，但直接给帧号"""
        if isinstance(value, (tuple, list, Vector)) and index is None:
            for i, v in enumerate(value):
                if v is None:
                    continue
                self.keys.setdefault((owner, path, i), {})[fr] = (float(v), ease)
        else:
            self.keys.setdefault((owner, path, -1 if index is None else index), {})[fr] = (float(value), ease)

    def tween(self, owner, path, t0, t1, v0, v1, ease="cubic"):
        self.set(owner, path, t0, v0, ease)
        self.set(owner, path, t1, v1, "bez")

    def hold(self, owner, path, t, value):
        self.set(owner, path, t, value, "const")

    def commit(self):
        for (owner, path, idx), frames in self.keys.items():
            fs = sorted(frames)
            for fr in fs:
                val, _ = frames[fr]
                if idx >= 0:
                    getattr(owner, path)[idx] = val
                    owner.keyframe_insert(path, index=idx, frame=fr)
                else:
                    setattr(owner, path, val if not isinstance(getattr(owner, path), bool) else bool(val))
                    owner.keyframe_insert(path, frame=fr)
            # 设置每个关键帧的插值
            fc = find_fcurve(owner, path, idx)
            if fc is None:
                continue
            for kp in fc.keyframe_points:
                fr = int(round(kp.co[0]))
                if fr in frames:
                    interp, easing = EASE[frames[fr][1]]
                    kp.interpolation = interp
                    if easing != "AUTO":
                        kp.easing = easing
                    else:
                        kp.easing = "AUTO"
                    kp.handle_left_type = "AUTO_CLAMPED"
                    kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()


def find_fcurve(owner, path, idx):
    ad = None
    full = path
    if isinstance(owner, bpy.types.ID):
        ad = owner.animation_data
    else:
        # 节点插槽等非 ID 数据：动画挂在所属 ID（node tree）上
        idb = owner.id_data
        ad = idb.animation_data
        full = owner.path_from_id(path)
    if ad is None or ad.action is None:
        return None
    for fc in iter_fcurves(ad):
        if fc.data_path == full and (idx < 0 or fc.array_index == idx):
            return fc
    return None


def iter_fcurves(ad):
    act = ad.action
    # Blender 4.4+ 分层动作：fcurves 在 layers/strips/channelbags 里
    if hasattr(act, "layers") and len(act.layers):
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        yield fc
    elif hasattr(act, "fcurves"):
        for fc in act.fcurves:
            yield fc


# ------------------------------------------------------------------ 摄像机
class CamRig:
    """摄像机位置 + 目标点（Track To）+ 焦距 + 光圈；支持直线和绕目标的弧线移动"""

    def __init__(self, tl, cam, tgt):
        self.tl, self.cam, self.tgt = tl, cam, tgt
        self.pose = None
        self.t = 0.0

    def cut(self, t, loc, tgt, lens=50, fstop=5.6):
        """硬切：t 之前一帧保持旧机位（常量），t 起新机位"""
        if self.pose is not None:
            prev = F(t) - 1
            self._key(prev, self.pose, "const")
        self.pose = dict(loc=Vector(loc), tgt=Vector(tgt), lens=lens, fstop=fstop)
        self._key(F(t), self.pose, "lin")
        self.t = t

    def hold(self, t1):
        self._key(F(t1), self.pose, "lin")
        self.t = t1

    def move(self, t0, t1, loc, tgt, lens=None, fstop=None, ease="cubic", arc=False, step=1):
        """从当前机位移到新机位；arc=True 时绕目标点做球面插值（距离和角度分别插值）"""
        a = self.pose
        b = dict(loc=Vector(loc), tgt=Vector(tgt), lens=lens if lens else a["lens"], fstop=fstop if fstop else a["fstop"])
        f0, f1 = F(t0), F(t1)
        if f0 > F(self.t):
            self._key(f0, a, "lin")
        e = ease_fn(ease)
        n = max(1, f1 - f0)
        for k in range(0, n + 1, step):
            s = e(k / n)
            tgt_p = a["tgt"].lerp(b["tgt"], s)
            if arc:
                va, vb = a["loc"] - a["tgt"], b["loc"] - b["tgt"]
                ra, rb = va.length, vb.length
                aza, azb = math.atan2(va.y, va.x), math.atan2(vb.y, vb.x)
                d = azb - aza
                while d > math.pi:
                    d -= 2 * math.pi
                while d < -math.pi:
                    d += 2 * math.pi
                ela, elb = math.asin(max(-1, min(1, va.z / ra))), math.asin(max(-1, min(1, vb.z / rb)))
                r = ra + (rb - ra) * s
                az = aza + d * s
                el = ela + (elb - ela) * s
                loc_p = tgt_p + Vector((r * math.cos(el) * math.cos(az), r * math.cos(el) * math.sin(az), r * math.sin(el)))
            else:
                loc_p = a["loc"].lerp(b["loc"], s)
            p = dict(loc=loc_p, tgt=tgt_p, lens=a["lens"] + (b["lens"] - a["lens"]) * s,
                     fstop=a["fstop"] + (b["fstop"] - a["fstop"]) * s)
            self._key(f0 + k, p, "lin")
        self._key(f1, b, "lin")
        self.pose = b
        self.t = t1

    def _key(self, fr, p, ease):
        self.tl.setf(self.cam, "location", fr, tuple(p["loc"]), ease)
        self.tl.setf(self.tgt, "location", fr, tuple(p["tgt"]), ease)
        self.tl.setf(self.cam.data, "lens", fr, p["lens"], ease)
        self.tl.setf(self.cam.data.dof, "aperture_fstop", fr, p["fstop"], ease)
