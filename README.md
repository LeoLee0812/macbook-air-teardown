# MacBook Air 拆解视频

M5 MacBook Air（13 英寸）的 3D 拆解科普片：按 Apple 官方维修手册的顺序，一件件拆开讲解每个零件。纯配乐版 + 千问 TTS 两个旁白版（Next / Flash）。

## 目录

- `blender/`：程序化建模和拆解动画（`layout.py` 尺寸数据 → `model.py` 建模 → `anim.py` 动画编排 → `render_frames.py` 逐帧渲染 → `export_anchors.py` 导出标注锚点）
- `scripts/`：配乐分析（BPM/段落）、叠加层生成（`build_overlay.py`）、收尾出片（`finalize.sh`）
- `video/`：HyperFrames 合成工程（3D 画面 + 章节卡 + 跟随零件的标注 + 配乐）
- `tts/`：旁白文案、两个模型的合成/挑选/核对/混音脚本、对比结论 `TTS对比.md`
- `music/`：Suno 生成的配乐与节拍分析

## 重建

```bash
.venv/bin/python blender/textures.py all
blender -b --factory-startup --python blender/build.py -- --no-anim --out blender/model.blend
blender -b blender/model.blend --python blender/build_anim.py -- --out blender/macbook.blend
blender -b blender/macbook.blend --python blender/render_frames.py -- render/frames 0 3695 32
blender -b blender/macbook.blend --python blender/export_anchors.py
.venv/bin/python scripts/build_overlay.py
zsh scripts/finalize.sh
```
