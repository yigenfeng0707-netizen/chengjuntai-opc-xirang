# 成军台 · 赛事结果与资源台账

> 建立于 2026-09-24。用途：一处看清「交了没有 / 结果如何 / 还有什么在计费或会到期」。
> 交付物指纹见 `docs/DELIVERABLES.md`；部署操作见 `DEPLOY天翼云.md`。

## 1. 赛事状态

| 项 | 状态 | 依据 |
|---|---|---|
| 报名 | 已完成 | `README.md:26`「报名状态：已报名」 |
| 赛道 | 惠民产品创新 / AI+自选开放场景 | `docs/delivery-notes.md:4` |
| 官方截止 | 2026-08-20 | `docs/delivery-notes.md:3` |
| 材料就绪 | 已就绪（视频 58.97s + PPT 15 页 + 公网 Demo + 仓库） | 2026-09-24 实测 |
| **Store 实际上传** | **待核实** —— 登录 https://ai.js.189.cn/OPCCompetition/OPCOutFiles 查「我的作品」；`docs/SUBMISSION_CHECKLIST.html` 明确记录 Agent 无法代登，故仓库内无回执 | 用户本人 |
| **8/11 聚能湾答辩结果** | **待核实** —— 仓库内无任何晋级/淘汰记录 | 用户本人 / 赛事通知 |
| 复赛 / 决赛安排 | **待核实** | 赛事通知 |
| 归档方式 | **不另建 Release**（2026-09-24 用户裁决）：三件交付物中两件已在公开仓 git 历史内，第三件可重渲染，且本机仅一块物理盘 | Task 3 |

自评快照（不作为当前结论）：五维 89/A（2026-08-06），最低项为商业模式 7.75。

## 2. 在跑的资源与到期日

| 资源 | 现状（2026-09-24 实测） | 到期 / 需动作 |
|---|---|---|
| 天翼云 ECS | `https://opcopcos.cn:8088/` → 200；`/api/v1/health` → 401（鉴权，正常） | **试用到期日待核实**（天翼云控制台 → 云主机）。`docs/archive/APPLY_ECS_TOKEN.md` 建议授权覆盖至复赛/决赛 + 7~14 天 |
| Let's Encrypt 证书 | `notAfter = 2026-11-08 06:27:26 UTC`（剩约 45 天） | 若需继续对外演示，确认服务器上的 certbot 续期定时任务仍生效 |
| 3 个 systemd 服务 | `teleagent-backend` / `teleagent-mcp` / `teleagent-web` | 停服即断公网 Demo；不再需要时按 `DEPLOY天翼云.md` §9 下线并释放 |
| LLM 主链路 Token | 息壤/星辰为正式口径，级联含壁韧/SenseNova 兜底 | 试用 Token 到期日待核实 |
| 本地密钥 | `content_factory/config.yaml`（含 api_token / web 口令），已 gitignore，9/7 有改动 | 不外发；轮换见 `docs/SECURITY_KEY_ROTATION.md` |
| 公开仓内的明文口令 | `docs/LOCAL_DEMO.md:32-33` 以明文写出演示账号 `admin` / `judge` 的口令；仓库 public，历史提交同样留痕 | **未处置（用户动作）**：先服务器上轮换 `users.json` 里这两个口令 → 再清理该文档。只改文档不轮换＝无效 |

## 3. 归档与恢复

- 归档结论（2026-09-24）：**不建 GitHub Release**。理由三条，均可复核：
  1. 提交版视频（blob `dcd977f6`，6,019,286 B）与答辩 PPT 自 `69f448a`（2026-08-10）起就被 git 跟踪，已随 public 仓存在于 GitHub —— 防丢失价值由 git 历史承担；
  2. 母版 `demo-video/out/demo-video.mp4`（71.02s / 13 分镜）理论上可重建，但**不是零成本**：分镜脚本与画面代码在仓内（`demo-video/src/Root.tsx` + `demo-video/public/shots.json`），而 `docs/delivery-notes.md`「视频重跑」调用的合成脚本在**仓库之外**（用户主目录下的 demo-video-factory 技能），且需要一次能正常跑的演示来录制。所以母版丢了能重建，但重建工具不在版本控制里。
  3. 本机 C: 与 D: 同在 **Disk 0**（一块物理盘），同机任何「另存一份」副本都不构成异地备份，只会制造伪安全感。
- 仍欠的归档动作（备份侧收尾项；安全侧另有 §2 明文口令一项）：本机只有 Disk 0 一块物理盘，母版视频与 `content_factory/config.yaml`（含密钥）都是**单副本**。要做真异地副本，外接盘 / 网盘 / 私有仓任选其一，落地后用 `certutil -hashfile <文件> SHA256` 与 `docs/DELIVERABLES.md` 的 sha256(12) 前缀比对。同机换目录不算备份。
- 冻结点：`5915737`（2026-08-11 08:40 +0800，即预赛最后一次代码提交）
- 重跑视频 / PPT：`docs/delivery-notes.md`「视频重跑」「PPT 重生成」两节
- 官方提交规格复核：视频 ≤60s、1920×1080、h264+aac、≤100MB —— 提交版 4 项全合规

## 4. 休眠与重启

最后一次代码提交 2026-08-11，至 2026-09-24 无活动。重启本地演示：
`scripts/start_local_demo.bat` → http://127.0.0.1:8090（评委 60 秒体验路径见 `README.md`）。
先跑 `python scripts/health_check.py` 与 `python tests/test_campaign_core.py`（mock 回归的产物写进临时目录，不会污染 `data/`、`articles/` 与本机检索索引，口径见 `README.md`「无 Key 状态机回归」）。
