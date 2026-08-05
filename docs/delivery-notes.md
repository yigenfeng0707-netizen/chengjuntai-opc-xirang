# 成军台 · 预赛提交速记

> 官网截止：**2026-08-20**  
> 赛道：惠民产品创新 · AI+自选开放场景  
> 入口：https://ai.js.189.cn/OPCCompetition  
> **主仓（唯一）**：https://github.com/yigenfeng0707-netizen/chengjuntai-opc-xirang  
> 勿将 `bidding-intelligence-assistant` / `opc-builder-bid-ai` 填为 Demo 或代码主链接（见 `REPO_COMPARISON.md`）。

## 必交两项

| 项 | 本地路径 | 规格 |
|----|----------|------|
| 演示视频 | `demo-output/Chengjuntai_demo_cinematic_60s.mp4`（及 `_submit` 同内容） | **59.5s** · ~8MB · 1080p30 · 硬烧字幕 |
| 答辩 PPT | `docs/成军台_息壤杯预赛答辩.pptx` | 13 页 · 图文并茂 · ~1.5MB · pptx |

## 视频重跑

```powershell
# 1) 启动 Web +（建议）NL2SQL
cd D:\APPs\天翼息壤杯\chengjuntai
scripts\start_local_demo.bat
scripts\start_nl2sql_demo.bat

# 2) 电影级合成（storyboard 已按 60s 官方限时）
powershell -File "$env:USERPROFILE\.cursor\skills\demo-video-factory\scripts\run_demo_video.ps1" `
  -Storyboard demo.storyboard.json
```

仅重合成（不重录）：

```powershell
python "$env:USERPROFILE\.cursor\skills\demo-video-factory\scripts\compose_demo_video.py" `
  --storyboard demo.storyboard.json
```

## PPT 重生成

```powershell
# Pillow 静帧 → assets/ppt/*.png，再嵌入 pptx
python scripts\build_contest_pptx.py --render
# 仅重打 pptx（已有 assets/ppt）
python scripts\build_contest_pptx.py
```

## 附加字段（若后台有）

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/yigenfeng0707-netizen/chengjuntai-opc-xirang |
| Demo | 天翼云公网 URL（部署后填） |
| 口号 | 息壤育智 · 一人成军 |
| 模型口播 | 息壤 primary（wishub-x6）；勿声称 mock |

## 验收

```powershell
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate `
  -of default=noprint_wrappers=1 demo-output\Chengjuntai_demo_cinematic_60s.mp4
```

期望：时长 ≤60s，1920×1080，h264+aac，文件 ≤100MB。

## 全局可复用 Skill

本次预赛交付流程已沉淀为 Cursor Agent Skill（本体不在本仓）：

`~/.cursor/skills/xirang-opc-contest-deliver/`（Windows：`%USERPROFILE%\.cursor\skills\xirang-opc-contest-deliver\`）

触发词示例：息壤杯、OPC、预赛提交、60秒视频、电影级、答辩PPT、图文并茂、Store上传、一人成军。
