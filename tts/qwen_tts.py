#!/usr/bin/env python3
# 千问 TTS（阿里云百炼 DashScope）：qwen-audio-3.1-tts-next / qwen-audio-3.1-tts-flash
# 接口：POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer
#   flash：input.voice 用拼音音色 ID（如 xunanchuan_v3.1），可加 input.instruction 控制语气
#   next ：要念的文字放 input.text_prompt（必填）；input.text 放声音/语气描述；可同时指定 voice
#         （实测：只给 text 不给 text_prompt 会报错；把描述放 text_prompt 会念一段自动生成的试听句）
# 返回 output.audio.url（24 小时有效的 wav），国内 OSS 直连下载
# 密钥运行时从 ~/Desktop/配置信息/千问TTS-qwen-audio-3.1.md 读取，不写进仓库
import json, os, re, sys, time, urllib.request

URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"
KEYFILE = os.path.expanduser("~/Desktop/配置信息/千问TTS-qwen-audio-3.1.md")
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 阿里云国内节点直连


def key():
    return re.search(r"DASHSCOPE_API_KEY=(\S+)", open(KEYFILE, encoding="utf-8").read()).group(1)


def synth(model, text, out_wav, voice=None, text_prompt=None, instruction=None, sample_rate=24000, tries=4):
    """text 是要念的文字；text_prompt 是语气描述（next 模型会自动把两者放到正确字段）"""
    inp = {"text": text, "format": "wav", "sample_rate": sample_rate}
    if voice:
        inp["voice"] = voice
    if "next" in model:
        inp["text_prompt"] = text            # next：念的内容
        inp["text"] = text_prompt or text     # next：风格描述
    elif text_prompt:
        inp["text_prompt"] = text_prompt
    if instruction:
        inp["instruction"] = instruction
    body = json.dumps({"model": model, "input": inp}).encode()
    last = None
    for i in range(tries):
        t0 = time.time()
        req = urllib.request.Request(URL, data=body, headers={"Authorization": "Bearer " + key(), "Content-Type": "application/json"})
        try:
            with OP.open(req, timeout=180) as r:
                d = json.loads(r.read().decode())
            url = d["output"]["audio"]["url"]
            with OP.open(url, timeout=120) as r:
                open(out_wav, "wb").write(r.read())
            return dict(ok=True, secs=round(time.time() - t0, 2), usage=d.get("usage"), request_id=d.get("request_id"))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(2 + 3 * i)
    return dict(ok=False, error=last)


if __name__ == "__main__":
    model, text, out = sys.argv[1], sys.argv[2], sys.argv[3]
    voice = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
    prompt = sys.argv[5] if len(sys.argv) > 5 else None
    print(json.dumps(synth(model, text, out, voice=voice, text_prompt=prompt), ensure_ascii=False))
