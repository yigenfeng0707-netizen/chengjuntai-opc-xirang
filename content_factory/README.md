---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '1230fa43-755e-4f0b-a7ce-1503a80bfd20'
  PropagateID: '1230fa43-755e-4f0b-a7ce-1503a80bfd20'
  ReservedCode1: 'a901140c-f418-4f87-afbb-d8da60752cde'
  ReservedCode2: 'a901140c-f418-4f87-afbb-d8da60752cde'
---

# AI 内容工厂 · 完整项目文档

> 四层 AI 内容工厂 + MCP 封装 + BidAutoPipeline 双向联动 + 定时调度 + 向量知识库 + 重试容错 + 邮件告警 + PDF 导出 + Web 管理面板 + 任务优先级队列 + 用户权限分级 + 操作日志导出 + Docker 容器化
>
> 本项目与同仓库的 **NL2SQL 智能问数 MCP 服务**（`../` 目录）打通联动：内容工厂"数据回流层"调用 NL2SQL 查询投标项目历史中标数据，反向优化选题策略，并共用 BidAutoPipeline 标书知识库。

---

## 一、项目架构总览

```
nl2sql_teleagent_prod/                  ← 仓库根（已含 NL2SQL 智能问数服务）
├── mcp_http_nl2sql_v3.py               ← NL2SQL MCP 服务（8765，已在运行）
├── znws_query_mock.py                  ← 演示版投标数据后端（8082）
└── content_factory/                    ← 本项目：AI 内容工厂
    ├── config.yaml                     统一配置（密钥/路径/邮箱/LLM）
    ├── main.py                         统一入口（自然语言指令调度）
    ├── env_check.py                    模块1 环境检测
    ├── topic_collector.py              第一层 选题采集
    ├── agents.py                       第二层 多Agent内容生成（大纲/写作/初审）
    ├── quality_gate.py                 第三层 质量门控+发布通道
    ├── data_feedback.py                第四层 数据回流（联动NL2SQL）
    ├── vector_store.py                 模块5 向量知识库+自动摘要
    ├── task_retry.py                   模块6 任务重试容错
    ├── task_queue.py                   模块9 任务优先级队列
    ├── bid_pipeline_link.py            模块3 标书系统双向联动
    ├── scheduler.py                    模块4 定时任务调度
    ├── notify_mail.py                  模块7 邮件告警
    ├── pdf_exporter.py                 模块8 Markdown导出PDF
    ├── auth_users.py                   模块11 用户权限分级
    ├── op_logger.py                    模块12 操作日志导出
    ├── mcp_server.py                   模块2 MCP stdio 服务（9工具）
    ├── web_server.py                   模块10 Web 管理面板（8090）
    ├── templates/index.html            Web 前端
    ├── articles/                       成品稿件
    ├── export_pdf/                     PDF 输出
    ├── logs/                           全流程日志
    ├── data/                           选题/稿件元数据/断点
    ├── vector_db/                      向量库持久化
    ├── knowledge/                      标书知识库本地缓存
    ├── start.bat / start_mcp.bat / start_scheduler.bat / start_web.bat
    ├── Dockerfile / docker-compose.yml
    ├── requirements / mcp.json / schedule_config.json / users.json
    └── README.md                       本文档
```

### 四层业务流水线
1. **选题采集层**：RSS 抓取 → 清洗去重 → LLM 多维打分 → topics.json
2. **多Agent生成层**：大纲Agent → 写作Agent → 初审校验Agent → articles/
3. **质量门控层**：篇幅/代码/链接/空段落校验 → 自动排版 → 公众号预留
4. **数据回流层**：文章绑定ID/标签 → 外部指标导入 → 联动 NL2SQL 查投标历史 → 反向优化选题

### 与 NL2SQL 的联动点
- `data_feedback.analyze_topic_data_with_nl2sql()` 调用 `http://127.0.0.1:8765/mcp` 的 `intelligent_query`，查询"2026上半年中标金额按行业分组"
- 结合内容工厂自身选题表现，输出选题优化建议
- 两者共用 BidAutoPipeline 标书知识库目录

---

## 二、裸机部署步骤（Windows）

1. 确认已安装 Python 3.11~3.13（本机当前 3.12.13 ✅）
2. 双击 `start.bat`，自动执行：环境自检 → 安装依赖 → 启动调度+Web面板
3. 浏览器访问 `http://127.0.0.1:8090`
4. 默认账号：见 `users.json`（首次部署请修改默认密码）
5. **先填密钥再跑真实链路**：编辑 `config.yaml`

> 建议先确保根目录 NL2SQL MCP 服务（8765）+ 演示后端（8082）已启动，数据回流层才能联动查到投标历史。

---

## 三、Docker 部署教程

```bat
cd D:\nl2sql_teleagent_prod\content_factory
docker-compose up -d            :: 启动 Web 面板
docker-compose logs -f          :: 查看日志
docker-compose down             :: 停止
```

切换启动模块（编辑 `docker-compose.yml` 的 `command`）：
```yaml
command: ["python","mcp_server.py"]      # MCP 服务
command: ["python","scheduler.py"]       # 定时调度
command: ["python","main.py","--pipeline"]  # 全链路
```

数据目录已通过 volumes 挂载，容器销毁数据不丢失。

---

## 四、指令清单（8 类）

### 1. 环境检测
```
执行环境检测，输出本机适配报告，校验是否满足内容工厂全部运行条件
```
或：`python env_check.py`

### 2. 完整内容生产流水线
```
启动内容工厂完整流水线：采集资讯选题→筛选TOP6选题→生成文稿→执行质量校验→自动摘要提取→向量化入库→导出PDF，任务失败自动重试，任务设置普通优先级
```
```
启动高优先级任务：根据投标项目需求生成行业技术综述，同步至BidAutoPipeline知识库
```

### 3. MCP 调用（OpenCode / OpenClaw / Hermes / TeleAgent）
```
调用MCP服务 content-factory，执行 collect_topics，抓取AI数字化行业资讯生成候选选题
```
```
调用MCP服务 content-factory，执行 generate_article，选题：AI智能体MCP搭建实战教程
```
```
调用MCP服务 content-factory，执行 export_article_pdf，导出最新一篇文章为PDF
```

### 4. BidAutoPipeline 双向联动
```
读取BidAutoPipeline内投标项目，提取赛道信息，定向采集资讯生成行业选题
```
```
将内容工厂已校验完成的调研报告同步至BidAutoPipeline知识库并同步向量索引
```

### 5. 定时任务 & 向量检索
```
查看当前全部定时任务列表
```
```
启动定时调度程序，每日早上9点自动采集行业资讯选题
```
```
在向量知识库检索与智能体招投标相关的行业技术资料
```

### 6. 告警与 PDF 专项
```
测试邮件告警通道，发送一条测试通知
```
```
批量将articles目录内所有已审核文稿导出PDF至export_pdf文件夹
```

### 7. 任务队列 & Web 面板
```
查看当前任务队列，展示排队任务优先级与运行状态
```
```
启动Web管理面板，访问地址 http://127.0.0.1:8090
```

### 8. 权限与日志管理
```
导出近7天全部操作审计日志保存为csv文件
```
```
查看当前系统所有账户与角色权限配置
```

---

## 五、MCP 接入教程

### mcp.json 配置
```json
{
  "mcpServers": {
    "content-factory": {
      "command": "python",
      "args": ["./content_factory/mcp_server.py"]
    }
  }
}
```

### TeleAgent 客户端接入
TeleAgent 底部【M】图标 → 添加 MCP 服务器 → 命令式 → 填入上述配置即可调用 9 个工具。

### 9 个 MCP 工具
| 工具 | 功能 |
|---|---|
| collect_topics | 采集生成候选选题 |
| generate_article | 三 Agent 串行生成文稿 |
| quality_check | 稿件质量校验 |
| analysis_topic_data | 数据回流分析（联动 NL2SQL） |
| export_knowledge_doc | 导出知识库文档 |
| sync_vector_store | 文档向量化入库 |
| run_scheduled_task | 手动触发定时任务 |
| export_article_pdf | 文章导出 PDF |
| task_queue_control | 任务队列管理 |

---

## 六、标书联动操作

- **正向推送**（内容工厂→标书）：`bid_pipeline_link.sync_knowledge_to_bid()`，把审核通过稿件按行业标签分类同步到 `bid_pipeline_root/knowledge/library`
- **反向拉取**（标书→内容工厂）：`bid_pipeline_link.fetch_bid_project_themes()`，读取标书项目清单识别赛道；清单缺失时自动联动 NL2SQL 查投标历史热门行业生成选题
- 在 `config.yaml` 配置 `bid_pipeline_root` 指向真实标书系统目录；缺失则降级为本地 `knowledge/` 缓存

---

## 七、定时任务配置

编辑 `schedule_config.json`：
```json
{
  "tasks": [{
    "id": "daily_topic_collect",
    "name": "每日资讯选题采集",
    "enabled": true,
    "cron": "0 9 * * *",          // 分 时 日 月 周
    "action": "collect_topics",
    "params": {"topk": 6}
  }]
}
```
- 启动调度：`start_scheduler.bat` 或 `python scheduler.py`（每 30 秒检查到点）
- Web 面板可可视化启停

---

## 八、向量库使用

- 轻量本地方案：TF-IDF + 余弦相似度，无需额外数据库/模型下载
- 自动摘要：`vector_store.auto_summary(content)` TF-IDF 关键句抽取
- 语义检索：`vector_store.search(query, topk=5)`
- 持久化于 `vector_db/`，同步至标书系统 `vector_sync_path`
- 文稿生成时自动入库

---

## 九、环境故障排查清单

| 现象 | 排查 |
|---|---|
| start.bat 阻断 | 看 `logs/environment_check.log`，按修复建议处理 |
| Web 面板 401 | 会话过期，重新登录 |
| 权限不足 403 | 用 admin 账号或联系管理员授权 |
| 选题采集为空 | RSS 源未配置或网络不通，会降级内置示例源 |
| 生成内容是模拟稿 | `config.yaml` 的 `llm.enabled=false`，填齐 API 配置后走真实大模型 |
| 向量检索无结果 | 先执行一次全链路或 `sync_vector_store` 入库 |
| 数据回流报 NL2SQL 离线 | 启动根目录 `..\\start_mcp.bat` + `..\\start_mock_backend.bat` |
| PDF 中文方块 | 容器内已装 Noto CJK；裸机用 Windows 自带微软雅黑 |
| 邮件未发送 | `config.yaml` SMTP 未配置，降级仅记日志 |
| 定时任务不执行 | 确认 `start_scheduler.bat` 在运行，cron 字段格式正确 |

---

## 十、邮件告警配置

编辑 `config.yaml`：
```yaml
smtp_server: "smtp.exmail.qq.com"
smtp_port: 465
smtp_user: "you@company.com"
smtp_password: "授权码"
mail_receivers: ["ops@company.com"]
```
触发场景：任务失败、连续重试失效、批量生成完成。测试：`notify_mail.test_mail_channel()`

---

## 十一、PDF 导出

- 单篇：`pdf_exporter.export_article_by_id(id)`
- 批量：`pdf_exporter.export_all()`（导出 articles/ 全部到 export_pdf/）
- 自动页眉（标题/时间）、页脚（页码）
- Web 面板「PDF导出」页一键操作

---

## 十二、任务队列使用

```python
import task_queue
task_queue.add_task("紧急标书素材", "generate_article", {"topic":"..."}, priority=1)  # 高
task_queue.add_task("常规采集", "collect_topics", {"topk":6}, priority=9)              # 低
task_queue.list_queue()       # 查看队列
task_queue.set_priority(tid, 1)  # 改优先级
task_queue.cancel_task(tid)      # 取消
```
持久化于 `data/task_queue.json`，重启不丢失。最大并发 2，避免过载。

---

## 十三、Web 面板访问指南

地址 `http://127.0.0.1:8090`，功能页：看板总览 / 选题列表 / 文稿预览 / 流水线 / 任务队列 / 定时任务 / 向量检索 / 标书同步 / PDF 导出 / 系统日志 / 用户权限。

---

## 十四、权限管理说明

| 角色 | 权限 |
|---|---|
| super_admin | 全部权限 |
| operator | 执行任务/查看/导出/队列/调度 |
| guest | 仅查看 |

- 用户持久化 `users.json`
- 新增/禁用/改密：`auth_users.add_user / disable_user / change_password`
- Web 与 MCP 同步鉴权

---

## 十五、日志导出操作

- 实时日志：`op_logger.tail(150)` 或 Web 面板「系统日志」
- 按时间范围导出 CSV：`op_logger.export_logs_csv(start, end)`
- 日志按天滚动分割，保留 30 天（`config.yaml: log_roll_days`）

---

## 十六、降级说明（保证开箱可跑通）

为支持"未填任何真实密钥也能完整跑通结构验证"，以下模块在配置缺失时自动降级：
- **LLM 写作/打分**：降级为基于规则的模拟内容（结构完整，非真实大模型生成）
- **RSS 采集**：降级为内置 6 条示例资讯
- **SMTP 邮件**：降级为仅记日志
- **BidAutoPipeline 目录缺失**：降级同步到本地 `knowledge/`
- **NL2SQL 离线**：数据回流给出降级说明，不阻断

填齐 `config.yaml` 真实密钥后，各模块自动切换为真实链路。

---

## 容器启动/停止/重建指令

```bat
docker-compose up -d            :: 启动
docker-compose stop             :: 停止
docker-compose down             :: 停止并移除
docker-compose build --no-cache :: 重建镜像
docker-compose restart          :: 重启
```

---

> 说明：本文档部分内容可能由 AI 生成，部署后请按实际环境核对配置项。

> AI生成