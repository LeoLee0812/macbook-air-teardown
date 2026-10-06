#!/usr/bin/env python3
# 对转写有问题的段落多录几条（TTS 每次结果不同），按 whisper 字错率挑最好的一条替换
# 用法：python3 tts/takes.py next s03 s06 ...  [--n 3]
import json, os, sys, shutil, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qwen_tts import synth
from verify import cer, local_asr
HERE = os.path.dirname(os.path.abspath(__file__))
N = json.load(open(os.path.join(HERE, "narration.json")))
argv_ = sys.argv[1:]
if "--n" in argv_:
    i = argv_.index("--n"); argv_ = argv_[:i] + argv_[i + 2:]
args = [a for a in argv_ if not a.startswith("--")]
which, ids = args[0], args[1:]
n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 3
model = {"next": "qwen-audio-3.1-tts-next", "flash": "qwen-audio-3.1-tts-flash"}[which]
segs = {s["id"]: s for s in N["segments"]}
TD = os.path.join(HERE, which, "takes")
os.makedirs(TD, exist_ok=True)
log = {}


def whisper_retry(p):
    # 本地 faster-whisper（先去掉首尾静音再识别，避免静音段幻听）
    tmp = p + ".trim.wav"
    af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
          "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-af", af, tmp], check=True)
    t = local_asr(tmp)
    os.remove(tmp)
    return t


for sid in ids:
    ref = segs[sid]["text"]
    cands = []
    cur = os.path.join(HERE, which, sid + ".wav")
    if os.path.exists(cur):
        t = whisper_retry(cur)
        cands.append((cer(ref, t) if t else 1.0, cur, t))
    for k in range(n):
        out = os.path.join(TD, f"{sid}_t{k}.wav")
        r = synth(model, N.get("lead", "") + ref, out, voice=N["voice"], tries=8)
        if not r.get("ok"):
            continue
        t = whisper_retry(out)
        cands.append((cer(ref, t) if t else 1.0, out, t))
    cands.sort(key=lambda c: c[0])
    best = cands[0]
    if best[1] != cur:
        shutil.copy(best[1], cur)
    log[sid] = [dict(cer=round(c[0], 3), file=os.path.basename(c[1]), text=c[2]) for c in cands]
    print(sid, "选中", os.path.basename(best[1]), f"CER {best[0]:.2f}", best[2], flush=True)
json.dump(log, open(os.path.join(TD, f"takes_{'_'.join(ids)}.json"), "w"), ensure_ascii=False, indent=1)
