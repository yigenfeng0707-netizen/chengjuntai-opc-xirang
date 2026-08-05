# 成军台 · 报名后下一周冲刺（8 月预赛准备）

> 状态：**已报名**（惠民 · AI+自选开放场景）  
> 目标：在 8 月预赛前具备「公网可访问 +（有 Key 时）真实 E2E + 视频/PPT 可交」  
> **执行主表（D1–D7 勾选）**：[`P0_WEEK_PLAN.md`](./P0_WEEK_PLAN.md) · 用户亲办：[`USER_ONLY_TODO.md`](./USER_ONLY_TODO.md)  
> **当前约束**：可用天翼云 ECS **免费试用**；**星辰 TokenHub / 息壤 Key 尚在等主办方** → 见双路径 [`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md)

## 双路径（并行，互不阻塞）

| 路径 | 本周动作 | 验收 |
|------|----------|------|
| **A** 天翼云试用 → 公网 Demo | 开试用 ECS、安全组、`deploy_to_ctyun.sh` | 公网 URL 可打开登录页；评委账号可用 |
| **B** 主办方 Token → primary LLM | 联系主办方要星辰/息壤 Key；到手后注入并重启 | 徽章显示息壤/星辰；`health_check` 的 `llm_providers=pass` |
| **Interim** | 有 SenseNova/百炼则开真实 E2E；否则结构 Demo + 显式无 Key 横幅 | 禁止静默 mock |

## 本周必做（按优先级）

| 日 | 事项 | 验收标准 | 谁做 |
|----|------|----------|------|
| D1 | **联系主办方要星辰/息壤 Token**（话术见 `CTYUN_TRIAL.md`） | 已发出请求；记录对接渠道 | **你** |
| D1 | 本地结构演示 / 可选 fallback E2E | 看板可开；有 SenseNova/百炼则真实战役，否则无 Key 横幅 | 本地脚本 + 你验证 |
| D2 | **Path A：天翼云试用 ECS 部署** | 公网 URL 可打开登录页；评委账号可用 | **你**（试用控制台）+ `DEPLOY天翼云.md` / `CTYUN_TRIAL.md` |
| D2–D3 | HTTPS / 改密 | 按 `PROD_HARDENING.md`；默认密码已改 | **你** |
| D3 | 录制 Demo 视频 | 有真实 Key（息壤或 interim fallback）再录正式成片；无 Key 只录结构预览并标注 | 你录 / 可用自动化辅助 |
| D4 | PPT 初稿 | 按 `PPT_OUTLINE.md` 12–15 页；含架构图与双战役截图 | 你 |
| D5 | 材料对齐提交口 | Demo URL、仓库链接写入 `STORE_REGISTRATION.md`；自检 `CHECKLIST.md` | 你 |
| Token 到手当日 | **Path B：切 primary 为息壤/星辰** | 徽章与周报模型字段为息壤/星辰 | 注入 Key + 重启 |
| D6–D7 | 预演 + 修 bug | 评委路径 60 秒可复现；备份战役数据 | 共同 |

## Key 配置（最短路径）

```powershell
# Path B（主办方发放后 —— 正式 primary）
$env:XIRANG_API_KEY="主办方发放的息壤或星辰Key"
# 可选：单独 TokenHub
$env:TOKENHUB_API_KEY="..."

# Interim（等 Token 期间的真实 E2E，可选）
$env:SENSENOVA_API_KEY="..."
$env:DASHSCOPE_API_KEY="..."

cd D:\APPs\天翼息壤杯\chengjuntai
scripts\start_local_demo.bat
python scripts\health_check.py
```

未配置任何 Key 时：看板会明确提示「无可用 LLM」，发起战役会报错——**这是预期行为**，禁止静默 mock。  
级联顺序：息壤/星辰 → TokenHub → SenseNova → 百炼（见 `config.yaml.example`）。

## 公网 Demo（Path A，现在就能做）

1. 试用中心开 ECS：https://www.ctyun.cn/act/trial/central （步骤见 `DEPLOY天翼云.md` §3）
2. 安全组放行 22/80/443，执行 `deploy_to_ctyun.sh`
3. Nginx 反代：`scripts/nginx_chengjuntai.conf`
4. 有 interim Key 则写入服务器环境变量或 `config.yaml`；**没有也先上线结构 Demo**
5. 把公网 URL 填回 `docs/STORE_REGISTRATION.md` 的「Demo 地址」
6. 主办方 Token 到手后再注入 `XIRANG_API_KEY` 并重启（Path B）

## 视频 / PPT

- 一周执行：`docs/P0_WEEK_PLAN.md`
- 脚本（含 60 秒点击表）：`docs/DEMO_VIDEO_SCRIPT.md`
- 演讲稿 15 页：`docs/PPT_SPEAKER_DECK.md` · HTML：`docs/PPT_SPEAKER_DECK.html`
- 大纲：`docs/PPT_OUTLINE.md`
- 成片要求：1080p、真实模型徽章（优先息壤/星辰；interim 可用 fallback 并在口播说明）、字幕含产品名与赛道；录前 **Ctrl+F5**

## 明确只有你能做的事

详见 [`USER_ONLY_TODO.md`](./USER_ONLY_TODO.md)：

- 开通天翼云 **试用** ECS、安全组放行、域名/HTTPS 证书（无需等 Token）
- **联系主办方**申请星辰 TokenHub / 息壤 API Key（勿提交到 Git；勿发隐私截图）
- 公网 **改默认密码**（口令只写本地 `ADMIN_ACCESS.local.md`）
- 若有商汤/百炼账号：可选配置 interim fallback 做真实 E2E
- 赛事后台上传证明材料、提交预赛交付物、填写公网 Demo 与仓库链接
- 录屏成片终审与 PPT 最终排版

## 仓库侧已就绪（可随时演示结构）

- 成军看板 + 双模板战役 + 人审 + 周报导出
- 一键启动：`scripts/start_local_demo.bat`
- 健康检查：`python scripts/health_check.py`
- 结构回归（显式 mock）：`python tests/test_campaign_core.py`
- 双路径说明：`docs/CTYUN_TRIAL.md`
