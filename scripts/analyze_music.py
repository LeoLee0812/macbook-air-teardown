#!/usr/bin/env python3
# 量配乐：BPM、拍点、每小节能量、段落边界；用来挑曲子和定分镜卡点
# 用法：.venv/bin/python scripts/analyze_music.py music/raw/*.m4a [--json out.json]
import json, sys
import numpy as np
import librosa


def analyze(path):
    y, sr = librosa.load(path, sr=22050, mono=True)
    dur = len(y) / sr
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time", tightness=120)
    tempo = float(np.atleast_1d(tempo)[0])
    # 用拍间隔中位数复核 BPM
    ibi = np.diff(beats)
    bpm_med = 60.0 / float(np.median(ibi)) if len(ibi) else tempo
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    t_rms = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
    # 每 2 秒能量（dB）
    edges = np.arange(0, dur + 2, 2.0)
    prof = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (t_rms >= a) & (t_rms < b)
        v = float(np.mean(rms[m])) if m.any() else 0.0
        prof.append(20 * np.log10(v + 1e-6))
    # 段落：MFCC+chroma 的 agglomerative 分段
    hop = 512
    mf = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop)
    ch = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    feat = np.vstack([librosa.util.normalize(mf, axis=1), ch])
    feat = librosa.util.sync(feat, librosa.time_to_frames(beats, sr=sr, hop_length=hop), aggregate=np.median)
    k = 9
    try:
        bounds = librosa.segment.agglomerative(feat, k)
        seg_t = [0.0] + [float(beats[min(i, len(beats) - 1)]) for i in bounds[1:]]
    except Exception:  # noqa: BLE001
        seg_t = []
    # 起始静音、结尾形态
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    first_beat = float(beats[0]) if len(beats) else 0.0
    return {
        "file": path, "duration": round(dur, 2), "bpm_track": round(tempo, 2), "bpm_median": round(bpm_med, 2),
        "first_beat": round(first_beat, 3), "n_beats": int(len(beats)),
        "beats": [round(float(b), 3) for b in beats],
        "energy_db_2s": [round(p, 1) for p in prof],
        "segments": [round(s, 2) for s in seg_t],
        "onset_mean": round(float(np.mean(onset_env)), 3),
    }


def bar(db, lo=-45, hi=-8):
    n = int(max(0, min(1, (db - lo) / (hi - lo))) * 30)
    return "█" * n


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = None
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        args = [a for a in args if a != out]
    res = []
    for p in args:
        r = analyze(p)
        res.append(r)
        print(f"\n=== {p}\n时长 {r['duration']}s  BPM(track) {r['bpm_track']}  BPM(中位拍距) {r['bpm_median']}  首拍 {r['first_beat']}s  拍数 {r['n_beats']}")
        print("段落边界(s):", r["segments"])
        for i, db in enumerate(r["energy_db_2s"]):
            print(f"  {i*2:5.0f}s {db:6.1f} {bar(db)}")
    if out:
        json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
