# MacBook Air（M2 起这一代）美式键盘布局：6 排，全高功能键，右上角触控 ID
# 单位：u（键距）。每排总宽 14.5u。坐标原点在键盘区左上角，x 向右、y 向下（排序号）
# 被 textures.py（画字符贴图）和 model.py（建键帽）共用
PITCH = 18.6  # mm，键距
CAP_GAP = 2.4  # mm，键帽间缝

# (标签, 宽度u, 类型)  类型：k 普通 / t 触控ID / half_up / half_down 方向键半高
ROWS = [
    [("esc", 1.5, "k"), ("F1", 1, "k"), ("F2", 1, "k"), ("F3", 1, "k"), ("F4", 1, "k"), ("F5", 1, "k"),
     ("F6", 1, "k"), ("F7", 1, "k"), ("F8", 1, "k"), ("F9", 1, "k"), ("F10", 1, "k"), ("F11", 1, "k"),
     ("F12", 1, "k"), ("", 1, "t")],
    [("~|`", 1, "k"), ("!|1", 1, "k"), ("@|2", 1, "k"), ("#|3", 1, "k"), ("$|4", 1, "k"), ("%|5", 1, "k"),
     ("^|6", 1, "k"), ("&|7", 1, "k"), ("*|8", 1, "k"), ("(|9", 1, "k"), (")|0", 1, "k"), ("_|-", 1, "k"),
     ("+|=", 1, "k"), ("delete", 1.5, "k")],
    [("tab", 1.5, "k"), ("Q", 1, "k"), ("W", 1, "k"), ("E", 1, "k"), ("R", 1, "k"), ("T", 1, "k"), ("Y", 1, "k"),
     ("U", 1, "k"), ("I", 1, "k"), ("O", 1, "k"), ("P", 1, "k"), ("{|[", 1, "k"), ("}|]", 1, "k"), ("||\\", 1, "k")],
    [("caps lock", 1.75, "k"), ("A", 1, "k"), ("S", 1, "k"), ("D", 1, "k"), ("F", 1, "k"), ("G", 1, "k"),
     ("H", 1, "k"), ("J", 1, "k"), ("K", 1, "k"), ("L", 1, "k"), (":|;", 1, "k"), ('"|\'', 1, "k"),
     ("return", 1.75, "k")],
    [("shift", 2.25, "k"), ("Z", 1, "k"), ("X", 1, "k"), ("C", 1, "k"), ("V", 1, "k"), ("B", 1, "k"), ("N", 1, "k"),
     ("M", 1, "k"), ("<|,", 1, "k"), (">|.", 1, "k"), ("?|/", 1, "k"), ("shift", 2.25, "k")],
    [("fn", 1, "k"), ("control", 1, "k"), ("option", 1, "k"), ("command", 1.25, "k"), ("", 5, "k"),
     ("command", 1.25, "k"), ("option", 1, "k"), ("◀", 1, "k"), ("▲", 1, "half_up"), ("▶", 1, "k")],
]
# 方向键 ▲ 下半格放 ▼
DOWN_KEY = ("▼", 1, "half_down")


def keys_mm():
    """返回每个键：dict(label, kind, x, y, w, h) 单位 mm，x/y 是键帽中心，原点在键盘区中心，y 向上"""
    out = []
    total_w = 14.5 * PITCH
    total_h = len(ROWS) * PITCH
    for r, row in enumerate(ROWS):
        x = 0.0
        for label, wu, kind in row:
            w = wu * PITCH
            cx = x + w / 2 - total_w / 2
            cy = total_h / 2 - (r + 0.5) * PITCH
            capw = w - CAP_GAP
            caph = PITCH - CAP_GAP
            if kind == "half_up":
                out.append(dict(label=label, kind=kind, x=cx, y=cy + PITCH / 4, w=capw, h=PITCH / 2 - CAP_GAP / 2 - 0.3))
                out.append(dict(label=DOWN_KEY[0], kind="half_down", x=cx, y=cy - PITCH / 4, w=capw,
                                h=PITCH / 2 - CAP_GAP / 2 - 0.3))
            else:
                out.append(dict(label=label, kind=kind, x=cx, y=cy, w=capw, h=caph))
            x += w
    return out, total_w, total_h


if __name__ == "__main__":
    ks, w, h = keys_mm()
    print(len(ks), "keys", round(w, 1), "x", round(h, 1), "mm")
