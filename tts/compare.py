#!/usr/bin/env python3
# Next vs Flash 对比：合成耗时、语速、需要提速的段数、whisper 字错率、响度、Gemini 听感评测
# 用法：python3 tts/compare.py   → 输出 tts/compare.json 和 tts/compare.md
import base64, json, os, re, subprocess, statistics, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
N = json.load(open(os.path.join(HERE, "narration.json")))
README = os.path.expanduser("~/Desktop/配置信息/云雾API-中转/README.md")


def load(p, default=None):
    try:
        return json.load(open(p))
    except Exception:  # noqa: BLE001
        return default


def lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
    return (float(m[-1]) if m else None, float(p[-1]) if p else None)


def chars(t):
    return len(re.sub(r"[\s，。、：；！？,.·]", "", t))


def gemini_listen(path_a, path_b):
    """两段旁白样本一起发给 Gemini，请它盲评（A/B 不告诉是哪个模型）"""
    key = re.search(r"YUNWU_API_KEY=(sk-[A-Za-z0-9]+)", open(README, encoding="utf-8").read()).group(1)
    content = [{"type": "text", "text": (
        "下面有两段中文旁白录音 A 和 B，文案完全相同，都是同一个音色，只是 TTS 模型不同。请当专业配音导演盲评："
        "1) 自然度/像真人的程度；2) 吐字清晰度；3) 节奏和停顿；4) 有没有吞字、读错、怪音、机械感；"
        "5) 哪段更适合高端科技产品拆解视频。每项给 A、B 各打 1-10 分并说明理由，最后给总评。"
        "如果没收到音频就直接说没收到，不要编。")}]
    for tag, p in (("A", path_a), ("B", path_b)):
        mp3 = p + ".cmp.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-t", "45", "-ac", "1", "-b:a", "64k", mp3], check=True)
        content.append({"type": "text", "text": f"录音 {tag}："})
        content.append({"type": "input_audio", "input_audio": {"data": base64.b64encode(open(mp3, "rb").read()).decode(),
                                                                "format": "mp3"}})
        os.remove(mp3)
    body = {"model": "gemini-3.1-pro-preview", "temperature": 0.2, "messages": [{"role": "user", "content": content}]}
    req = urllib.request.Request("https://api.openlux.ai/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode())["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        return f"（Gemini 评测失败：{e}）"


out = {}
for which in ("next", "flash"):
    rep = load(os.path.join(HERE, which, "report.json"), [])
    lay = load(os.path.join(HERE, which, "layout.json"), [])
    ver = load(os.path.join(HERE, f"verify_{which}.json"), [])
    dur = load(os.path.join(HERE, which, "trim", "durations.json"), {})
    secs = [r["secs"] for r in rep if r.get("secs")]
    total_speech = sum(dur.values())
    total_chars = sum(chars(s["text"]) for s in N["segments"])
    vo = os.path.join(HERE, which, "vo.wav")
    li, pk = lufs(vo) if os.path.exists(vo) else (None, None)
    out[which] = dict(
        model=f"qwen-audio-3.1-tts-{which}",
        segments=len(N["segments"]),
        synth_secs_avg=round(statistics.mean(secs), 2) if secs else None,
        synth_secs_total=round(sum(secs), 1) if secs else None,
        speech_secs=round(total_speech, 2),
        chars_per_sec=round(total_chars / total_speech, 2) if total_speech else None,
        sped_up=sum(1 for L in lay if L["tempo"] > 1.001),
        max_tempo=max([L["tempo"] for L in lay], default=1.0),
        overflow=sum(1 for L in lay if L["over"] > 0.01),
        cer_avg=round(statistics.mean([v["cer"] for v in ver]), 3) if ver else None,
        cer_bad=[dict(id=v["id"], cer=v["cer"], hyp=v["hyp"]) for v in ver if v["cer"] >= 0.15],
        vo_lufs=li, vo_peak=pk,
    )
def sample(which, ids=("s01", "s03", "s06", "s07", "s12", "s15", "s18", "s21")):
    """挑几段有代表性的旁白，中间隔 0.5 秒拼成一条评测样本"""
    files = [os.path.join(HERE, which, "trim", i + ".wav") for i in ids]
    inp, fl = [], []
    for k, f in enumerate(files):
        inp += ["-i", f]
        fl.append(f"[{k}:a]apad=pad_dur=0.5[p{k}]")
    fl.append("".join(f"[p{k}]" for k in range(len(files))) + f"concat=n={len(files)}:v=0:a=1[o]")
    dst = os.path.join(HERE, which, "sample.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + inp + ["-filter_complex", ";".join(fl), "-map", "[o]", dst], check=True)
    return dst


a = sample("next") if os.path.exists(os.path.join(HERE, "next", "trim")) else ""
b = sample("flash") if os.path.exists(os.path.join(HERE, "flash", "trim")) else ""
if os.path.exists(a) and os.path.exists(b) and "--no-gemini" not in sys.argv:
    # 截取旁白最密的前 40 秒（从第一段开始）
    out["gemini_blind_AB"] = {"A": "next", "B": "flash", "review": gemini_listen(a, b)}
json.dump(out, open(os.path.join(HERE, "compare.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
