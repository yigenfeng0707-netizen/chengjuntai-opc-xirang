# 标书 BidAutoPipeline 全路径演示

成军台内嵌的标书联动：知识同步 ↔ 赛道选题 ↔ 材料工作台（要求拆解 / 证据矩阵 / Word）。

**真实标讯主路径**见 [REAL_DATA.md](./REAL_DATA.md)。本页保留演示与 API 速查。

## 一键准备

```bat
REM 1) 推荐：刷新政采网真实标讯 + 启动问数
scripts\start_real_data.bat

REM 2) 仅问数服务（库空才 seed 演示）
scripts\start_nl2sql_demo.bat

REM 3) 冷回退：离线 JSON 演示清单（DB 空时才会用到）
python scripts\seed_bid_demo.py

REM 4) Web
cd content_factory
python web_server.py
```

看板：http://127.0.0.1:8090  
登录：`admin` / `chengjun2026`（写操作需 `run_task`；评委 `judge` 只读）

## 数据优先级

| 优先级 | 来源 | UI 表现 |
|--------|------|---------|
| 1 | `bid_telecom.db`（`owner_user_id=real`） | 真实标讯横幅 · ID `REAL_*` |
| 2 | `bid_telecom.db`（demo 行） | 警告：请刷新真实标讯 |
| 3 | `bid_projects.json` / BID_ZJ_* | **当前为本地回退，正在/请刷新真实标讯** |

刷新入口：

- CLI：`python scripts\refresh_real_bids.py --quick`
- UI 标书工作台 / 智能问数：**刷新真实标讯**
- API：`POST /api/bid/refresh_real` · `GET /api/bid/refresh_status`

## 配置

`content_factory/config.yaml`：

| 键 | 空值时行为 |
|----|------------|
| `bid_pipeline_root` | 知识库用本地 `content_factory/knowledge/`；项目清单优先 DB |
| `knowledge_sync_folder` | 默认同步到 `content_factory/knowledge/` |
| `vector_sync_path` | 仅当父目录存在时同步向量 |

外挂真实 BidAutoPipeline 时：

```yaml
bid_pipeline_root: "D:/work/BidAutoPipeline"
knowledge_sync_folder: "${bid_pipeline_root}/knowledge/library"
vector_sync_path: "${bid_pipeline_root}/vector_db"
```

清单文件约定（仅 DB 空时）：`<bid_pipeline_root>/projects/project_list.json`

## 冷回退演示 ID（JSON）

| ID | 项目 | 赛道 | 地区 |
|----|------|------|------|
| `BID_ZJ_001` | 杭州电信政企云网融合专线扩容 | 云网融合 | 杭州 |
| `BID_ZJ_002` | 宁波市智慧城市5G专网建设 | 5G专网 | 宁波 |
| `BID_ZJ_003` | 温州数字政府一体化平台运维 | 数字政府 | 温州 |
| `BID_ZJ_004` | 嘉兴物联网感知平台二期 | 物联网 | 嘉兴 |
| `BID_ZJ_005` | 金华IDC算力调度中心采购 | IDC算力 | 金华 |

问数库有真实行时，标书清单以 DB 为准，上表仅作冷回退。

## 点击路径（评委 3 分钟）

1. **侧栏 → 标书工作台**
   - 看真实标讯 `REAL_*`（或回退横幅 + BID_ZJ_*）
   - **刷新真实标讯**（可选）
   - **正向同步** / **拉取赛道选题** / **一键写入选题池**
   - 行内 **获客战役 / 综述战役**
2. **材料工作台**：粘贴招标文本 → **要求拆解** → **生成证据矩阵** → **导出 Word**  
   （Word 附卷含封面 / checklist / 证据矩阵 + `content_factory/data/bid_package_outline.md` 投标包章节大纲）
3. **侧栏 → 智能问数**：看行数 / 最近刷新；点预设卡（需 znws/MCP）

## API 速查

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/bid/status` | 登录 |
| GET | `/api/bid/projects` | 登录 |
| GET | `/api/bid/themes` | 登录 |
| POST | `/api/bid/refresh_real` | run_task |
| GET | `/api/bid/refresh_status` | 登录 |
| POST | `/api/bid/sync` | run_task |
| POST | `/api/bid/seed` | run_task |
| POST | `/api/bid/push_article` | run_task |
| POST | `/api/bid/push_campaign` | run_task |
| POST | `/api/bid/themes_to_topics` | run_task |
| POST | `/api/bid/theme_to_campaign` | run_task |
| POST | `/api/bid/workspace/parse` | run_task |
| POST | `/api/bid/workspace/matrix` | 登录 |
| POST | `/api/bid/workspace/export_docx` | export |
| GET | `/api/nl2sql/status` | 登录（含 row_count / real_count / last_refresh） |

## 真 vs 模拟

| 能力 | 状态 |
|------|------|
| 浙江政采网抓取 → bid_telecom.db | **真**（站点可达时；失败保留上次缓存） |
| 项目清单 / 赛道选题 | **真**（优先 DB；JSON 冷回退） |
| 正向同步稿件到 knowledge/ | **真** |
| 赛道 → 发起战役 | **真**（Campaign OS + LLM） |
| 要求拆解 / 证据矩阵 / Word | **真**（见材料工作台） |
| 智能问数 | **真**（znws:8082 / MCP:8765） |

## Smoke

```powershell
python scripts\refresh_real_bids.py --quick --timeout 180
$tok = (Invoke-RestMethod http://127.0.0.1:8090/api/login -Method POST -ContentType 'application/json' -Body '{"u":"admin","p":"chengjun2026"}').token
$h = @{ Authorization = "Bearer $tok" }
Invoke-RestMethod http://127.0.0.1:8090/api/bid/status -Headers $h
Invoke-RestMethod http://127.0.0.1:8090/api/bid/projects -Headers $h
Invoke-RestMethod http://127.0.0.1:8090/api/nl2sql/status -Headers $h
```
