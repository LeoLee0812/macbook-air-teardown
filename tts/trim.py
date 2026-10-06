#!/usr/bin/env python3
# 去掉每段 TTS 首尾静音，输出到 <版本>/trim/，打印有效时长
import os, sys, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
which = sys.argv[1]
src = os.path.join(HERE, which)
dst = os.path.join(src, "trim")
os.makedirs(dst, exist_ok=True)
N = json.load(open(os.path.join(HERE, "narration.json")))
out = {}
for seg in N["segments"]:
    a = os.path.join(src, seg["id"] + ".wav")
    b = os.path.join(dst, seg["id"] + ".wav")
    if not os.path.exists(a):
        continue
    af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
          "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a, "-af", af, "-ar", "48000", "-ac", "1", b], check=True)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", b],
                             capture_output=True, text=True).stdout)
    out[seg["id"]] = round(d, 3)
    print(seg["id"], f"{d:5.2f}s  窗口 {seg['end'] - seg['t']:5.2f}s  需提速 {max(1.0, d / (seg['end'] - seg['t'])):.2f}x")
json.dump(out, open(os.path.join(dst, "durations.json"), "w"), indent=1)
