#!/usr/bin/env python3
# 用 OpenLux 的 whisper 转写音频，检查 TTS 读得对不对
import sys, os, re, json, subprocess
README = os.path.expanduser("~/Desktop/配置信息/云雾API-中转/README.md")
KEY = re.search(r"YUNWU_API_KEY=(sk-[A-Za-z0-9]+)", open(README, encoding="utf-8").read()).group(1)
def asr(path, model="whisper-1"):
    r = subprocess.run(["curl", "-sS", "--max-time", "120", "https://api.openlux.ai/v1/audio/transcriptions",
                        "-H", f"Authorization: Bearer {KEY}", "-F", f"file=@{path}", "-F", f"model={model}",
                        "-F", "language=zh", "-F", "response_format=json"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout).get("text", r.stdout)
    except Exception:
        return r.stdout[:300]
if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, "→", asr(p), flush=True)
