#!/usr/bin/env python3
# 把抽帧图拼成带时间标注的联系表
import sys, os, glob
from PIL import Image, ImageDraw, ImageFont
d, out = sys.argv[1], sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 4
fs = sorted(glob.glob(os.path.join(d, "f*.png")))
ims = [Image.open(f) for f in fs]
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w, rows * (h + 24)), (30, 30, 30))
dr = ImageDraw.Draw(sheet)
fnt = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 16)
for i, (f, im) in enumerate(zip(fs, ims)):
    x, y = (i % cols) * w, (i // cols) * (h + 24)
    sheet.paste(im, (x, y + 24))
    fr = int(os.path.basename(f)[1:6])
    dr.text((x + 6, y + 3), f"{fr/30:6.2f}s  f{fr}", fill=(230, 230, 230), font=fnt)
sheet.save(out)
print(out, sheet.size)
