#!/usr/bin/env python3
# 用同一套文案、同一个音色，分别跑 Next 和 Flash 两个模型，逐段合成并记录耗时/时长
# 用法：python3 tts/gen_all.py next|flash
import json, os, sys, subprocess, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qwen_tts import synth
HERE = os.path.dirname(os.path.abspath(__file__))
N = json.load(open(os.path.join(HERE, "narration.json")))
which = sys.argv[1]
model = {"next": "qwen-audio-3.1-tts-next", "flash": "qwen-audio-3.1-tts-flash"}[which]
od = os.path.join(HERE, which)
os.makedirs(od, exist_ok=True)


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout.strip() or 0)


def one(seg):
    out = os.path.join(od, seg["id"] + ".wav")
    if os.path.exists(out) and os.path.getsize(out) > 2000:
        return seg["id"], {"ok": True, "cached": True}
    kw = dict(voice=N["voice"])
    if which == "next" and N.get("text_prompt"):
        kw["text_prompt"] = N["text_prompt"]
    # 句首加一个逗号：Next 模型会吞掉第一个字，加了就正常；两个版本发同样的文本
    r = synth(model, N.get("lead", "") + seg["text"], out, tries=8, **kw)
    return seg["id"], r


workers = 2 if which == "next" else 6   # next 并发太高会 429
res = {}
with cf.ThreadPoolExecutor(workers) as ex:
    for sid, r in ex.map(one, N["segments"]):
        res[sid] = r
        print(sid, r, flush=True)
report = []
for seg in N["segments"]:
    p = os.path.join(od, seg["id"] + ".wav")
    d = dur(p) if os.path.exists(p) else 0
    win = seg["end"] - seg["t"]
    report.append(dict(id=seg["id"], dur=round(d, 2), window=round(win, 2), over=round(d - win, 2),
                       secs=res[seg["id"]].get("secs"), ok=res[seg["id"]].get("ok")))
json.dump(report, open(os.path.join(od, "report.json"), "w"), ensure_ascii=False, indent=1)
for r in report:
    flag = "  超时!" if r["over"] > 0 else ""
    print(f'{r["id"]} 时长 {r["dur"]:5.2f}s / 窗口 {r["window"]:5.2f}s  合成 {r["secs"]}s{flag}')
