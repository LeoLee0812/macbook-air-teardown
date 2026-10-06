#!/usr/bin/env python3
# 通过 OpenLux 中转调用 Suno 生成纯音乐配乐
# 用法：
#   python3 scripts/suno_gen.py submit <标签名> <风格预设名>
#   python3 scripts/suno_gen.py fetch  <标签名> <task_id>      # 续查已提交的任务
# 密钥运行时从 ~/Desktop/配置信息/云雾API-中转/README.md 读取，不写进仓库
import json, os, re, subprocess, sys, time, urllib.request

BASE = "https://api.openlux.ai"
README = os.path.expanduser("~/Desktop/配置信息/云雾API-中转/README.md")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "music", "raw")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

NEG = ("vocals, voice, singing, choir, lyrics, spoken word, rap, humming, vocal chops, "
       "aggressive, distorted guitar, heavy metal, dubstep, trap")

# 曲式：安静开场 → 起拍 → 稳定律动（逐个零件）→ 高潮（总爆炸图）→ 收尾
STRUCTURE = """[Instrumental]
[Intro: soft ticking metallic percussion, single warm analog synth pulse, airy pad, mysterious]
[Build: arpeggiated synth enters, deep sub bass, light kick drum]
[Verse: steady precise groove, glassy plucks, clean electronic drums, mechanical clicks]
[Verse 2: add soft piano motif, brighter, more movement]
[Breakdown: pads and piano, tension rising]
[Chorus: full arrangement, wide warm synth chords, uplifting, cinematic]
[Outro: elements drop out, single piano note, long reverb tail]
[End]"""

PRESETS = {
    "precise": "minimal cinematic electronic, precise ticking percussion, warm analog synth arpeggios, "
               "deep sub bass, glassy plucks, soft piano motif, modern tech product launch, clean, elegant, "
               "inspiring, 120 BPM, instrumental",
    "glass": "ambient electronica, crystalline mallets, pulsing synth bass, delicate glitch percussion, "
             "felt piano, cinematic swells, futuristic design film, calm confidence, 118 BPM, instrumental",
}


def key():
    m = re.search(r"YUNWU_API_KEY=(sk-[A-Za-z0-9]+)", open(README, encoding="utf-8").read())
    return m.group(1)


def req(method, path, body=None, tries=5):
    # 中转偶发 SSL EOF，带重试
    for i in range(tries):
        try:
            data = json.dumps(body).encode() if body is not None else None
            r = urllib.request.Request(BASE + path, data=data, method=method, headers={
                "Authorization": "Bearer " + key(), "Content-Type": "application/json", "User-Agent": UA})
            with urllib.request.urlopen(r, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:  # noqa: BLE001
            print("请求失败，重试:", e, flush=True)
            time.sleep(4 + i * 3)
    raise SystemExit("请求多次失败")


def poll(name, task):
    d = {}
    for _ in range(90):
        f = req("GET", "/suno/fetch/" + task)
        d = f.get("data") or {}
        st = d.get("status")
        print("status:", st, d.get("progress"), flush=True)
        if st in ("SUCCESS", "FAILURE"):
            break
        time.sleep(10)
    os.makedirs(OUT, exist_ok=True)
    json.dump(d, open(os.path.join(OUT, f"{name}.json"), "w"), ensure_ascii=False, indent=2)
    if d.get("status") != "SUCCESS":
        raise SystemExit("失败: " + str(d.get("fail_reason")))
    for i, clip in enumerate(d.get("data") or []):
        url = clip.get("cld2AudioUrl") or clip.get("audio_url")
        ext = os.path.splitext(url.split("?")[0])[1] or ".mp3"
        dst = os.path.join(OUT, f"{name}-{i}{ext}")
        # CDN 会拦 Python 默认 UA，用 curl 带浏览器 UA 下载；国内 CDN 直连不走代理
        env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}
        cmd = ["curl", "-sSL", "--retry", "3", "--max-time", "120", "-A", UA, "-o", dst, url]
        if subprocess.run(cmd, env=env).returncode != 0:  # 直连失败再走代理
            subprocess.run(cmd, check=True)
        print(f"clip {i}: {clip.get('title')} | {clip.get('duration')}s | {clip.get('tags')} -> {dst}", flush=True)


def main():
    mode, name = sys.argv[1], sys.argv[2]
    if mode == "fetch":
        poll(name, sys.argv[3])
        return
    tags = PRESETS[sys.argv[3]]
    body = {"mv": "chirp-fenix", "title": "Inside, Part by Part", "tags": tags, "negative_tags": NEG,
            "make_instrumental": True, "prompt": STRUCTURE}
    sub = req("POST", "/suno/submit/music", body)
    print("submit:", json.dumps(sub, ensure_ascii=False), flush=True)
    if sub.get("code") != "success" or not sub.get("data"):
        raise SystemExit(1)
    time.sleep(20)
    poll(name, sub["data"])


if __name__ == "__main__":
    main()
