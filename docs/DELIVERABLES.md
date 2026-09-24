# 交付物指纹清单

> 由 `python scripts/record_deliverables.py` 生成，勿手工编辑。
> 生成时间：2026-09-24 08:33 · HEAD `ef6d734`

| 交付物 | 路径 | 体积 | 实测规格 | sha256(12) |
|---|---|---|---|---|
| 提交版演示视频 | `demo-video/out/demo-video-60s.mp4` | 5.74 MiB | 58.97s · 1920×1080 · h264 · 剪辑自母版 | `1b26281a16d9` |
| 母版演示视频 | `demo-video/out/demo-video.mp4` | 8.50 MiB | 71.02s · 1920×1080 · h264 · 13 镜 · 2129 帧 @30fps | `da15e6c386e5` |
| 预赛答辩 PPT | `docs/成军台_息壤杯预赛答辩.pptx` | 1.64 MiB | 15 页 · pptx | `607171680352` |

## 说明

- `demo-video/out/*.mp4` 被 `.gitignore` 排除，**仅存本地 + GitHub Release 归档**（见 `docs/OUTCOME.md`）。
- 提交版 = 59s 合规剪辑；母版 = 完整 13 分镜，含更多讲解，不用于官方提交。
