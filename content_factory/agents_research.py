# -*- coding: utf-8 -*-
"""调研官 Agent（鲁棒增强版）"""
import re
import llm_client
import op_logger
from config_loader import load_config

SYSTEM = (
    "你是成军台「调研官」。输出结构化 Markdown，必须含："
    "## 目标客群 ICP / ## 主渠道（≥3）/ ## 竞品观察 / ## 机会点 / ## 风险 / ## 本周可试点动作。"
    "务实可执行，避免空话；条目化。"
)


def _mock_research(goal: str, brief: str, note: str = "结构演示") -> str:
    """降级返回：保证结构完整，不抛异常。"""
    g = (goal or "").strip() or "（未指定）"
    b = (brief or "").strip() or "（无补充指令）"
    return (
        f"# 调研报告（{note}）\n\n"
        f"> 说明：因 LLM 暂不可用，以下为结构化骨架示例，供后续迭代填充。\n\n"
        f"## 战役目标\n{g}\n\n"
        f"## 任务指令\n{b}\n\n"
        f"## 目标客群 ICP\n- 独立开发者 / 小微经营者 / 一人公司\n- 关注获客成本与转化效率的团队\n- 希望快速落地 AI 能力但缺少人力的企业\n\n"
        f"## 主渠道（≥3）\n1. 内容种草：技术博客 / 短视频 / 社群\n2. 社群答疑：垂直领域群 / 问答平台\n3. 私域跟进：邮件 / 企业微信 / 私信触达\n\n"
        f"## 竞品观察\n- 通用 Chat 套壳：缺「战役看板 + 可验收周报」闭环\n- 纯生成式工具：少「人审闸门 + 多角色分工」\n- 传统 CRM：上手重、成本高，不适合一人/小团队快速试错\n\n"
        f"## 机会点\n- 一人成军工具可显著降低获客与跟进人力成本\n- 息壤原生多智能体协作，形成差异化体验\n- 可验收周报降低采购决策门槛\n\n"
        f"## 风险\n- 内容同质化，缺乏行业深度\n- 跟进无节奏，线索转化率波动\n- 渠道效果数据缺失，难以归因\n\n"
        f"## 本周可试点动作\n1. 产出 3 条种草内容并发布\n2. 建立 10 人跟进清单并设定触达节奏\n3. 完成 1 份行业观察周报（含数据引用）\n\n"
        f"> ⚠️ 降级返回（{note}），非正式模型输出\n"
    )


def _ensure_structure(text: str, goal: str, brief: str) -> str:
    """确保产出含最小结构；若关键章节缺失则自动补齐，不抛异常。"""
    t = (text or "").strip()
    if not t:
        return _mock_research(goal, brief, note="LLM返回空，已补骨架")
    # 检测最小章节（至少要有 3 个 ## 标题）
    headings = re.findall(r"^##\s+", t, re.M)
    if len(headings) >= 3:
        return t
    # 章节不足：补齐模板附录
    append = (
        "\n\n---\n\n"
        "## （补齐）风险提示\n- 建议进一步补充：渠道数据、竞品样例、落地时间节点\n\n"
        "## （补齐）本周可试点动作\n1. 与 3 位潜在客户访谈，验证痛点优先级\n2. 准备 1 份成军看板样例截图\n3. 导出首版周报并内部评审\n"
    )
    op_logger.log(
        "agent_research",
        f"调研产出章节不足({len(headings)}个)，自动补齐模板附录",
        level="WARN",
    )
    return t + append


def run_research(goal: str, brief: str) -> str:
    g = (goal or "").strip()
    b = (brief or "").strip()
    if not g:
        # 输入不合法：不抛异常，返回带提示的降级
        op_logger.log("agent_research", "调研目标为空，返回降级骨架", level="WARN")
        return _mock_research(g, b, note="目标为空-骨架示例")

    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    allow_mock = bool(cfg.get("demo_mode", {}).get("allow_mock_llm", True))

    try:
        status = llm_client.provider_status()
    except Exception:
        status = {"providers": [], "enabled": False}

    if not status.get("providers"):
        if allow_mock:
            op_logger.log("agent_research", "无可用LLM，返回降级", level="WARN")
            return _mock_research(g, b, note="无LLM配置-骨架示例")
        # 不允许 mock 时：返回明确错误提示而非抛异常
        return _mock_research(g, b, note="错误：无可用LLM，请检查配置")

    try:
        prompt = f"战役目标：{g}\n任务指令：{b or '通用调研'}\n请输出调研报告。"
        out = llm_client.call_llm(
            prompt,
            fallback="",
            system_prompt=SYSTEM,
            temperature=0.5,
            thinking=False,
        )
    except Exception as ex:
        op_logger.log("agent_research", f"LLM调用异常: {type(ex).__name__}: {ex}", level="ERROR")
        out = ""

    if not out or not str(out).strip():
        try:
            llm_client.bump_fail()
        except Exception:
            pass
        if allow_mock:
            op_logger.log("agent_research", "LLM返回空，降级mock", level="WARN")
            return _mock_research(g, b, note="LLM失败-骨架示例")
        # 不允许 mock 时也返回结构化降级，不抛 RuntimeError 打断整条战役
        op_logger.log("agent_research", "require_real_llm 失败，仍返回结构化骨架", level="ERROR")
        return _mock_research(g, b, note="错误：LLM调用失败，请稍后重试")

    try:
        llm_client.bump_ok()
    except Exception:
        pass
    try:
        op_logger.log("agent_research", f"调研完成 {len(str(out))}字")
    except Exception:
        pass
    return _ensure_structure(out, g, b)
