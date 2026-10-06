#!/usr/bin/env python3
# 两个版本逐段转写（Gemini 走 OpenLux），和文案比对字错率，结果写 verify_<版本>.json
import json, os, sys, re, concurrent.futures as cf, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gem_asr import transcribe
HERE = os.path.dirname(os.path.abspath(__file__))
N = json.load(open(os.path.join(HERE, "narration.json")))
which = sys.argv[1]
CN_NUM = {"0": "零", "1": "一", "2": "二", "3": "三", "4": "四", "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"}


def norm(s):
    s = s.replace("Ｍ", "M").upper()
    s = re.sub(r"[\s，。、：:；;！!？?,.·\-—（）()「」“”\"']", "", s)
    # 数字统一成逐位汉字，避免「13」和「十三」算错
    s = re.sub(r"\d", lambda m: CN_NUM[m.group(0)], s)
    s = s.replace("十", "").replace("百", "").replace("千", "").replace("万", "")
    return s


def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    sm = difflib.SequenceMatcher(None, r, h)
    errs = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
    return errs / max(1, len(r))


def one(seg):
    p = os.path.join(HERE, which, "trim", seg["id"] + ".wav")
    for _ in range(3):
        try:
            t = transcribe(p)
            if "未收到音频" not in t:
                return seg["id"], seg["text"], t
        except Exception as e:  # noqa: BLE001
            t = f"ERR {e}"
    return seg["id"], seg["text"], t


rows = []
with cf.ThreadPoolExecutor(6) as ex:
    for sid, ref, hyp in ex.map(one, N["segments"]):
        c = cer(ref, hyp)
        rows.append(dict(id=sid, ref=ref, hyp=hyp, cer=round(c, 3)))
        print(f"{sid} CER {c:.2f} | {hyp}", flush=True)
json.dump(rows, open(os.path.join(HERE, f"verify_{which}.json"), "w"), ensure_ascii=False, indent=1)
print("平均字错率", round(sum(r["cer"] for r in rows) / len(rows), 3))
