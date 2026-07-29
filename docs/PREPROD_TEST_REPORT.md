# 成军台 · 预发测试报告（PREPROD）

> 测试时间：2026-07-29  
> 环境：本地 `http://127.0.0.1:8090`  
> LLM：interim TokenPlan / SenseNova（gitignore 的 `content_factory/config.yaml`，**不提交 Key**）  
> 范围：预赛主演示路径 + 侧栏可用性 + 冒烟脚本

## 1. 根因与修复

| 问题 | 根因 | 修复 |
|------|------|------|
| `Cannot set properties of null (setting 'innerHTML')` | 从「战役列表」点「打开」时 `navHomeOpen` 用 `setTimeout(50)` 抢跑；`vHome` 仍在等 API，`campPanel`/`artBox` 尚未挂到 DOM；或导航离开后 `startCamp`/`viewArt` 仍写旧节点 | `setHTML`/`$` 空指针守卫；`nav()` 异步 + `_viewSeq` 防过期渲染；`navHomeOpen` 改为 `await nav('home')` 后再 `openCamp`；`showCamp`/`viewArt` 缺节点时回退到看板 |
| 侧栏像「坏了」 | 次要能力（选题/向量/调度/改密 UI）无入口或空操作，易被当成崩溃 | 内容工厂 / 用户页明确标注「预赛范围外 / 敬请期待」；主路径文案强化 |
| 内容生成「不可用」 | 多为上述 JS 崩溃中断后续操作；API 本身可用 | 修好 DOM 竞态；E2E 已验证 `generate_article` 与战役产物 |

代码改动：`content_factory/templates/index.html`（最小前端加固）。  
新增：`scripts/smoke_e2e.py`、本报告。

## 2. 通过/失败矩阵

### A. 前端稳定性

| 项 | 结果 | 说明 |
|----|------|------|
| 登录页 + health 徽章 | PASS | `loginBanner`/`modelText` 均有 null 守卫 |
| 登录 → 成军看板 | PASS | `content`/`campPanel` 在 API 返回后写入 |
| 战役列表 → 打开 | PASS | 消除 50ms 竞态 |
| 发起成军 / 人审 / 产物 / 周报 UI 路径 | PASS | 写节点前检查；失败有横幅而非抛异常 |

### B. API / 功能（`python scripts/smoke_e2e.py`）

| 检查项 | 结果 | 备注 |
|--------|------|------|
| GET `/api/health` | PASS | `demo_ready=true`，providers=2（TokenPlan + SenseNova） |
| POST `/api/login` admin | PASS | `super_admin` |
| POST `/api/login` judge | PASS | `guest` |
| judge 发起战役 | PASS | HTTP 403，不可 `run_task` |
| GET `/api/metrics` | PASS | |
| GET `/api/campaigns` | PASS | |
| campaign start `lead_gen` | PASS | ~11s → `planned` |
| approve → run → awaiting_review | PASS | ~179s，5 产物 |
| artifact fetch | PASS | |
| weekly report | PASS | |
| final approve → completed | PASS | |
| `/api/run` `generate_article` | PASS | 已生成文章 ID；质检 `review_pass=false`（门禁偏严，**生成可用**） |

### C. 结构回归（无 Key / CI）

| 检查项 | 结果 |
|--------|------|
| `python scripts/smoke_e2e.py --mock` | PASS |
| `python tests/test_campaign_core.py` | PASS |
| `python scripts/smoke_e2e.py --skip-llm-heavy` | PASS（轻量 HTTP） |

### D. 侧栏审计

| 导航 | 状态 | 备注 |
|------|------|------|
| 成军看板 | 可用（主路径） | 发起 → 人审 → 产物 → 周报 |
| 战役列表 | 可用 | 打开已修竞态 |
| 成效指标 | 可用 | JSON 埋点 |
| 内容工厂 | 可用（快测） | `generate_article`；选题/向量/调度/全量 PDF UI = **预赛范围外** |
| 系统日志 | 可用 | tail 150 |
| 用户权限 / 权限管理 | 可用 | 列表 + 超管启用/禁用/改角色；邮箱注册 |
| 用户洞察 | 可用（仅 super_admin） | 使用情况 / 画像 / 轨迹 |

## 3. 已知缺口（预赛可接受）

1. **主办方星辰 / 息壤 Token 未到**：当前徽章为 interim TokenPlan；到手后注入 `XIRANG_API_KEY` 并重启即可切 primary。  
2. **NL2SQL 数据参谋**：健康检查常为离线；战役 data 任务会降级说明，不阻断主路径。  
3. **内容质检 `review_pass`**：样例文可能未过质量门，不影响生成与演示。  
4. **公网 / HTTPS / 改默认密码**：运维项，见 `docs/PROD_HARDENING.md`、`docs/CTYUN_TRIAL.md`。  
5. **批量选题、向量检索面板、定时开关 UI**：预赛范围外（用户管理写操作已开放给超管）。

## 4. 用户如何验收（Ctrl+F5）

1. 确认服务：`http://127.0.0.1:8090`（若刚改后端：先停旧进程再 `scripts\start_local_demo.bat`）。  
2. 浏览器 **Ctrl+F5** 强刷，避免旧 JS 缓存。  
3. 看登录页横幅：应显示过渡模型已就绪。  
4. `admin` / `chengjun2026` 登录。  
5. **成军看板** → 样例「① AI获客跟进」→ **发起成军** → **人审通过并执行**（约 2–4 分钟）→ 打开产物 → **导出成军周报** → 终审完成。  
6. 侧栏点一遍：列表打开战役不应再控制台报 `innerHTML`；内容工厂可点「快速生成」。  
7. 可选：`judge` / `judge2026` 只能看，不能发起。  
8. 回归命令：
   ```powershell
   cd D:\APPs\天翼息壤杯\chengjuntai
   python scripts/smoke_e2e.py --skip-llm-heavy
   python scripts/smoke_e2e.py          # 含真实 LLM，约 3–5 分钟
   python scripts/smoke_e2e.py --mock   # 无网结构
   ```

## 5. 结论

**预赛主演示路径（发起成军 → 人审 → 产物 → 周报）在 interim Key 下已打通；JS null `innerHTML` 已修；次要功能已标明范围外。**  
未提交 git（含 Key 的 `config.yaml` 保持 gitignore）。

---

## 6. 认证与权限（2026-07-29 增补）

| 能力 | 状态 | 说明 |
|------|------|------|
| 邮箱/用户名登录 | PASS | `POST /api/login` 接受 email 或 username |
| 邮箱注册 | PASS | `POST /api/register` → role=`user` |
| 角色权限 | PASS | `super_admin` / `operator` / `user` / `guest` |
| 战役隔离 | PASS | `user` 仅见自己的 `created_by`；admin/operator 可见全部 |
| 用户轨迹 | PASS | `content_factory/data/user_events.jsonl` |
| 画像 / 用量 | PASS | 侧栏「用户洞察」（仅 super_admin） |
| 权限管理 UI | PASS | 启用/禁用、改角色 |

凭证见本地 `docs/ADMIN_ACCESS.local.md`（gitignore，勿提交）。  
兼容：`admin` / `chengjun2026`；主超管邮箱见该文件。

## 5. 产品升级后补充（2026-07-29 晚）

问题-方案-演示路径见 `PRODUCT_UPGRADE_NOTES.md` / `PROJECT_DOC.md` §2。

| 项 | 说明 |
|----|------|
| 产物可见性 | 产物抽屉高亮 + 产物中心；内容工厂预览列表 |
| Word 主交付 | `POST /api/campaign/{id}/report_docx`；UI「导出 Word」 |
| 智能问数 | 侧栏页 + 真实 MCP/znws；`scripts/start_nl2sql_demo.bat` |
| 样例战役 | `scripts/seed_demo_campaigns.py` 幂等种子 |

冒烟建议：

```powershell
# 注册 → 登录 → 发起（user）→ 超管看轨迹
$body = @{email='demo_user@example.com';password='demo1234';display_name='Demo'} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8090/api/register -Method POST -Body $body -ContentType 'application/json'
```
