#!/usr/bin/env python3
# 用 Gemini（走 OpenLux）逐字转写音频（whisper 挂了时的替补）
import base64, json, os, re, sys, subprocess, urllib.request
README = os.path.expanduser("~/Desktop/配置信息/云雾API-中转/README.md")
KEY = re.search(r"YUNWU_API_KEY=(sk-[A-Za-z0-9]+)", open(README, encoding="utf-8").read()).group(1)
def transcribe(path, model="gemini-2.5-flash"):
    mp3 = path + ".mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-b:a", "64k", mp3], check=True)
    b64 = base64.b64encode(open(mp3, "rb").read()).decode()
    body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": [
        {"type": "text", "text": "逐字转写这段中文语音，只输出听到的原话（数字按读音写成阿拉伯数字也可以），不要解释。如果没有收到音频，只回答：未收到音频。"},
        {"type": "input_audio", "input_audio": {"data": b64, "format": "mp3"}}]}]}
    req = urllib.request.Request("https://api.openlux.ai/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode())
    os.remove(mp3)
    return d["choices"][0]["message"]["content"].strip()
if __name__ == "__main__":
    for p in sys.argv[1:]:
        try:
            print(p, "→", transcribe(p), flush=True)
        except Exception as e:
            print(p, "ERR", e, flush=True)
