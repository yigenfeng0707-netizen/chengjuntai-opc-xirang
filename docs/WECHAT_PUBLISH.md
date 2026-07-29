# 微信公众号 · 草稿优先发布

成军台将内容工厂稿件推送到**公众号草稿箱**（`draft/add`），**不自动群发 / 不调用 mass send**。请在公众平台草稿箱核对后手动发布。

> **隐私**：请在本机配置 AppID / AppSecret，**不要把密钥粘贴到聊天、Issue 或截图**。

## 配置方式（任选其一）

### 1. 独立本地文件（推荐）

```bat
cd content_factory
copy config.wechat.local.yaml.example config.wechat.local.yaml
```

用编辑器打开 `config.wechat.local.yaml`，填入真实 `app_id` / `app_secret`（该文件已在 `.gitignore`）。

### 2. 环境变量

PowerShell：

```powershell
$env:WECHAT_APP_ID="你的AppID"
$env:WECHAT_APP_SECRET="你的AppSecret"
$env:WECHAT_THUMB_MEDIA_ID="永久素材封面media_id"   # 强烈建议
# 可选：$env:WECHAT_COVER_IMAGE="D:\covers\default.jpg"
```

### 3. `config.yaml` 的 `wechat:` 段

见 `content_factory/config.yaml.example`。`config.yaml` 本身已 gitignore，适合本地已有该文件时追加。

**优先级**：环境变量 > `config.wechat.local.yaml` > `config.yaml` → `wechat`。

## 封面（thumb_media_id）

微信图文草稿通常要求 **永久素材封面** `thumb_media_id`：

1. 公众平台 → 素材管理 → 上传封面图 → 复制 MediaID，填入 `thumb_media_id` / `WECHAT_THUMB_MEDIA_ID`；或  
2. 配置 `cover_image` / `WECHAT_COVER_IMAGE` 为本地 jpg/png，首次推送时调用 `material/add_material` 自动上传。

未配置封面时推送会 **明确失败**（不会假装成功）。

## IP 白名单

`client_credential` 与草稿接口要求调用方 IP 在公众平台白名单中：

- 公众平台 → 开发 → 基本配置 → IP 白名单  
- 错误码常见 `40164`：成军台会返回可读提示

## 验证

### UI

1. 启动 Web：`python content_factory/web_server.py`（或 `scripts\start_local_demo.bat`）  
2. 登录（非 guest）→ **内容工厂 → 稿件台**  
3. 顶部应显示「公众号草稿通道已配置」或「未配置公众号凭证」横幅  
4. 点文章行 **「推送到公众号草稿」**  
   - 成功：展示 `media_id` + 草稿箱提示  
   - 未配置：`未配置公众号凭证`（skipped，非成功）  
   - 失败：红色错误（token / IP / 封面等）

### API

```http
GET  /api/wechat/status
POST /api/wechat/publish_draft
Content-Type: application/json
{"article_id":"ART........"}
```

或：

```http
POST /api/run
{"action":"publish_wechat_draft","params":{"article_id":"ART........"}}
```

也可：`quality_gate.publish_to_wechat_draft(article_id)` / MCP 工具 `publish_wechat_draft`。

### 冒烟（无真实调用）

```bash
python tests/test_wechat_draft.py
```

### 可选实网（仅当本机已配置凭证）

```bash
python scripts/live_wechat_draft.py ART你的稿件ID
```

未设环境变量/本地文件时脚本会直接退出并说明原因，不会空跑成功。

## 仍需你完成的事项

| 项 | 说明 |
|----|------|
| AppID / AppSecret | 本机自行写入上述配置，勿提交 git |
| IP 白名单 | 服务器/本机出口公网 IP |
| 封面 media_id 或 cover 图 | 微信图文草稿硬要求 |
| 草稿核对与正式发布 | 在公众平台手动完成；成军台只写草稿箱 |

## 相关文件

- `content_factory/wechat_publisher.py` — token + draft/add  
- `content_factory/quality_gate.py` — `publish_to_wechat_draft`  
- `content_factory/config.wechat.local.yaml.example`
