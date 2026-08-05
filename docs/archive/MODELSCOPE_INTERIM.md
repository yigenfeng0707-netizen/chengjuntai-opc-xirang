# ModelScope（魔搭）临时说明

> **竞赛主路径不是 ModelScope。** 息壤杯公网 Demo / Store 以 **天翼云 ECS** 为准。

## 结论（先读这句）

- **不要把魔搭当正式参赛部署。** 等天翼云试用 / ECS 审批通过后再按 `DEPLOY天翼云.md` + `docs/CTYUN_TRIAL.md` 上线。
- 若仅本地联调或临时给内部分享，可用魔搭单端口托管，但需接受：**单端口、冷启动、与天翼云评测环境不一致** 等限制。
- Store / 赛事后台 **Demo URL 仍填天翼云公网地址**；魔搭链接最多作 interim 备注，不作主提交。

## 何时可以碰魔搭

| 场景 | 是否建议 |
|------|----------|
| 本地无公网、仅同事内网看一眼 | 可选 interim |
| 正式评委 / Store / 冲奖主链接 | **否** → 等 ECS |
| CI 镜像预览 | 可选，勿写进报名主表 |

## 操作提示（若坚持 interim）

1. 确认无密钥进仓：只用环境变量 / 平台密钥注入，勿提交 `config.yaml` / `.env`。
2. 单端口需把静态与 API 挂在同一进程（本仓库 `content_factory/web_server.py` 已是一体服务时相对省事）。
3. 页面顶栏健康徽章、问数横幅按现有逻辑展示；无 Key 时明确报错，禁止静默假成功。

## 下一步

1. 推进天翼云 ECS（用户侧：`docs/USER_ONLY_TODO.md`）
2. 部署后把公网 URL 写入 `docs/STORE_REGISTRATION.md`
3. 魔搭链接可删或降级为「已废弃 interim」

