#!/bin/zsh
# 收尾：序列帧 → teardown.mp4 → HyperFrames 合成渲染 → 换上母带配乐 → 两个旁白版
# 用法：zsh scripts/finalize.sh [--skip-encode] [--skip-render]
set -e
ROOT=${0:A:h}/..
cd $ROOT
OUT=$ROOT/out
mkdir -p $OUT

if [[ "$*" != *--skip-encode* ]]; then
  echo "== 编码 3D 序列帧"
  ffmpeg -v error -y -framerate 30 -start_number 0 -i render/frames/f%05d.jpg -frames:v 3696 \
    -c:v libx264 -preset slow -crf 14 -pix_fmt yuv420p -movflags +faststart video/assets/teardown.mp4
  ffprobe -v error -show_entries format=duration:stream=nb_frames -of compact video/assets/teardown.mp4
fi

echo "== 母带配乐：-14 LUFS / -1 dBTP"
ffmpeg -v error -y -i music/bed.wav -af "loudnorm=I=-14:TP=-1:LRA=9" -ar 48000 -t 123.21 $OUT/music_master.wav

if [[ "$*" != *--skip-render* ]]; then
  echo "== HyperFrames 渲染"
  (cd video && npx hyperframes render --quality delivery --output $OUT/hf_render.mp4)
fi

echo "== 纯配乐版：换上母带配乐"
ffmpeg -v error -y -i $OUT/hf_render.mp4 -i $OUT/music_master.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k \
  -shortest -movflags +faststart "$OUT/MacBookAir拆解-纯配乐版.mp4"

for v in next flash; do
  if [[ -f tts/$v/mix_$v.wav ]]; then
    echo "== 旁白版：$v"
    ffmpeg -v error -y -i $OUT/hf_render.mp4 -i tts/$v/mix_$v.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k \
      -shortest -movflags +faststart "$OUT/MacBookAir拆解-旁白版-${v:u}.mp4"
  fi
done
ls -la $OUT
