# 真实标讯数据（浙江政采网）

成军台标书工作台 / 智能问数的**主数据路径**是 `bid_telecom.db`（SQLite），来源为浙江省政府采购网公开采购公告（通信/信息化类关键词筛选）。

数据源站点：https://zfcg.czt.zj.gov.cn  
抓取脚本：`fetch_real_data.py` · 包装：`scripts/refresh_real_bids.py`

## 合规说明

- 仅采集**公开政府采购公告**列表/详情中的项目名称、地区、行业分类、金额、状态等业务字段。
- 不采集、不存储个人隐私信息；演示与运维日志勿写入证件号/手机号等。
- 请遵守站点服务条款与合理访问频率；脚本已内置 User-Agent、随机间隔与失败重试。
- 本数据用于产品演示、赛道洞察与 NL2SQL，**不构成招投标法律意见**。

## 如何刷新

```bat
REM 快速（约 12 个区县，跳过详情金额，适合冒烟 / UI 按钮）
python scripts\refresh_real_bids.py --quick

REM 增量全量区县（较慢，含详情金额）
python scripts\refresh_real_bids.py

REM 清空后全量重建
python scripts\refresh_real_bids.py --full-rebuild
REM 或
python fetch_real_data.py --full-rebuild

REM 带超时（秒）
python scripts\refresh_real_bids.py --quick --timeout 180
```

产出：

| 路径 | 含义 |
|------|------|
| `bid_telecom.db` | 问数 / 标书清单主库，`owner_user_id=real` |
| `logs/real_projects.json` | 最近一次抓取原始 JSON |
| `logs/fetch.log` | 抓取日志 |
| `logs/fetch_meta.json` | 最近成功/失败时间与行数 |
| `logs/fetch_status.json` | UI 可轮询进度 |

## 一键启动

```bat
scripts\start_real_data.bat
```

流程：快速刷新 → 启动 znws `:8082` → MCP `:8765`。  
若站点不可达，保留库内上次成功数据；空库时问数可回落 `seed_demo_db.py` 演示行。

兼容旧入口：`scripts\start_nl2sql_demo.bat`（仅当库空时 seed，不强制覆盖真实行）。

## 调度建议

生产环境（见 `DEPLOY天翼云.md`）建议每日 09:00：

```cron
0 9 * * * /path/to/python /opt/.../fetch_real_data.py >> /opt/.../logs/cron_fetch.log 2>&1
```

本地 Windows 可用任务计划程序调用 `scripts\refresh_real_bids.py`。

## 与标书工作台 / NL2SQL 的关系

1. **标书工作台** `GET /api/bid/projects`：优先读 `bid_telecom.db`（REAL_*）；库空或失败时回落 `bid_projects.json` / BID_ZJ_*，并显示横幅「当前为本地回退，正在/请刷新真实标讯」。
2. **赛道选题** 使用真实 `industry` / `region` 聚合。
3. **智能问数** 始终查同一 SQLite；UI 展示 `row_count` / `real_count` / `last_refresh`。
4. **UI「刷新真实标讯」**：`POST /api/bid/refresh_real`（需 `run_task`）后台子进程抓取；`GET /api/bid/refresh_status` 轮询。

## 故障排查

| 现象 | 处理 |
|------|------|
| 403/429/超时 | 稍后 `--quick` 重试；检查网络；查看 `logs/fetch.log` |
| 库仍只有 demo | 确认抓取 `ok=true` 且 `real_count>0`；勿对真实行跑 `seed_demo_db --force` |
| UI 横幅本地回退 | 点「刷新真实标讯」或跑 refresh 脚本 |
| 问数离线 | `start_real_data.bat` 或分别启动 `znws_query_mock.py` / `mcp_http_nl2sql_v3.py` |

## Smoke

```powershell
python scripts\refresh_real_bids.py --quick --timeout 180
python -c "from fetch_real_data import db_stats; print(db_stats())"
# Web 登录后
# GET /api/nl2sql/status  → row_count / real_count / last_refresh
# GET /api/bid/projects   → source 含 bid_telecom.db
# POST /api/nl2sql/query  → 各行业中标项目数量和金额合计
```
