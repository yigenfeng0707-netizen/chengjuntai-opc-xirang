# 密钥轮换说明（SenseNova）

## 背景

公开仓库 [bidding-intelligence-assistant](https://github.com/yigenfeng0707-netizen/bidding-intelligence-assistant) 曾在 `backend/app/services/ai_service.py` / `config.py` **硬编码**商汤 SenseNova API Key。源码侧已改为仅从环境变量 `SENSENOVA_API_KEY`（或 `backend/.env`）读取，但 **Git 历史仍可能保留旧值**。

## 你需要做的（人工）

1. 登录商汤 / SenseNova 控制台，**立即作废或轮换**曾暴露的 Key（若仍有效）。
2. 为本地与生产重新签发新 Key，只写入：
   - 成军台：`chengjuntai/.env` 或 gitignore 的 `content_factory/config.yaml`（字段 `api_key_env: SENSENOVA_API_KEY`）
   - BidTrace 薄壳（若仍自用）：`bidding-intelligence-assistant/backend/.env`
3. **不要**把真实 Key 写进源码、README、截图或公开 Issue。

## 成军台仓卫生

- `content_factory/config.yaml`、`.env`、`users.json` 已在 `.gitignore`，禁止 `git add -f`。
- 预赛主仓与提交链接只用 [chengjuntai-opc-xirang](https://github.com/yigenfeng0707-netizen/chengjuntai-opc-xirang)，勿把含历史密钥的聊天壳仓当作主作品链接。

## 自检

```powershell
# 工作区不应再出现硬编码 sk- 进 py/js（config.yaml / .env 除外且须被 ignore）
rg -n "api_key\s*=\s*[\"']sk-" --glob "*.py" content_factory
git check-ignore -v content_factory/config.yaml .env
```
