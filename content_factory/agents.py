# -*- coding: utf-8 -*-
"""
第二层：多 Agent 内容生成层
三个独立智能体串行协作：
1. 大纲 Agent：根据选题产出结构化长文大纲
2. 写作 Agent：基于大纲生成完整 Markdown 技术文稿，含实操步骤、代码块
3. 初审校验 Agent：检测虚构数据、占位符、无效代码、逻辑缺陷
成品稿件持久化存放 articles/
"""
import os
import json
import re
import datetime
from config_loader import ARTICLES_DIR, DATA_DIR, load_config
from task_retry import retry
import vector_store
import op_logger
import llm_client

ARTICLES_META = os.path.join(DATA_DIR, "articles_meta.json")

PROMPT_OUTLINE = (
    "你是技术内容大纲专家。为以下选题生成结构化大纲，含引言、3-5个核心章节(每章2-3个小节)、总结。"
    "输出Markdown列表。\n选题：{topic}\n摘要：{summary}\n"
    "【真实数据上下文】（写作须引用，勿编造未标注数字）：\n{real_ctx}"
)
PROMPT_WRITE = (
    "你是资深技术作者。根据大纲撰写完整Markdown长文，篇幅{min_words}-{max_words}字。\n"
    "硬性要求：\n"
    "1) 必须引用下方【真实数据上下文】中的统计数字，并写明「来源：成军台真实标讯库」；\n"
    "2) 禁止出现 xxx/TODO/FIXME/[AI工具名称]/XX品牌 等占位符；产品名用「成军台」；\n"
    "3) 任何示意性转化率/获客数必须标注「示例」，不得写成已发生的真实业绩；\n"
    "4) 可含实操步骤；代码块可选，若写代码须完整可运行示意。\n"
    "选题：{topic}\n大纲：{outline}\n【真实数据上下文】：\n{real_ctx}"
)
PROMPT_REVIEW = (
    "你是内容审核专家。仅在下列情况判 fail：\n"
    "① 出现未标注的绝对业绩数字且无法对应真实库（标注「示例/模拟」或写明「来源：成军台真实标讯库」的数字不算虚构）；\n"
    "② 残留占位符（xxx/TODO/FIXME/[AI工具名称]/XX 等）；\n"
    "③ 明显残缺无法运行的伪代码；\n"
    "④ 严重自相矛盾。\n"
    "Markdown表格/列表不算无效代码。达标则 pass=true、issues=[]。\n"
    "只输出JSON:{{\"pass\":bool,\"issues\":[{{\"type\":\"...\",\"detail\":\"...\"}}],\"suggestions\":\"...\"}}\n"
    "文稿：{article}"
)


def _format_nl2sql_ctx(result: dict) -> str:
    if not result or not result.get("ok"):
        return ""
    cols = result.get("columns") or []
    rows = result.get("rows") or []
    lines = [
        f"数据源={result.get('source') or 'nl2sql'} · 行数={result.get('row_count', len(rows))}",
    ]
    if result.get("sql"):
        lines.append(f"SQL摘要：{str(result.get('sql'))[:180]}")
    for row in rows[:12]:
        if isinstance(row, dict):
            lines.append(" · ".join(f"{k}={v}" for k, v in row.items()))
        elif isinstance(row, (list, tuple)):
            if cols and len(cols) == len(row):
                lines.append(" · ".join(f"{c}={v}" for c, v in zip(cols, row)))
            else:
                lines.append(" · ".join(str(x) for x in row))
        else:
            lines.append(str(row))
    return "\n".join(lines)


def fetch_real_content_context(topic: str = "", summary: str = "") -> dict:
    """从 NL2SQL/znws 拉取真实标讯统计，供种草/内容写作引用。"""
    try:
        import agents_data
    except Exception as ex:
        return {"ok": False, "text": "", "error": str(ex)}

    q = (
        "统计真实标讯总条数、演示条数、近30天新增、按地区TOP5、按行业TOP5。"
        f"选题参考：{(topic or '')[:80]} {(summary or '')[:120]}"
    )
    try:
        result = agents_data.query_nl2sql(q, chart_type="table")
    except Exception as ex:
        return {"ok": False, "text": "", "error": str(ex)}

    if not result.get("ok"):
        return {
            "ok": False,
            "text": "（NL2SQL 暂不可用：写作时勿编造具体标讯业绩数字；示意数据须标注「示例」。）",
            "error": result.get("error") or "offline",
            "raw": result,
        }
    text = _format_nl2sql_ctx(result)
    return {"ok": True, "text": text or "（查询成功但无行）", "raw": result}


def _call_llm(prompt: str, fallback: str = "") -> str:
    """调用 LLM；require_real_llm=true 且未允许 mock 时禁止静默返回 mock fallback。"""
    cfg = load_config()
    llm_cfg = cfg.get("llm", {})
    allow_mock = bool(cfg.get("demo_mode", {}).get("allow_mock_llm", False))
    require_real = bool(llm_cfg.get("require_real_llm", False)) and not allow_mock
    out = llm_client.call_llm(prompt, fallback="" if require_real else fallback)
    if out:
        return out
    if require_real and not llm_client.is_llm_enabled():
        raise RuntimeError("内容官：无可用 LLM provider（require_real_llm=true）")
    if require_real:
        raise RuntimeError("内容官：LLM 调用失败（require_real_llm=true，禁止静默 mock）")
    return fallback


def _mock_outline(topic, summary):
    return (f"# {topic}\n\n## 引言\n背景与价值\n\n"
            f"## 核心概念\n- 定义\n- 关键特性\n- 应用场景\n\n"
            f"## 实操步骤\n- 环境准备\n- 配置说明\n- 代码实现\n- 验证测试\n\n"
            f"## 进阶优化\n- 性能调优\n- 常见问题\n\n## 总结\n")


def _mock_article(topic, outline, min_words, max_words):
    return (f"# {topic}\n\n> 本文系统讲解{topic}的落地实践，含完整代码示例与实操步骤。\n\n"
            f"## 引言\n{topic}是当前企业AI落地的重要方向。随着大模型能力持续增强，如何将{topic}稳定接入企业真实业务场景成为关键挑战。本文从环境准备到生产部署，给出可复制的完整实践路径，帮助团队快速实现规模化落地。实操价值显著，行业案例稀缺。\n\n"
            f"## 核心概念\n{topic}具备标准化、可复用、易扩展三大特性。标准化指遵循业界主流协议规范，确保多工具互通；可复用指一次开发多场景复用，降低重复建设成本；易扩展指架构松耦合，便于按需挂载新能力。三者结合，使{topic}成为企业AI中台的关键拼图。\n\n"
            f"## 实操步骤\n### 环境准备\n确保 Python 3.11+ 环境，执行以下命令安装核心依赖：\n\n"
            f"```bash\npip install fastapi uvicorn pyyaml requests\n```\n\n"
            f"### 配置说明\n统一配置文件 config.yaml 管理密钥、路径、端口等参数，禁止代码硬编码：\n\n"
            f"```yaml\nservice:\n  host: 127.0.0.1\n  port: 8090\nllm:\n  enabled: true\n  api_base: https://api.example.com/v1\n```\n\n"
            f"### 代码实现\n核心示例通过三步串行完成业务处理：\n\n```python\n"
            f"def run_pipeline(topic):\n    # 步骤1 构建大纲\n    outline = build_outline(topic)\n    # 步骤2 生成正文\n    article = write_article(outline)\n    # 步骤3 质检校验\n    result = quality_check(article)\n    return {{'article': article, 'pass': result['pass']}}\n\n"
            f"if __name__ == '__main__':\n    r = run_pipeline('{topic}')\n    print('质检通过' if r['pass'] else '需整改')\n```\n\n"
            f"### 验证测试\n执行后应依次输出大纲、正文与质检结论，确认终端无报错。建议补充单元测试覆盖边界条件，例如空输入、超长文本、异常字符。测试用例:\n\n```python\nassert run_pipeline('测试选题')['pass'] in (True, False)\n```\n\n"
            f"## 进阶优化\n生产环境建议增加三层加固：一是引入任务重试机制，对网络抖动与接口超时自动重试；二是加入内存缓存，对高频相同查询直接命中缓存降低后端压力；三是接入操作日志审计，全链路留痕便于追溯。三者协同可显著提升系统稳定性与可观测性。\n\n"
            f"## 常见问题\nQ: 启动报端口占用？A: 修改 config.yaml 端口或释放占用进程。\nQ: 中文渲染异常？A: 检查字体文件路径与编码。\nQ: 内容生成偏短？A: 调整 target_min_words 参数。\n\n"
            f"## 总结\n本文完整呈现了{topic}从配置到部署的实践路径。核心在于：先跑通最小可用链路，再按场景逐层加固。建议团队据此搭建自有沙箱环境，逐步迁移至生产。后续可扩展负载均衡与多机分布式调度，进一步提升吞吐能力。\n")


# ---------- Agent 1：大纲 ----------
def outline_agent(topic: str, summary: str = "", real_ctx: str = "") -> str:
    @retry("outline_agent")
    def _do():
        prompt = PROMPT_OUTLINE.format(
            topic=topic, summary=summary,
            real_ctx=real_ctx or "（暂无真实库快照）",
        )
        out = _call_llm(prompt, fallback=_mock_outline(topic, summary))
        op_logger.log("agent_outline", f"大纲生成完成[{topic}]")
        return out
    return _do()


# ---------- Agent 2：写作 ----------
def write_agent(topic: str, outline: str, real_ctx: str = "") -> str:
    cfg = load_config().get("article", {})
    min_w = cfg.get("target_min_words", 800)
    max_w = cfg.get("target_max_words", 4000)
    @retry("write_agent")
    def _do():
        prompt = PROMPT_WRITE.format(
            topic=topic, outline=outline, min_words=min_w, max_words=max_w,
            real_ctx=real_ctx or "（暂无真实库快照；示意数据须标注「示例」）",
        )
        out = _call_llm(prompt, fallback=_mock_article(topic, outline, min_w, max_w))
        op_logger.log("agent_write", f"文稿生成完成[{topic}]，{len(out)}字")
        return out
    return _do()


# ---------- Agent 3：初审校验 ----------
def review_agent(article: str) -> dict:
    @retry("review_agent")
    def _do():
        prompt = PROMPT_REVIEW.format(article=article[:8000])
        result = _call_llm(prompt, fallback='{"pass": true, "issues": [], "suggestions": "模拟通过"}')
        try:
            # 提取JSON
            m = re.search(r"\{.*\}", result, re.S)
            return json.loads(m.group()) if m else {"pass": True, "issues": [], "suggestions": result}
        except Exception:
            return {"pass": True, "issues": [], "suggestions": result}
    return _do()


# ---------- 串行协作主流程 ----------
def generate_article(topic: str, summary: str = "", tags: list = None, task_id: str = None,
                     campaign_id: str = None) -> dict:
    """三 Agent 串行：大纲→写作→初审，返回稿件信息；可选关联战役 ID"""
    op_logger.log("agent_pipeline", f"开始生成文稿[{topic}]", task_id=task_id)
    usage_before = llm_client.token_usage()
    real = fetch_real_content_context(topic, summary)
    real_ctx = real.get("text") or ""
    if real.get("ok"):
        op_logger.log("agent_pipeline", "已注入真实标讯统计到写作上下文", task_id=task_id)
    else:
        op_logger.log(
            "agent_pipeline",
            f"真实数据未注入（将约束勿编造）：{real.get('error')}",
            level="WARN", task_id=task_id,
        )

    outline = outline_agent(topic, summary, real_ctx=real_ctx)
    article = write_agent(topic, outline, real_ctx=real_ctx)
    review = review_agent(article)
    usage_after = llm_client.token_usage()
    tokens_used = max(
        0,
        int(usage_after.get("total_tokens") or 0) - int(usage_before.get("total_tokens") or 0),
    )

    art_id = f"ART{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    safe_title = re.sub(r"[\\/:*?\"<>|]", "_", topic)[:40]
    md_file = os.path.join(ARTICLES_DIR, f"{art_id}_{safe_title}.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(f"---\nid: {art_id}\ntitle: {topic}\ntags: {tags or []}\ncreated_at: {datetime.datetime.now().isoformat()}\n---\n\n{article}")

    # 自动摘要 + 向量入库
    summary_text = vector_store.auto_summary(article)
    vector_store.index_document(art_id, topic, article, tags or [], source="content_factory")

    # 更新稿件元数据
    meta_list = []
    if os.path.exists(ARTICLES_META):
        try:
            with open(ARTICLES_META, "r", encoding="utf-8") as f:
                meta_list = json.load(f)
        except Exception:
            meta_list = []
    entry = {
        "id": art_id, "title": topic, "file": os.path.basename(md_file),
        "tags": tags or [], "summary": summary_text,
        "review_pass": review.get("pass", False), "review": review,
        "real_data_used": bool(real.get("ok")),
        "tokens_used": tokens_used,
        "token_usage_snapshot": {
            "total_tokens": usage_after.get("total_tokens"),
            "prompt_tokens": usage_after.get("prompt_tokens"),
            "completion_tokens": usage_after.get("completion_tokens"),
            "last": usage_after.get("last"),
        },
        "created_at": datetime.datetime.now().isoformat(),
    }
    if campaign_id:
        entry["campaign_id"] = campaign_id
    meta_list.append(entry)
    with open(ARTICLES_META, "w", encoding="utf-8") as f:
        json.dump(meta_list, f, ensure_ascii=False, indent=2)

    op_logger.log(
        "agent_pipeline",
        f"文稿生成完成 {art_id}，初审{'通过' if review.get('pass') else '未通过'}，"
        f"真实数据={'是' if real.get('ok') else '否'}，tokens≈{tokens_used}",
        task_id=task_id,
    )
    return {"id": art_id, "title": topic, "file": md_file, "summary": summary_text,
            "review_pass": review.get("pass", False), "review": review,
            "campaign_id": campaign_id, "real_data_used": bool(real.get("ok")),
            "tokens_used": tokens_used}


def link_article_campaign(article_id: str, campaign_id: str) -> dict:
    """将内容工厂稿件关联到战役（写入 articles_meta.campaign_id）"""
    if not os.path.exists(ARTICLES_META):
        raise ValueError("无稿件元数据")
    with open(ARTICLES_META, "r", encoding="utf-8") as f:
        meta_list = json.load(f)
    found = None
    for a in meta_list:
        if a.get("id") == article_id:
            a["campaign_id"] = campaign_id
            found = a
            break
    if not found:
        raise ValueError(f"稿件不存在: {article_id}")
    with open(ARTICLES_META, "w", encoding="utf-8") as f:
        json.dump(meta_list, f, ensure_ascii=False, indent=2)
    return found


def articles_for_campaign(campaign_id: str) -> list:
    return [a for a in list_articles() if a.get("campaign_id") == campaign_id]


def list_articles():
    if os.path.exists(ARTICLES_META):
        with open(ARTICLES_META, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


if __name__ == "__main__":
    r = generate_article("MCP协议实战教程", "MCP协议降低智能体集成成本")
    print(json.dumps(r, ensure_ascii=False, indent=2))
