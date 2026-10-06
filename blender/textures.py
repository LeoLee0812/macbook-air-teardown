#!/usr/bin/env python3
# 生成贴图（用项目 .venv 的 Python 跑，不在 Blender 里跑）：
#   键盘字符、屏幕壁纸、电池标签、底壳刻字、各块 PCB（走线/焊盘/丝印）
# 用法：.venv/bin/python blender/textures.py [all|kb|wall|battery|bottom|pcb]
import math, os, random, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
TEX = os.path.join(HERE, "tex")
os.makedirs(TEX, exist_ok=True)

SF = "/System/Library/Fonts/SFNS.ttf"
SF_MONO = "/System/Library/Fonts/SFNSMono.ttf"
HELV = "/System/Library/Fonts/Helvetica.ttc"


def font(size, path=SF):
    for p in (path, SF, HELV):
        try:
            return ImageFont.truetype(p, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- 键盘字符
def keyboard():
    from keyboard_layout import keys_mm
    keys, W, H = keys_mm()
    PX = 14  # 每毫米像素
    img = Image.new("L", (int(W * PX), int(H * PX)), 0)
    d = ImageDraw.Draw(img)

    def cx(x):
        return (x + W / 2) * PX

    def cy(y):
        return (H / 2 - y) * PX

    for k in keys:
        lab, kind = k["label"], k["kind"]
        if kind == "t" or not lab:
            continue
        x0, y0 = cx(k["x"] - k["w"] / 2), cy(k["y"] + k["h"] / 2)
        x1, y1 = cx(k["x"] + k["w"] / 2), cy(k["y"] - k["h"] / 2)
        kw, kh = x1 - x0, y1 - y0
        if len(lab) == 3 and lab[1] == "|":  # 双字符键：上符号下数字
            top, bot = lab[0], lab[2]
            f = font(int(3.3 * PX))
            d.text((x0 + kw / 2, y0 + kh * 0.30), top, fill=255, font=f, anchor="mm")
            d.text((x0 + kw / 2, y0 + kh * 0.70), bot, fill=255, font=f, anchor="mm")
        elif len(lab) == 1 and lab.isalpha():  # 字母键：居中大写
            d.text((x0 + kw / 2, y0 + kh / 2), lab, fill=255, font=font(int(4.6 * PX)), anchor="mm")
        elif lab in ("◀", "▲", "▶", "▼"):
            s = 1.3 * PX
            mx, my = x0 + kw / 2, y0 + kh / 2
            pts = {"◀": [(mx - s, my), (mx + s * .8, my - s), (mx + s * .8, my + s)],
                   "▶": [(mx + s, my), (mx - s * .8, my - s), (mx - s * .8, my + s)],
                   "▲": [(mx, my - s * .8), (mx - s, my + s * .6), (mx + s, my + s * .6)],
                   "▼": [(mx, my + s * .8), (mx - s, my - s * .6), (mx + s, my - s * .6)]}[lab]
            d.polygon(pts, fill=255)
        elif lab.startswith("F") and lab[1:].isdigit():  # 功能键：小号字
            d.text((x0 + kw / 2, y0 + kh * 0.62), lab, fill=255, font=font(int(2.9 * PX)), anchor="mm")
            # 上方一个小图标点位（亮度/音量等图标的抽象）
            r = 0.9 * PX
            mx, my = x0 + kw / 2, y0 + kh * 0.33
            d.ellipse((mx - r, my - r, mx + r, my + r), outline=255, width=max(2, int(0.25 * PX)))
        else:  # 修饰键：左下/右下小写
            f = font(int(2.7 * PX))
            if lab in ("delete", "return") or (lab == "shift" and k["x"] > 0) or (lab in ("command", "option") and k["x"] > 0):
                d.text((x1 - 1.6 * PX, y1 - 1.6 * PX), lab, fill=255, font=f, anchor="rs")
            elif lab == "fn":
                d.text((x0 + 1.6 * PX, y0 + 2.2 * PX), "fn", fill=255, font=f, anchor="lt")
                # 地球图标
                r = 1.25 * PX
                mx, my = x0 + kw - 3.4 * PX, y1 - 3.2 * PX
                w_ = max(2, int(0.22 * PX))
                d.ellipse((mx - r, my - r, mx + r, my + r), outline=255, width=w_)
                d.ellipse((mx - r * .45, my - r, mx + r * .45, my + r), outline=255, width=w_)
                d.line((mx - r, my, mx + r, my), fill=255, width=w_)
            elif lab == "esc":
                d.text((x0 + 1.6 * PX, y1 - 1.6 * PX), lab, fill=255, font=f, anchor="ls")
            else:
                d.text((x0 + 1.6 * PX, y1 - 1.6 * PX), lab, fill=255, font=f, anchor="ls")
            if lab == "command":
                # ⌘ 符号
                d.text((x1 - 2.6 * PX if k["x"] < 0 else x0 + 2.6 * PX, y0 + 3.0 * PX), "⌘", fill=255,
                       font=font(int(3.2 * PX)), anchor="mm")
            if lab == "option":
                d.text((x1 - 2.6 * PX if k["x"] < 0 else x0 + 2.6 * PX, y0 + 3.0 * PX), "⌥", fill=255,
                       font=font(int(3.2 * PX)), anchor="mm")
            if lab == "control":
                d.text((x1 - 2.6 * PX, y0 + 3.0 * PX), "⌃", fill=255, font=font(int(3.2 * PX)), anchor="mm")
            if lab == "caps lock":
                d.ellipse((x0 + 1.6 * PX, y0 + 1.8 * PX, x0 + 2.6 * PX, y0 + 2.8 * PX), fill=90)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(os.path.join(TEX, "kb_legend.png"))
    json.dump({"w_mm": W, "h_mm": H}, open(os.path.join(TEX, "kb_legend.json"), "w"))
    print("kb_legend.png", img.size)


# ---------------------------------------------------------------- 壁纸
def wallpaper():
    W, H = 2560, 1664
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    u, v = x / W, y / H
    # 底色：深海蓝 → 天蓝的对角渐变
    c0 = np.array([0.02, 0.05, 0.12])
    c1 = np.array([0.10, 0.30, 0.58])
    c2 = np.array([0.62, 0.84, 0.98])
    t = np.clip(0.55 * u + 0.45 * (1 - v), 0, 1)
    base = c0[None, None] * (1 - t[..., None]) + c1[None, None] * t[..., None]
    img = base.copy()
    # 几条柔和流动的光带
    rng = np.random.default_rng(7)
    for i in range(7):
        ph = rng.uniform(0, 6.28)
        fr = rng.uniform(1.2, 2.4)
        amp = rng.uniform(0.08, 0.18)
        cen = 0.25 + 0.08 * i + amp * np.sin(fr * 6.28 * u + ph) + 0.05 * np.sin(3.1 * 6.28 * u + ph * 2)
        dist = (v - cen)
        width = rng.uniform(0.015, 0.05)
        band = np.exp(-(dist ** 2) / (2 * width ** 2))
        glow = np.exp(-(dist ** 2) / (2 * (width * 4) ** 2)) * 0.35
        k = (band * 0.55 + glow) * (0.35 + 0.65 * u)
        col = c2 * (0.6 + 0.4 * (i / 6))
        img = img + k[..., None] * col[None, None] * 0.55
    # 暗角
    r = np.sqrt((u - 0.55) ** 2 + (v - 0.45) ** 2)
    img *= (1.0 - 0.55 * np.clip(r - 0.25, 0, 1))[..., None]
    img = np.clip(img, 0, 1) ** (1 / 1.1)
    out = Image.fromarray((img * 255).astype(np.uint8), "RGB")
    # 菜单栏：顶部一条半透明深色，几个小块代表菜单项（不画任何商标）
    d = ImageDraw.Draw(out, "RGBA")
    d.rectangle((0, 0, W, 64), fill=(8, 12, 20, 120))
    xs = [60, 170, 260, 350, 450]
    for i, xx in enumerate(xs):
        d.rounded_rectangle((xx, 24, xx + (70 if i == 0 else 56), 40), 6, fill=(235, 240, 248, 200 if i == 0 else 150))
    for i, xx in enumerate([2060, 2140, 2220, 2300, 2400]):
        d.rounded_rectangle((xx, 22, xx + 44, 42), 6, fill=(235, 240, 248, 150))
    out = out.filter(ImageFilter.GaussianBlur(0.8))
    out.save(os.path.join(TEX, "wallpaper.png"))
    print("wallpaper.png", out.size)


# ---------------------------------------------------------------- 电池标签
def battery_label(spec):
    """spec: dict(cells=[{w,d}], wh, text...)；每个电芯一张小标签，统一画在一张图上按 UV 取"""
    W, H = 1600, 1000
    img = Image.new("RGB", (W, H), (29, 30, 33))
    d = ImageDraw.Draw(img)
    # 细线框 + 文字
    d.rectangle((40, 40, W - 40, H - 40), outline=(120, 122, 126), width=3)
    f1, f2 = font(64), font(34)
    d.text((80, 80), spec.get("title", "Li-ion Polymer Battery"), fill=(225, 226, 228), font=f1)
    yy = 180
    for line in spec.get("lines", []):
        d.text((80, yy), line, fill=(170, 172, 176), font=f2)
        yy += 52
    # 警示图标区（抽象的圆角方块）
    for i in range(5):
        d.rounded_rectangle((80 + i * 120, H - 200, 180 + i * 120, H - 100), 14, outline=(170, 172, 176), width=4)
    img.save(os.path.join(TEX, "battery_label.png"))
    print("battery_label.png")


# ---------------------------------------------------------------- 底壳刻字
def bottom_engrave(text_lines):
    W, H = 2400, 600
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 200), text_lines[0], fill=255, font=font(150), anchor="mm")
    for i, t in enumerate(text_lines[1:]):
        d.text((W / 2, 360 + i * 60), t, fill=200, font=font(40), anchor="mm")
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    img.save(os.path.join(TEX, "bottom_engrave.png"))
    print("bottom_engrave.png")



# ---------------------------------------------------------------- PCB
def _mirror_text(img, xy, text, fnt, fill, anchor="ls"):
    """把文字左右镜像后贴到 img 上（xy 为镜像前的锚点）"""
    tmp = Image.new("RGBA", (int(fnt.size * len(text) * 0.75) + 20, int(fnt.size * 1.6)), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((10, int(fnt.size * 1.2)), text, fill=fill, font=fnt, anchor="ls")
    tmp = tmp.transpose(Image.FLIP_LEFT_RIGHT)
    x, y = int(xy[0]), int(xy[1])
    img.paste(tmp, (x - tmp.width + 10, y - int(fnt.size * 1.2)), tmp)


def _pcb_draw(W_mm, D_mm, cx0, cy0, rects, seed, px=20, labels=True, mirror=False):
    """画一块 PCB：深绿阻焊 + 走线 + 过孔 + 焊盘 + 丝印。rects=[(cx,cy,w,d,kind,label)] 机身坐标 mm"""
    rng = random.Random(seed)
    Wp, Hp = int(W_mm * px), int(D_mm * px)
    col = Image.new("RGB", (Wp, Hp), (15, 16, 18))   # 黑色阻焊（Apple 主板是黑色 PCB）
    met = Image.new("L", (Wp, Hp), 0)
    dc, dm = ImageDraw.Draw(col), ImageDraw.Draw(met)

    def P(x, y):  # 机身 mm → 像素（y 向上）
        return ((x - (cx0 - W_mm / 2)) * px, (cy0 + D_mm / 2 - y) * px)

    # 铺铜区（稍亮的大块）
    for i in range(14):
        x, y = rng.uniform(cx0 - W_mm / 2, cx0 + W_mm / 2), rng.uniform(cy0 - D_mm / 2, cy0 + D_mm / 2)
        w, d = rng.uniform(6, 26), rng.uniform(4, 16)
        a, b = P(x - w / 2, y + d / 2), P(x + w / 2, y - d / 2)
        dc.rectangle((a[0], a[1], b[0], b[1]), fill=(21, 23, 26))
    # 走线：从芯片边缘出发的曼哈顿 + 45° 折线束
    for r in rects:
        cx, cy, w, d = r[0], r[1], r[2], r[3]
        n = int(6 + (w + d) * 0.6)
        for k in range(n):
            side = rng.choice("NSEW")
            if side in "NS":
                x = cx + rng.uniform(-w / 2, w / 2); y = cy + (d / 2 if side == "N" else -d / 2)
                dx, dy = 0, (1 if side == "N" else -1)
            else:
                y = cy + rng.uniform(-d / 2, d / 2); x = cx + (w / 2 if side == "E" else -w / 2)
                dx, dy = (1 if side == "E" else -1), 0
            pts = [P(x, y)]
            L1 = rng.uniform(2, 9)
            x += dx * L1; y += dy * L1; pts.append(P(x, y))
            # 45° 拐弯
            t = rng.choice((-1, 1))
            L2 = rng.uniform(1, 5)
            if dx == 0:
                x += t * L2; y += dy * L2
            else:
                x += dx * L2; y += t * L2
            pts.append(P(x, y))
            L3 = rng.uniform(3, 18)
            if dx == 0:
                x += t * L3 * 0 + 0; y += dy * L3
            else:
                x += dx * L3
            pts.append(P(x, y))
            wt = rng.choice((1, 1, 2, 2, 3))
            dc.line(pts, fill=(36, 39, 44), width=wt, joint="curve")
            if rng.random() < 0.35:  # 末端过孔
                vx, vy = pts[-1]
                rr = rng.choice((5, 6, 7))
                dc.ellipse((vx - rr, vy - rr, vx + rr, vy + rr), fill=(196, 160, 92))
                dm.ellipse((vx - rr, vy - rr, vx + rr, vy + rr), fill=255)
                dc.ellipse((vx - rr * .45, vy - rr * .45, vx + rr * .45, vy + rr * .45), fill=(10, 14, 12))
    # 随机过孔阵列
    for i in range(int(W_mm * D_mm * 0.05)):
        x, y = rng.uniform(cx0 - W_mm / 2, cx0 + W_mm / 2), rng.uniform(cy0 - D_mm / 2, cy0 + D_mm / 2)
        vx, vy = P(x, y)
        rr = rng.choice((4, 5))
        dc.ellipse((vx - rr, vy - rr, vx + rr, vy + rr), fill=(160, 132, 80))
        dm.ellipse((vx - rr, vy - rr, vx + rr, vy + rr), fill=200)
    # 焊盘阵列与丝印框
    for r in rects:
        cx, cy, w, d, kind, label = r
        a, b = P(cx - w / 2 - 0.6, cy + d / 2 + 0.6), P(cx + w / 2 + 0.6, cy - d / 2 - 0.6)
        if kind == "chip":
            dc.rectangle((a[0], a[1], b[0], b[1]), outline=(205, 210, 205), width=3)
        if kind in ("con", "chip"):
            # 两侧小焊盘
            nn = int(max(w, d) / 0.8)
            for k in range(nn):
                if w >= d:
                    x = cx - w / 2 + (k + 0.5) * w / nn
                    for yy in (cy + d / 2 + 0.25, cy - d / 2 - 0.25):
                        q = P(x, yy)
                        dc.rectangle((q[0] - 4, q[1] - 5, q[0] + 4, q[1] + 5), fill=(214, 178, 104))
                        dm.rectangle((q[0] - 4, q[1] - 5, q[0] + 4, q[1] + 5), fill=255)
                else:
                    y = cy - d / 2 + (k + 0.5) * d / nn
                    for xx in (cx + w / 2 + 0.25, cx - w / 2 - 0.25):
                        q = P(xx, y)
                        dc.rectangle((q[0] - 5, q[1] - 4, q[0] + 5, q[1] + 4), fill=(214, 178, 104))
                        dm.rectangle((q[0] - 5, q[1] - 4, q[0] + 5, q[1] + 4), fill=255)
        if labels and label:
            if mirror:
                q = P(cx + w / 2, cy + d / 2 + 1.0)
                _mirror_text(col, (q[0] + 0, q[1] - 6), label, font(26, SF_MONO), (210, 214, 210, 255))
            else:
                q = P(cx - w / 2, cy + d / 2 + 1.0)
                dc.text((q[0], q[1] - 26), label, fill=(210, 214, 210), font=font(26, SF_MONO))
    # 散布的测试点
    for i in range(int(W_mm * D_mm * 0.004)):
        x, y = rng.uniform(cx0 - W_mm / 2, cx0 + W_mm / 2), rng.uniform(cy0 - D_mm / 2, cy0 + D_mm / 2)
        q = P(x, y)
        rr = rng.choice((5, 6, 8))
        dc.ellipse((q[0] - rr, q[1] - rr, q[0] + rr, q[1] + rr), fill=(214, 178, 104))
        dm.ellipse((q[0] - rr, q[1] - rr, q[0] + rr, q[1] + rr), fill=255)
    # 板号丝印
    if labels:
        if mirror:
            q = P(cx0 - W_mm / 2 + 34, cy0 - D_mm / 2 + 4)
            _mirror_text(col, q, "820-03286-A", font(40, SF_MONO), (210, 214, 210, 255))
        else:
            q = P(cx0 + W_mm / 2 - 34, cy0 - D_mm / 2 + 6)
            dc.text(q, "820-03286-A", fill=(210, 214, 210), font=font(40, SF_MONO))
    # 阻焊颗粒感
    arr = np.asarray(col).astype(np.float32)
    noise = np.random.default_rng(seed).normal(0, 2.2, arr.shape[:2])[..., None]
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr), met


def pcb():
    import layout as L
    B = L.LB
    S = L.SOC
    rects = [(S["cx"], S["cy"], S["w"], S["d"], "chip", "U1000")]
    rects += [(n["cx"], n["cy"], n["w"], n["d"], "chip", f"U{9000 + i * 100}") for i, n in enumerate(L.NAND)]
    rects += [(p["cx"], p["cy"], p["w"], p["d"], "chip", f"U{8100 + i * 10}") for i, p in enumerate(L.PMIC)]
    rects += [(s["cx"], s["cy"], s["w"], s["d"], "shield", "") for s in L.SHIELDS]
    rects += [(c["cx"], c["cy"], c["w"], c["d"], "con", f"J{5100 + i * 10}") for i, c in enumerate(L.CONNECTORS)]
    # 底面（SoC 所在面，朝底壳）：丝印字镜像
    col, met = _pcb_draw(B["w"], B["d"], B["cx"], B["cy"], rects, 1234, mirror=True)
    col.save(os.path.join(TEX, "pcb_main.png"))
    met.save(os.path.join(TEX, "pcb_main_metal.png"))
    # 顶面（朝键盘）：只有连接器和零散元件
    rects_t = [(c["cx"], c["cy"], c["w"], c["d"], "con", "") for c in L.CONNECTORS]
    col, met = _pcb_draw(B["w"], B["d"], B["cx"], B["cy"], rects_t, 4321)
    col.save(os.path.join(TEX, "pcb_main_top.png"))
    met.save(os.path.join(TEX, "pcb_main_top_metal.png"))
    # 小板通用贴图（40×40 mm 一张，平铺）
    rects = [(0, 0, 8, 5, "chip", "U200"), (12, 10, 4, 3, "con", "J1"), (-12, -8, 6, 6, "chip", "U300")]
    col, met = _pcb_draw(40, 40, 0, 0, rects, 77)
    col.save(os.path.join(TEX, "pcb_small.png"))
    met.save(os.path.join(TEX, "pcb_small_metal.png"))
    print("pcb textures", col.size)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "kb"):
        keyboard()
    if what in ("all", "wall"):
        wallpaper()
    if what in ("all", "pcb"):
        pcb()
    if what in ("all", "battery"):
        battery_label({"title": "Li-ion Polymer Battery", "lines": [
            "53.8 Wh", "Rechargeable · Do not puncture, crush or heat", "MacBook Air (13-inch)"]})
    if what in ("all", "bottom"):
        bottom_engrave(["MacBook Air", ""])
