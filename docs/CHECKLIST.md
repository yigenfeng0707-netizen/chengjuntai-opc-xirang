# 提交前自检清单（质量门禁）

> 报名阶段：**已报名**（惠民 · AI+自选开放场景）  
> **执行主表**：[`P0_WEEK_PLAN.md`](./P0_WEEK_PLAN.md)（D1–D7）  
> 用户亲办：[`USER_ONLY_TODO.md`](./USER_ONLY_TODO.md) · 双路径：[`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md) · 冲刺摘要：[`NEXT_SPRINT.md`](./NEXT_SPRINT.md)

## 里程碑

- [x] 赛事报名提交（惠民 / AI+自选开放场景）
- [ ] **Path A**：天翼云试用公网 Demo + HTTPS/改密（可先于竞赛 Token）
- [ ] 已联系主办方申请星辰/息壤 Token
- [ ] **Path B / Interim**：真实 Key 端到端（息壤优先；SenseNova/百炼可过渡）
- [ ] 3 分钟演示视频成片（点击表见 `DEMO_VIDEO_SCRIPT.md`）
- [ ] PPT 12–15 页可答辩（`PPT_SPEAKER_DECK.md` / `.html`）
- [ ] 「评委 60 秒体验」公网可走通（零讲解）
- [ ] 预赛提交口材料齐全（Demo URL / 仓库 / 文档）

## 产品

- [ ] 成军看板可完成「AI获客跟进」端到端（真实 LLM；interim fallback 亦可）
- [ ] 第二模板「行业综述」可发起
- [ ] 人审通过/驳回可用
- [ ] 成军周报可导出
- [ ] 模型徽章：预赛成片优先显示息壤/星辰（Token 到手后）
- [ ] 无 Key 时明确报错 + 橙色横幅，无静默 mock（演示账号）

## 安全与生产

- [ ] config.yaml / users.json 未提交真实密钥
- [ ] 默认密码已修改
- [ ] 评委只读账号可用
- [ ] HTTPS 或赛事可接受的公网 Demo
- [ ] `python scripts/health_check.py` 中结构项通过；有 Key 时 `llm_providers` 与 `demo_ready` 通过

## 材料

- [ ] PROJECT_DOC / PPT / 视频 / README 评委路径一致（均指向 60 秒 CTA）
- [ ] `STORE_REGISTRATION.md` 已填公网 Demo 与仓库链接
- [ ] 智云 Store 赛道勾选正确（惠民 · AI+自选）
- [ ] 仓库公开或按赛事要求授权评委访问
- [ ] 密钥与改密后账号未提交 Git；口令仅存 `ADMIN_ACCESS.local.md`
