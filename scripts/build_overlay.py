#!/usr/bin/env python3
# 生成 HyperFrames 合成页 video/index.html：3D 渲染视频 + 配乐 + 章节卡/标注/数据/平铺标签/爆炸图标签
# 数据来自 overlay/overlay.json（Blender 动画脚本导出的时间轴 + 锚点逐帧屏幕坐标）
# 用法：.venv/bin/python scripts/build_overlay.py
import json, os, re, html, subprocess, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OV = json.load(open(os.path.join(ROOT, "overlay", "overlay.json")))
OUT = os.path.join(ROOT, "video", "index.html")
FPS = 30
W, H = 1920, 1080
DUR = OV["duration"]
BARS = OV["bars"]
SAFE = 70            # 画面安全边距
CARD_BOX = (110, 96, 760, 300)   # 章节卡占用区域（左上）

ACCENT = "#8CC8F2"   # 天蓝点缀（跟机身天蓝色呼应）
FG = "#F4F2EE"
FG2 = "#AEB6BE"

KNOLL_NAMES = {   # 平铺图标签：零件 → (显示名, 上/下)
    "topcase": ("顶壳 + 键盘", -1), "lid": ("屏幕总成", -1), "bottomcase": ("底壳", -1), "battery": ("电池", -1), "logicboard": ("主板", 1),
    "trackpad": ("触控板", -1), "speaker_L": ("扬声器 + 天线 ×2", 1), "usbc0": ("雷雳 4 接口板 ×2", -1),
    "magsafe": ("MagSafe 3 板", 1), "audioflex": ("音频 / 传感器排线", -1), "touchidboard": ("触控 ID 板", 1),
    "batcover": ("电池盖板", -1), "hingecover0": ("铰链盖 ×2", 1), "screw_b0": ("五角螺丝 ×4", -1),
}


def esc(s):
    return html.escape(s, quote=True)


def track(anchor):
    return OV["tracks"].get(anchor, {})


def in_frame(p, margin=SAFE):
    return p[2] == 1 and margin <= p[0] <= W - margin and margin <= p[1] <= H - margin


def text_w(s, px):
    """估算文字宽度：中文按 1em，西文按 0.58em"""
    w = 0.0
    for ch in s:
        w += px * (1.0 if ord(ch) > 0x2E80 else 0.58)
    return w


def best_run(anchor, t0, t1):
    """在 [t0,t1] 内找锚点连续在画面里的最长一段，返回 (f0, f1)"""
    tr = track(anchor)
    f0, f1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    best, cur = None, None
    for f in range(f0, f1 + 1):
        p = tr.get(str(f))
        ok = p is not None and in_frame(p)
        if ok:
            cur = (cur[0], f) if cur else (f, f)
            if best is None or cur[1] - cur[0] > best[1] - best[0]:
                best = cur
        else:
            cur = None
    return best


def label_box(x, y, dx, dy, tw, th=84):
    if dx >= 0:
        return (x + dx, y + dy - th / 2, x + dx + tw, y + dy + th / 2)
    return (x + dx - tw, y + dy - th / 2, x + dx, y + dy + th / 2)


def overlap(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def chapter_card_windows():
    out = []
    for c in OV["chapters"]:
        hold = min(2.9, c["t1"] - c["t0"] - 0.25)
        out.append((c["t0"], c["t0"] + hold))
    return out


CARD_WIN = chapter_card_windows()


def place(anchor, f0, f1, title, sub, dx0, dy0, used):
    """选一个让标签整段都在画面里、且不压章节卡/其它标签的偏移"""
    tw = max(text_w(title, 36), text_w(sub, 25)) + 40
    tr = track(anchor)
    pts = [tr[str(f)] for f in range(f0, f1 + 1) if str(f) in tr]
    cands = [(dx0, dy0), (-dx0, dy0), (dx0, -dy0), (-dx0, -dy0), (int(dx0 * 1.4), dy0), (-int(dx0 * 1.4), dy0)]
    t0, t1 = f0 / FPS, f1 / FPS
    best, best_score = cands[0], -1e9
    for dx, dy in cands:
        score = 0
        for p in pts[::3]:
            bx = label_box(p[0], p[1], dx, dy, tw)
            if bx[0] < SAFE or bx[2] > W - SAFE or bx[1] < SAFE or bx[3] > H - SAFE:
                score -= 10
            for (c0, c1) in CARD_WIN:
                if c0 < t1 and c1 > t0 and overlap(bx, CARD_BOX):
                    score -= 6
            for (u0, u1, ubox) in used:
                if u0 < t1 and u1 > t0 and overlap(bx, ubox):
                    score -= 8
        if score > best_score:
            best, best_score = (dx, dy), score
        if score == 0:
            break
    mid = pts[len(pts) // 2]
    used.append((t0, t1, label_box(mid[0], mid[1], best[0], best[1], tw)))
    return best


def samples(anchor, f0, f1, step=2):
    tr = track(anchor)
    xs, ys = [], []
    for f in range(f0, f1 + 1, step):
        p = tr.get(str(f))
        if p is None:
            continue
        xs.append(round(p[0], 1))
        ys.append(round(p[1], 1))
    return xs, ys


# ------------------------------------------------------------------ 收集元素
callouts, used = [], []
for i, c in enumerate(OV["callouts"]):
    run = best_run(c["anchor"], c["t0"], c["t1"])
    if run is None or (run[1] - run[0]) / FPS < 0.7:
        print("跳过（锚点不在画面里）:", c["anchor"], c["title"])
        continue
    f0, f1 = run
    dx, dy = place(c["anchor"], f0, f1, c["title"], c["sub"], c["dx"], c["dy"], used)
    xs, ys = samples(c["anchor"], f0, f1)
    callouts.append(dict(id=f"co{i}", t0=f0 / FPS, t1=f1 / FPS, title=c["title"], sub=c["sub"], dx=dx, dy=dy, xs=xs, ys=ys,
                         step=2 / FPS))

knoll = []
kn_items = {k["part"]: k for k in OV["knoll"]}
for part, (name, side) in KNOLL_NAMES.items():
    k = kn_items.get(part)
    if not k:
        continue
    run = best_run(k["anchor"], k["t0"], k["t1"])
    if run is None:
        print("跳过平铺标签:", part)
        continue
    f0, f1 = run
    xs, ys = samples(k["anchor"], f0, f1, 6)
    knoll.append(dict(id=f"kn_{part}", t0=f0 / FPS, t1=f1 / FPS, name=name, side=side, xs=xs, ys=ys, step=6 / FPS))
# 顶壳在切镜时就已就位

explode = []
ex_runs = []
for j, e in enumerate(OV["explode"]):
    run = best_run(e["anchor"], e["t0"], e["t1"])
    if run is None or (run[1] - run[0]) / FPS < 0.7:
        print("跳过爆炸图标签:", e["part"])
        continue
    ex_runs.append((j, e, run))
# 爆炸图标签排成左右两列：按锚点在画面中的高度均匀分配，避免挤在一起
if ex_runs:
    fm = int(sum((r[0] + r[1]) / 2 for _, _, r in ex_runs) / len(ex_runs))
    pos = {}
    for j, e, run in ex_runs:
        tr = track(e["anchor"])
        f = min(max(fm, run[0]), run[1])
        p = tr.get(str(f)) or tr.get(str(run[0]))
        pos[j] = p
    cx = sum(p[0] for p in pos.values()) / len(pos)
    left = sorted([j for j in pos if pos[j][0] < cx], key=lambda j: pos[j][1])
    right = sorted([j for j in pos if pos[j][0] >= cx], key=lambda j: pos[j][1])
    # 两列数量尽量平衡
    while len(left) > len(right) + 1:
        mv = max(left, key=lambda j: pos[j][0]); left.remove(mv); right.append(mv)
    while len(right) > len(left) + 1:
        mv = min(right, key=lambda j: pos[j][0]); right.remove(mv); left.append(mv)
    left.sort(key=lambda j: pos[j][1]); right.sort(key=lambda j: pos[j][1])
    xl = min(pos[j][0] for j in pos) - 170
    xr = max(pos[j][0] for j in pos) + 170
    slot = {}
    for col, xcol in ((left, xl), (right, xr)):
        if not col:
            continue
        ys_ = [pos[j][1] for j in col]
        y0 = max(SAFE + 40, min(ys_) - 30)
        y1 = min(H - SAFE - 40, max(ys_) + 30)
        n = len(col)
        for k, j in enumerate(col):
            ty = (y0 + y1) / 2 if n == 1 else y0 + (y1 - y0) * k / (n - 1)
            slot[j] = (xcol - pos[j][0], ty - pos[j][1])
    for j, e, run in ex_runs:
        f0, f1 = run
        xs, ys = samples(e["anchor"], f0, f1)
        dx, dy = slot[j]
        explode.append(dict(id=f"ex{j}", t0=f0 / FPS, t1=f1 / FPS, title=e["title"], dx=dx, dy=dy, xs=xs, ys=ys, step=2 / FPS))

chapters = [c for c in OV["chapters"]]
texts = OV["texts"]

# ------------------------------------------------------------------ 字体子集
chars = set()
for c in callouts:
    chars |= set(c["title"] + c["sub"])
for k in knoll:
    chars |= set(k["name"])
for e in explode:
    chars |= set(e["title"])
for c in chapters:
    chars |= set(c["cn"])
for t in texts:
    chars |= set(t["main"] + t["sub"])
chars |= set("顶壳 + 键盘0123456789 .,·:：，。、（）()×%-–—/WhcmkgGBs")
txt = "".join(sorted(chars))
fdir = os.path.join(ROOT, "video", "assets", "fonts")
open(os.path.join(fdir, "chars.txt"), "w").write(txt)
py = os.path.join(ROOT, ".venv", "bin", "pyftsubset")
for src, dst in (("NotoSerifSC.ttf", "NotoSerifSC-sub.woff2"), ("NotoSansSC.ttf", "NotoSansSC-sub.woff2")):
    subprocess.run([py, os.path.join(fdir, "src", src), f"--text-file={os.path.join(fdir, 'chars.txt')}",
                    "--flavor=woff2", f"--output-file={os.path.join(fdir, dst)}", "--layout-features=*",
                    "--unicodes=U+0020-007E"], check=True)
print("字体子集：", len(txt), "字")

# ------------------------------------------------------------------ HTML
def split_stat(main):
    m = re.match(r"^([\d.]+)\s*(.*)$", main)
    return (m.group(1), m.group(2)) if m else (main, "")


parts = []
for c in callouts:
    side = "r" if c["dx"] >= 0 else "l"
    ax, ay = abs(c["dx"]), c["dy"]
    # 引线：从锚点斜出 → 水平到标签
    mx = c["dx"] * 0.42
    pts = f"0,0 {mx:.0f},{c['dy']:.0f} {c['dx']:.0f},{c['dy']:.0f}"
    sub = f'<div class="co-s">{esc(c["sub"])}</div>' if c["sub"] else ""
    pos = f"left:{c['dx'] + 14}px;" if side == "r" else f"right:{-c['dx'] + 14}px;"
    parts.append(f'''<div class="co" id="{c["id"]}">
  <svg class="co-svg" width="2" height="2" viewBox="0 0 2 2"><polyline class="co-line" points="{pts}" /></svg>
  <div class="co-dot"></div><div class="co-ring"></div>
  <div class="co-lab co-{side}" style="{pos}top:{c['dy'] - (36 if c['sub'] else 30)}px;" data-layout-allow-overlap><div class="co-t" data-layout-allow-overlap>{esc(c["title"])}</div>{sub}</div>
</div>''')
for k in knoll:
    parts.append(f'''<div class="kn" id="{k["id"]}"><div class="kn-lab" style="top:-16px;" data-layout-allow-overlap>{esc(k["name"])}</div></div>''')
for e in explode:
    side = "r" if e["dx"] >= 0 else "l"
    mx = e["dx"] * 0.55
    pts = f"0,0 {mx:.0f},{e['dy']:.0f} {e['dx']:.0f},{e['dy']:.0f}"
    pos = f"left:{e['dx'] + 14}px;" if side == "r" else f"right:{-e['dx'] + 14}px;"
    parts.append(f'''<div class="co ex" id="{e["id"]}">
  <svg class="co-svg" width="2" height="2" viewBox="0 0 2 2"><polyline class="co-line" points="{pts}" /></svg>
  <div class="co-dot"></div>
  <div class="co-lab co-{side}" style="{pos}top:{e['dy'] - 30:.0f}px;" data-layout-allow-overlap><div class="co-t" data-layout-allow-overlap>{esc(e["title"])}</div></div>
</div>''')
for i, c in enumerate(chapters):
    parts.append(f'''<div class="scrim scrim-tl" id="chs{i}"></div>''')
    parts.append(f'''<div class="card" id="ch{i}"><div class="card-rule"></div><div class="card-t" data-layout-allow-overlap>{esc(c["cn"])}</div></div>''')
for i, t in enumerate(texts):
    k = t["kind"]
    sc_cls = {"title": "scrim-tl", "stat": "scrim-l" if t.get("pos") == "left" else "scrim-r", "note": "scrim-bl"}.get(k)
    if sc_cls and t.get("pos") != "center":
        parts.append(f'''<div class="scrim {sc_cls}" id="txs{i}"></div>''')
    if k == "title":
        parts.append(f'''<div class="tx tx-title" id="tx{i}"><div class="tt-main" data-layout-allow-overlap>{esc(t["main"])}</div><div class="tt-sub" data-layout-allow-overlap>{esc(t["sub"])}</div></div>''')
    elif k == "stat":
        num, unit = split_stat(t["main"])
        cls = "tx-stat tx-stat-l" if t.get("pos") == "left" else "tx-stat"
        parts.append(f'''<div class="tx {cls}" id="tx{i}"><div class="st-row"><span class="st-num">{esc(num)}</span><span class="st-unit">{esc(unit)}</span></div><div class="st-sub" data-layout-allow-overlap>{esc(t["sub"])}</div></div>''')
    elif k == "note":
        cls = "tx-note-c" if t["pos"] == "center" else "tx-note"
        sub = f'<div class="nt-sub" data-layout-allow-overlap>{esc(t["sub"])}</div>' if t["sub"] else ""
        parts.append(f'''<div class="tx {cls}" id="tx{i}"><div class="nt-main" data-layout-allow-overlap>{esc(t["main"])}</div>{sub}</div>''')
    elif k == "end":
        parts.append(f'''<div class="scrim-top" id="txs{i}"></div>''')
        parts.append(f'''<div class="tx tx-end" id="tx{i}"><div class="en-main" data-layout-allow-overlap>{esc(t["main"])}</div><div class="en-sub" data-layout-allow-overlap>{esc(t["sub"])}</div></div>''')
    elif k == "disclaimer":
        parts.append(f'''<div class="tx tx-disc" id="tx{i}" data-layout-allow-overlap>{esc(t["main"])}</div>''')
# 进度条：10 个拆解步骤
segs = "".join(f'<div class="pg-seg" id="pg{i}"><div class="pg-fill" id="pgf{i}"></div></div>' for i in range(10))
parts.append(f'<div class="pg" id="pg">{segs}</div>')

DATA = dict(callouts=[{k: c[k] for k in ("id", "t0", "t1", "xs", "ys", "step")} for c in callouts],
            knoll=[{k: c[k] for k in ("id", "t0", "t1", "xs", "ys", "step")} for c in knoll],
            explode=[{k: c[k] for k in ("id", "t0", "t1", "xs", "ys", "step")} for c in explode],
            chapters=[dict(t0=c["t0"], t1=c["t1"], num=c["num"]) for c in chapters],
            texts=[dict(kind=t["kind"], t0=t["t0"], t1=t["t1"]) for t in texts],
            bars=BARS, dur=DUR)

CSS = f"""
@font-face {{ font-family: "Noto Serif SC"; src: url("assets/fonts/NotoSerifSC-sub.woff2") format("woff2"); font-weight: 200 900; }}
@font-face {{ font-family: "Noto Sans SC"; src: url("assets/fonts/NotoSansSC-sub.woff2") format("woff2"); font-weight: 100 900; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: 1920px; height: 1080px; overflow: hidden; background: #07090c; }}
#root {{ position: relative; width: 100%; height: 100%; overflow: hidden; background: #07090c;
  font-family: "Noto Sans SC", sans-serif; color: {FG}; }}
#teardown {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
#ov {{ position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }}
.vig {{ position: absolute; inset: 0; background: radial-gradient(ellipse 75% 70% at 50% 48%, rgba(0,0,0,0) 62%, rgba(2,3,5,0.42) 100%); }}
.co, .kn {{ position: absolute; left: 0; top: 0; width: 0; height: 0; opacity: 0; }}
.co-svg {{ position: absolute; left: 0; top: 0; overflow: visible; }}
.co-line {{ fill: none; stroke: {ACCENT}; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round;
  filter: drop-shadow(0 0 6px rgba(0,0,0,0.7)); }}
.co-dot {{ position: absolute; left: -6px; top: -6px; width: 12px; height: 12px; border-radius: 50%; background: {ACCENT};
  box-shadow: 0 0 0 3px rgba(7,9,12,0.55), 0 0 18px rgba(140,200,242,0.75); }}
.co-ring {{ position: absolute; left: -17px; top: -17px; width: 34px; height: 34px; border-radius: 50%;
  border: 2px solid {ACCENT}; opacity: 0.0; }}
.co-lab {{ position: absolute; white-space: nowrap; background: rgba(7,9,13,0.60); padding: 9px 16px 11px;
  border-radius: 10px; box-shadow: 0 6px 24px rgba(0,0,0,0.35); }}
.co-r {{ text-align: left; }}
.co-l {{ text-align: right; }}
.co-t {{ font-size: 36px; font-weight: 600; letter-spacing: 0.01em; line-height: 1.25;
  text-shadow: 0 2px 18px rgba(0,0,0,0.85), 0 0 3px rgba(0,0,0,0.6); }}
.co-s {{ font-size: 25px; font-weight: 400; color: {FG2}; line-height: 1.35; margin-top: 4px;
  text-shadow: 0 2px 14px rgba(0,0,0,0.9); }}
.ex .co-t {{ font-size: 32px; }}
.kn-tick {{ position: absolute; left: -1px; width: 2px; background: {ACCENT}; opacity: 0.85; }}
.kn-lab {{ position: absolute; left: -240px; width: 480px; text-align: center; white-space: nowrap; font-size: 25px; font-weight: 500;
  color: {FG}; text-shadow: 0 2px 12px rgba(0,0,0,0.9); }}
.card {{ position: absolute; left: 118px; top: 104px; opacity: 0; }}
.card-rule {{ width: 72px; height: 3px; background: {ACCENT}; margin-bottom: 22px; transform-origin: left center; }}
.card-t {{ font-family: "Noto Serif SC", serif; font-weight: 900; font-size: 104px; line-height: 1.05; letter-spacing: 0.02em;
  text-shadow: 0 4px 30px rgba(0,0,0,0.6); }}
.tx {{ position: absolute; opacity: 0; }}
.tx-title {{ left: 118px; top: 112px; }}
.tt-main {{ font-family: "Noto Serif SC", serif; font-weight: 900; font-size: 112px; line-height: 1.12; letter-spacing: 0.01em;
  text-shadow: 0 4px 34px rgba(0,0,0,0.65); }}
.tt-sub {{ margin-top: 22px; font-size: 38px; font-weight: 400; color: {FG2}; letter-spacing: 0.06em; }}
.tx-stat {{ right: 130px; top: 380px; text-align: right; }}
.st-row {{ display: flex; align-items: baseline; justify-content: flex-end; gap: 14px; }}
.tx-stat-l {{ left: 104px; right: auto; text-align: left; }}
.tx-stat-l .st-row {{ justify-content: flex-start; }}
.st-num {{ font-family: "IBM Plex Mono", monospace; font-weight: 700; font-size: 132px; line-height: 1; letter-spacing: -0.03em;
  text-shadow: 0 4px 30px rgba(0,0,0,0.6); }}
.st-unit {{ font-family: "Noto Sans SC", "IBM Plex Mono", sans-serif; font-weight: 500; font-size: 48px; color: {ACCENT}; }}
.st-sub {{ margin-top: 16px; font-size: 32px; color: {FG2}; text-shadow: 0 2px 14px rgba(0,0,0,0.9); }}
.tx-note {{ left: 118px; bottom: 120px; }}
.tx-note-c {{ left: 0; right: 0; top: 470px; text-align: center; }}
.nt-main {{ font-size: 46px; font-weight: 600; text-shadow: 0 2px 18px rgba(0,0,0,0.85); }}
.tx-note-c .nt-main {{ font-family: "Noto Serif SC", serif; font-weight: 900; font-size: 96px; letter-spacing: 0.08em; }}
.nt-sub {{ margin-top: 8px; font-size: 30px; color: {FG2}; text-shadow: 0 2px 14px rgba(0,0,0,0.9); }}
.tx-end {{ left: 0; right: 0; top: 44px; text-align: center; }}
.scrim-top {{ position: absolute; left: 0; right: 0; top: 0; height: 460px; opacity: 0; pointer-events: none;
  background: linear-gradient(to bottom, rgba(3,4,6,0.78) 0%, rgba(3,4,6,0.45) 45%, rgba(3,4,6,0) 100%); }}
.en-main {{ font-family: "Noto Serif SC", serif; font-weight: 900; font-size: 124px; letter-spacing: 0.02em;
  text-shadow: 0 4px 40px rgba(0,0,0,0.7); }}
.en-sub {{ margin-top: 2px; font-size: 36px; color: {FG2}; letter-spacing: 0.12em; }}
.tx-disc {{ left: 0; right: 0; bottom: 64px; text-align: center; font-size: 22px; color: #8D949B; letter-spacing: 0.04em; }}
.pg {{ position: absolute; left: 50%; bottom: 46px; width: 420px; margin-left: -210px; height: 4px; display: flex; gap: 8px; opacity: 0; }}
.pg-seg {{ flex: 1; height: 4px; background: rgba(255,255,255,0.16); border-radius: 2px; overflow: hidden; }}
.pg-fill {{ width: 100%; height: 100%; background: {ACCENT}; transform-origin: left center; }}
.blackout {{ position: absolute; inset: 0; background: #000; opacity: 0; }}
.scrim {{ position: absolute; pointer-events: none; opacity: 0;
  background: radial-gradient(ellipse at center, rgba(4,6,9,0.62) 0%, rgba(4,6,9,0.38) 42%, rgba(4,6,9,0) 72%); }}
.scrim-tl {{ left: -260px; top: -160px; width: 1500px; height: 720px; }}
.scrim-r {{ right: -280px; top: 230px; width: 1200px; height: 560px; }}
.scrim-l {{ left: -300px; top: 230px; width: 1200px; height: 560px; }}
.scrim-bl {{ left: -260px; bottom: -200px; width: 1500px; height: 560px; }}
"""

JS = r"""
const D = __DATA__;
const tl = gsap.timeline({ paused: true });
const q = (id) => document.getElementById(id);
// 标注：跟着锚点走 + 出现/消失
function track(el, it) {
  const n = it.xs.length;
  tl.set(el, { x: it.xs[0], y: it.ys[0] }, Math.max(0, it.t0 - 0.02));
  if (n > 1) tl.to(el, { keyframes: { x: it.xs, y: it.ys, easeEach: "none" }, duration: (n - 1) * it.step, ease: "none" }, it.t0);
}
for (const it of D.callouts) {
  const el = q(it.id);
  track(el, it);
  const line = el.querySelector(".co-line");
  const len = 520;
  line.style.strokeDasharray = len;
  tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.12, ease: "none" }, it.t0);
  tl.fromTo(el.querySelector(".co-dot"), { scale: 0 }, { scale: 1, duration: 0.35, ease: "back.out(2.5)" }, it.t0);
  tl.fromTo(el.querySelector(".co-ring"), { scale: 0.4, opacity: 0.9 }, { scale: 1.6, opacity: 0, duration: 0.7, ease: "expo.out" }, it.t0 + 0.05);
  tl.fromTo(line, { strokeDashoffset: len }, { strokeDashoffset: 0, duration: 0.45, ease: "power2.out" }, it.t0 + 0.05);
  const lab = el.querySelector(".co-lab");
  const dir = lab.classList.contains("co-r") ? -18 : 18;
  tl.fromTo(lab, { opacity: 0, x: dir }, { opacity: 1, x: 0, duration: 0.45, ease: "power3.out" }, it.t0 + 0.22);
  const tOut = Math.max(it.t0 + 0.6, it.t1 - 0.28);
  tl.to(el, { opacity: 0, duration: 0.26, ease: "power1.in" }, tOut);
}
for (const it of D.explode) {
  const el = q(it.id);
  track(el, it);
  const line = el.querySelector(".co-line");
  line.style.strokeDasharray = 300;
  tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.12, ease: "none" }, it.t0);
  tl.fromTo(el.querySelector(".co-dot"), { scale: 0 }, { scale: 1, duration: 0.3, ease: "back.out(2.5)" }, it.t0);
  tl.fromTo(line, { strokeDashoffset: 300 }, { strokeDashoffset: 0, duration: 0.4, ease: "power2.out" }, it.t0 + 0.05);
  const lab = el.querySelector(".co-lab");
  tl.fromTo(lab, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }, it.t0 + 0.18);
  tl.to(el, { opacity: 0, duration: 0.3, ease: "power1.in" }, Math.max(it.t0 + 0.6, it.t1 - 0.3));
}
for (const it of D.knoll) {
  const el = q(it.id);
  track(el, it);
  tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.35, ease: "power2.out" }, it.t0);
  tl.fromTo(el.querySelector(".kn-lab"), { y: 8 }, { y: 0, duration: 0.45, ease: "power3.out" }, it.t0);
  tl.to(el, { opacity: 0, duration: 0.25, ease: "power1.in" }, it.t1 - 0.25);
}
// 章节卡
D.chapters.forEach((c, i) => {
  const el = q("ch" + i);
  const hold = Math.min(c.num === "" ? 1.9 : 2.9, c.t1 - c.t0 - 0.25);   // 「全部零件」「爆炸图」不是拆解步骤，标题停短一点
  const sc = q("chs" + i);
  tl.fromTo(sc, { opacity: 0 }, { opacity: 1, duration: 0.4, ease: "power1.out" }, c.t0);
  tl.to(sc, { opacity: 0, duration: 0.5, ease: "power1.in" }, c.t0 + hold);
  tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "none" }, c.t0 + 0.05);
  tl.fromTo(el.querySelector(".card-rule"), { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "expo.out" }, c.t0 + 0.05);
  tl.fromTo(el.querySelector(".card-t"), { y: 46, opacity: 0, clipPath: "inset(-30% -8% 130% -8%)" },
    { y: 0, opacity: 1, clipPath: "inset(-30% -8% -30% -8%)", duration: 0.7, ease: "expo.out" }, c.t0 + 0.1);
  tl.to(el, { opacity: 0, y: -14, duration: 0.4, ease: "power2.in" }, c.t0 + hold);
});
// 文字块
D.texts.forEach((t, i) => {
  const el = q("tx" + i);
  const sc = q("txs" + i);
  if (sc) {
    tl.fromTo(sc, { opacity: 0 }, { opacity: 1, duration: 0.45, ease: "power1.out" }, t.t0);
    tl.to(sc, { opacity: 0, duration: 0.45, ease: "power1.in" }, t.t1 - 0.4);
  }
  if (t.kind === "title") {
    tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.2 }, t.t0);
    tl.fromTo(el.querySelector(".tt-main"), { y: 60, clipPath: "inset(-30% -8% 130% -8%)" }, { y: 0, clipPath: "inset(-30% -8% -30% -8%)", duration: 1.0, ease: "expo.out" }, t.t0);
    tl.fromTo(el.querySelector(".tt-sub"), { opacity: 0, x: -20 }, { opacity: 1, x: 0, duration: 0.8, ease: "power3.out" }, t.t0 + 0.45);
    tl.to(el, { opacity: 0, y: -20, duration: 0.5, ease: "power2.in" }, t.t1 - 0.5);
  } else if (t.kind === "stat") {
    tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.2 }, t.t0);
    tl.fromTo(el.querySelector(".st-row"), { y: 50, clipPath: "inset(-30% -8% 130% -8%)" }, { y: 0, clipPath: "inset(-30% -8% -30% -8%)", duration: 0.8, ease: "expo.out" }, t.t0);
    tl.fromTo(el.querySelector(".st-sub"), { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, t.t0 + 0.3);
    tl.to(el, { opacity: 0, duration: 0.35, ease: "power2.in" }, t.t1 - 0.35);
  } else if (t.kind === "note") {
    tl.fromTo(el, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.55, ease: "power3.out" }, t.t0);
    tl.to(el, { opacity: 0, duration: 0.3, ease: "power2.in" }, t.t1 - 0.3);
  } else if (t.kind === "end") {
    tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.2 }, t.t0);
    tl.fromTo(el.querySelector(".en-main"), { y: 50, opacity: 0, scale: 1.04 }, { y: 0, opacity: 1, scale: 1, duration: 1.4, ease: "expo.out" }, t.t0);
    tl.fromTo(el.querySelector(".en-sub"), { opacity: 0 }, { opacity: 1, duration: 0.8, ease: "power2.out" }, t.t0 + 0.6);
  } else if (t.kind === "disclaimer") {
    tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.8, ease: "power2.out" }, t.t0);
  }
});
// 进度条：拆解 10 步
const pg = q("pg");
const steps = D.chapters.filter((c) => c.num !== "");
tl.fromTo(pg, { opacity: 0 }, { opacity: 1, duration: 0.5 }, steps[0].t0);
steps.forEach((c, i) => {
  tl.fromTo(q("pgf" + i), { scaleX: 0 }, { scaleX: 1, duration: c.t1 - c.t0, ease: "none" }, c.t0);
});
tl.to(pg, { opacity: 0, duration: 0.5 }, steps[steps.length - 1].t1 - 0.2);
// 片尾压黑
tl.fromTo("#blackout", { opacity: 0 }, { opacity: 1, duration: 0.8, ease: "power1.inOut" }, D.dur - 2.3);
window.__timelines["main"] = tl;
"""

body = "\n".join(parts)
page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<script src="assets/vendor/gsap.min.js"></script>
<style>{CSS}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{DUR}" data-width="1920" data-height="1080">
  <video id="teardown" class="clip" src="assets/teardown.mp4" muted playsinline data-start="0" data-duration="{DUR}" data-track-index="0"></video>
  <audio id="music" src="assets/music.m4a" data-start="0" data-duration="{DUR}" data-track-index="2" data-volume="1"></audio>
  <div id="ov" class="clip" data-start="0" data-duration="{DUR}" data-track-index="1">
    <div class="vig"></div>
    <div class="blackout" id="blackout"></div>
{body}
  </div>
</div>
<script>{JS.replace("__DATA__", json.dumps(DATA, ensure_ascii=False))}</script>
</body>
</html>
"""
open(OUT, "w").write(page)
print("写出", OUT, f"{len(page) / 1024:.0f} KB", "标注", len(callouts), "平铺", len(knoll), "爆炸", len(explode))
