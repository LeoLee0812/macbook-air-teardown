#!/usr/bin/env python3
# 把某个 TTS 版本（next / flash）的 22 段旁白排到时间轴上，混进配乐（旁白出现时配乐自动压低），输出成片音轨
# 用法：python3 tts/build_vo.py next|flash
#   1) 读 trim/ 下去掉首尾静音的分段和时长
#   2) 按 narration.json 的起点顺排：前一段说不完就把后一段顺延（最多 0.6 秒），还不够就轻微提速（≤1.15 倍）
#   3) 拼成整条旁白轨 vo.wav，再和配乐做侧链压缩（ducking），最后响度标准化到 -14 LUFS
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
which = sys.argv[1]
N = json.load(open(os.path.join(HERE, "narration.json")))
D = json.load(open(os.path.join(HERE, which, "trim", "durations.json")))
FIT = os.path.join(HERE, which, "fit")
os.makedirs(FIT, exist_ok=True)
TOTAL = 123.21
MUSIC = os.path.join(ROOT, "music", "bed.wav")

segs = N["segments"]
layout = []
prev_end = 0.0
for i, s in enumerate(segs):
    d = D[s["id"]]
    start = max(s["t"], prev_end + 0.15)
    nxt = segs[i + 1]["t"] if i + 1 < len(segs) else TOTAL - 0.4
    limit = nxt + 0.6 - 0.15             # 允许顺延到下一段原定起点后 0.6 秒
    hard = min(s["end"] + 0.9, limit)     # 也别拖出本镜头太多
    tempo = 1.0
    if start + d > hard:
        tempo = min(1.15, d / max(0.3, hard - start))
    real = d / tempo
    layout.append(dict(id=s["id"], text=s["text"], start=round(start, 3), dur=round(real, 3), end=round(start + real, 3),
                       tempo=round(tempo, 3), raw=d, over=round(start + real - hard, 3)))
    prev_end = start + real

for L in layout:
    src = os.path.join(HERE, which, "trim", L["id"] + ".wav")
    dst = os.path.join(FIT, L["id"] + ".wav")
    af = f"atempo={L['tempo']:.4f}" if L["tempo"] > 1.001 else "anull"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", af, "-ar", "48000", "-ac", "1", dst], check=True)

# 整条旁白轨：静音底 + 各段按起点延迟后混合
inputs, filt = [], []
for k, L in enumerate(layout):
    inputs += ["-i", os.path.join(FIT, L["id"] + ".wav")]
    ms = int(round(L["start"] * 1000))
    filt.append(f"[{k}:a]adelay={ms}|{ms},apad=whole_dur={TOTAL}[a{k}]")
mix_in = "".join(f"[a{k}]" for k in range(len(layout)))
filt.append(f"{mix_in}amix=inputs={len(layout)}:normalize=0:duration=longest,atrim=0:{TOTAL}[vo]")
vo = os.path.join(HERE, which, "vo.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", ";".join(filt), "-map", "[vo]", "-ar", "48000",
                                                            "-ac", "1", vo], check=True)

# 旁白响度先拉到 -16 LUFS 左右，配乐被旁白侧链压低约 9 dB，最后整体 -14 LUFS / -1 dBTP
mix = os.path.join(HERE, which, f"mix_{which}.wav")
fc = ("[0:a]loudnorm=I=-15:TP=-2:LRA=7,aformat=channel_layouts=stereo,asplit=2[vo1][vo2];"
      "[1:a]volume=0.92[mus];"
      "[mus][vo1]sidechaincompress=threshold=0.02:ratio=9:attack=25:release=420:makeup=1[duck];"
      "[duck][vo2]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1:LRA=9[out]")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vo, "-i", MUSIC, "-filter_complex", fc, "-map", "[out]", "-ar", "48000",
                "-t", str(TOTAL), mix], check=True)
json.dump(layout, open(os.path.join(HERE, which, "layout.json"), "w"), ensure_ascii=False, indent=1)
for L in layout:
    flag = f"  ⚠ 超出 {L['over']:.2f}s" if L["over"] > 0.01 else ""
    print(f"{L['id']} {L['start']:7.2f} → {L['end']:7.2f}  ×{L['tempo']:.2f}{flag}  {L['text']}")
print("输出", mix)
