#!/usr/bin/env python3
# 精确拟合拍网格（BPM+相位），再用低频能量判断小节重拍（downbeat）和 8 小节乐句边界
# 用法：.venv/bin/python scripts/beatgrid.py music/raw/precise-0.wav
import sys, json, numpy as np, librosa
y, sr = librosa.load(sys.argv[1], sr=22050)
dur = len(y)/sr
hop = 128
oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
t = librosa.times_like(oenv, sr=sr, hop_length=hop)
# 网格搜索 BPM 与相位，使 onset 包络在网格点上的均值最大
best = None
for bpm in np.arange(122.6, 123.5, 0.005):
    P = 60/bpm
    for ph in np.arange(0, P, 0.004):
        g = np.arange(ph, dur, P)
        idx = np.clip(np.round(g*sr/hop).astype(int), 0, len(oenv)-1)
        s = oenv[idx].mean()
        if best is None or s > best[0]:
            best = (s, bpm, ph)
s, bpm, ph = best
P = 60/bpm
print(f"BPM {bpm:.3f}  相位 {ph:.4f}s  拍长 {P:.5f}s  小节 {4*P:.4f}s")
# 低频（kick/bass）能量按拍取样
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
low = S[freqs < 150].sum(axis=0)
lowon = np.maximum(0, np.diff(low, prepend=low[0]))
beats = np.arange(ph, dur, P)
bi = np.clip(np.round(beats*sr/hop).astype(int), 0, len(lowon)-1)
# 每拍附近 ±30ms 的低频冲击
vals = np.array([lowon[max(0,i-3):i+4].max() for i in bi])
main = (beats > 26) & (beats < 52)
for k in range(4):
    sel = main & (np.arange(len(beats)) % 4 == k)
    print(f"拍序 mod4={k}: 低频冲击均值 {vals[sel].mean():.1f}")
# 能量按拍
rms = librosa.feature.rms(y=y, hop_length=hop)[0]
eb = np.array([20*np.log10(rms[max(0,i-20):i+20].mean()+1e-6) for i in bi])
json.dump({"bpm": bpm, "phase": ph, "period": P, "beats": [round(float(b),4) for b in beats],
           "beat_db": [round(float(e),2) for e in eb], "low_hit": [round(float(v),1) for v in vals]},
          open("music/beatgrid.json","w"), indent=0)
# 打印每小节（按 mod4=0 起算）能量，找乐句
for b0 in range(0, len(beats)-3, 4):
    print(f"bar{b0//4:3d} beat{b0:3d} t={beats[b0]:7.3f}  dB {eb[b0:b0+4].mean():6.1f}  low {vals[b0:b0+4].round(0)}")
