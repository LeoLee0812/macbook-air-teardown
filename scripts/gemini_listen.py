#!/usr/bin/env python3
# 让 Gemini（走 OpenLux）听一首配乐：有没有人声、曲式结构、情绪、结尾是否干净
# 用法：python3 scripts/gemini_listen.py <音频.mp3> [模型名]
# 注意：中转偶尔丢音频或编造分析，结论只作参考，卡点以 librosa 实测为准
import base64, json, re, sys, os, urllib.request

README = os.path.expanduser("~/Desktop/配置信息/云雾API-中转/README.md")
KEY = re.search(r"YUNWU_API_KEY=(sk-[A-Za-z0-9]+)", open(README, encoding="utf-8").read()).group(1)
path = sys.argv[1]
model = sys.argv[2] if len(sys.argv) > 2 else "gemini-3.1-pro-preview"
b64 = base64.b64encode(open(path, "rb").read()).decode()
prompt = (
    "请认真听这段音乐（它将用作一条约2分钟的 MacBook Air 3D 拆解科普视频的配乐，视频无旁白）。用中文回答：\n"
    "1. 全曲是否出现任何人声（唱词、哼唱、人声切片、说话声）？如有，给出大致时间段。没有就明确说没有。\n"
    "2. 按时间给出曲式结构（每段起止秒数、配器变化、能量高低）。\n"
    "3. 有没有明显的「重拍/drop/转折」时间点？列出来。\n"
    "4. 结尾是干净收束还是突然截断/淡出？\n"
    "5. 整体情绪和质感，适不适合精密、高级的科技产品拆解视频？有没有廉价感或混音问题？\n"
    "如果你没有收到音频，请直接回答「未收到音频」，不要编造。"
)
body = {
    "model": model,
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "input_audio", "input_audio": {"data": b64, "format": "mp3"}},
    ]}],
}
req = urllib.request.Request("https://api.openlux.ai/v1/chat/completions", data=json.dumps(body).encode(),
                             headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=300) as r:
    d = json.loads(r.read().decode())
print(d["choices"][0]["message"]["content"])
