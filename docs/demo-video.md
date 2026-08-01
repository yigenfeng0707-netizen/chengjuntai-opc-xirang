# 成军台 · 电影级演示视频（60 秒提交版）

官网限制：**≤1 分钟 · ≤100MB · mp4/mov/avi**（截止 8 月 20 日）。

## 产出

| 文件 | 说明 |
|------|------|
| `demo-output/Chengjuntai_demo_cinematic_60s.mp4` | 提交用成片（1080p30 · CRF17 · 硬烧字幕） |
| `demo.storyboard.json` | 分镜（可复跑） |

## 重跑

```powershell
# Web + NL2SQL 已启动后
powershell -File "$env:USERPROFILE\.cursor\skills\demo-video-factory\scripts\run_demo_video.ps1" `
  -Storyboard demo.storyboard.json

# 若仅微调时长：compose 后可用 ffmpeg -t 59.5 裁切
```

分镜对齐 `DEMO_VIDEO_SCRIPT.md` §A：评委 CTA → 样例产物 → Word → 问数。
