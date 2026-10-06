#!/usr/bin/env python3
# 两个 TTS 版本逐段转写，和文案比对字错率（CER），结果写 tts/verify_<版本>.json
# 默认用本地 faster-whisper（large-v3-turbo，模型走 hf-mirror 下载），两个版本用同一个识别器，结果可复现
# 用法：.venv/bin/python tts/verify.py next|flash
import json, os, re, sys, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
N = json.load(open(os.path.join(HERE, "narration.json")))
CN_NUM = {"0": "零", "1": "一", "2": "二", "3": "三", "4": "四", "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"}
T2S = str.maketrans("這們個電觸機鍵盤螺絲體結構攝頭風擴導熱塊顯幕剩頂殼換須輕層讓來後兩側線裡麵組膠著無還碟簡樣聲揚鉸鏈開蓋盤斷動麼與萬",
                    "这们个电触机键盘螺丝体结构摄头风扩导热块显幕剩顶壳换须轻层让来后两侧线里面组胶着无还碟简样声扬铰链开盖盘断动么与万")


def norm(s):
    s = s.translate(T2S).replace("Ｍ", "M").upper()
    s = re.sub(r"[\s，。、：:；;！!？?,.·\-—（）()「」“”\"'…]", "", s)
    s = re.sub(r"\d", lambda m: CN_NUM[m.group(0)], s)        # 数字统一成逐位汉字
    for ch in "十百千万":
        s = s.replace(ch, "")
    return s


def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    sm = difflib.SequenceMatcher(None, r, h)
    errs = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
    return errs / max(1, len(r))


_MODEL = None


def local_asr(path):
    global _MODEL
    if _MODEL is None:
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    import librosa
    audio, _ = librosa.load(path, sr=16000, mono=True)   # 自己解码，绕开 PyAV 版本不兼容
    segs, _ = _MODEL.transcribe(audio, language="zh", beam_size=5, initial_prompt="以下是普通话的句子。",
                                vad_filter=False, condition_on_previous_text=False)
    return "".join(s.text for s in segs).strip()


def main():
    which = sys.argv[1]
    rows = []
    for seg in N["segments"]:
        p = os.path.join(HERE, which, "trim", seg["id"] + ".wav")
        hyp = local_asr(p)
        c = cer(seg["text"], hyp)
        rows.append(dict(id=seg["id"], ref=seg["text"], hyp=hyp, cer=round(c, 3)))
        print(f"{seg['id']} CER {c:.2f} | {hyp}", flush=True)
    json.dump(rows, open(os.path.join(HERE, f"verify_{which}.json"), "w"), ensure_ascii=False, indent=1)
    print("平均字错率", round(sum(r["cer"] for r in rows) / len(rows), 3))


if __name__ == "__main__":
    main()
