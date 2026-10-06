#!/usr/bin/env python3
# 每小节分频段能量（低/中/高）+ 拍内 kick 规律性，确认段落边界
import sys, json, numpy as np, librosa
y, sr = librosa.load(sys.argv[1], sr=22050)
g = json.load(open("music/beatgrid.json"))
P, ph = g["period"], g["phase"]
hop = 256
S = np.abs(librosa.stft(y, n_fft=4096, hop_length=hop))**2
f = librosa.fft_frequencies(sr=sr, n_fft=4096)
t = librosa.times_like(S, sr=sr, hop_length=hop)
bands = {"sub<90": f<90, "low90-250": (f>=90)&(f<250), "mid250-2k": (f>=250)&(f<2000), "hi2k-8k": (f>=2000)&(f<8000), "air>8k": f>=8000}
E = {k: 10*np.log10(S[m].sum(axis=0)+1e-9) for k,m in bands.items()}
# 低频 onset：kick 检测（sub 段谱通量）
sub = S[f<120].sum(axis=0); flux = np.maximum(0, np.diff(np.log1p(sub), prepend=0))
nb = int((len(y)/sr - ph)/(4*P))
print("bar  start   " + "  ".join(f"{k:>9s}" for k in bands) + "   kick/beat")
for b in range(nb+1):
    a = ph + b*4*P; z = a + 4*P
    m = (t>=a)&(t<z)
    vals = [E[k][m].mean() for k in bands]
    # 每拍位置的 sub 通量峰值
    kb = []
    for j in range(4):
        bt = a + j*P; mm = (t>=bt-0.04)&(t<bt+0.06)
        kb.append(flux[mm].max() if mm.any() else 0)
    print(f"{b:3d} {a:7.3f}  " + "  ".join(f"{v:9.1f}" for v in vals) + "   " + " ".join(f"{x:4.2f}" for x in kb))
