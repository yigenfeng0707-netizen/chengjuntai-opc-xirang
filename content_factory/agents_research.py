# -*- coding: utf-8 -*-
"""调研官 Agent"""
import llm_client
import op_logger
from config_loader import load_config

SYSTEM = (
    "你是成军台「调研官」。输出结构化 Markdown，必须含："
    "## 目标客群 ICP / ## 主渠道（≥3）/ ## 竞品观察 / ## 机会点 / ## 风险 / ## 本周可试点动作。"
    "务实可执行，避免空话；条目化。"
)


def run_research(goal: str, brief: str) -> str:
    prompt = f"战役目标：{goal}\n任务指令：{brief}\n请输出调研报告。"
    allow_mock = bool(load_config().get("demo_mode", {}).get("allow_mock_llm", False))
    status = llm_client.provider_status()
    if not status.get("providers"):
        if allow_mock:
            return (
                f"# 调研报告（结构演示）\n\n## 目标\n{goal}\n\n## 指令\n{brief}\n\n"
                f"## 目标客群 ICP\n独立开发者 / 小微经营者 / 一人公司\n\n"
                f"## 主渠道\n1. 内容种草 2. 社群答疑 3. 私域跟进\n\n"
                f"## 竞品观察\n通用 Chat 套壳缺「战役看板+可验收周报」\n\n"
                f"## 机会点\n一人成军工具降低获客与跟进成本\n\n"
                f"## 风险\n内容同质化；跟进无节奏\n\n"
                f"## 本周可试点动作\n发 3 条种草 + 建 10 人跟进表\n\n"
                f"> ⚠️ mock 演示稿，非正式模型输出\n"
            )
        raise RuntimeError("调研官：无可用 LLM provider")
    out = llm_client.call_llm(prompt, fallback="", system_prompt=SYSTEM, temperature=0.5, thinking=False)
    if not out:
        llm_client.bump_fail()
        if allow_mock:
            return f"# 调研报告（结构演示）\n\n目标：{goal}\n\n> ⚠️ LLM 失败后的 mock\n"
        raise RuntimeError("调研官：LLM 调用失败")
    llm_client.bump_ok()
    op_logger.log("agent_research", "调研完成")
    return out
