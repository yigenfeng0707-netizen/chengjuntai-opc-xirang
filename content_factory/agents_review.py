# -*- coding: utf-8 -*-
"""复盘官 Agent"""
import llm_client
import op_logger
from config_loader import load_config

SYSTEM = (
    "你是成军台「复盘官」。基于已有产物写战役复盘 Markdown："
    "完成情况、关键产出、缺口、下周 TOP3、一人成军效率估算。"
)


def run_review(goal: str, brief: str, artifacts_digest: str) -> str:
    prompt = (
        f"战役目标：{goal}\n任务指令：{brief}\n"
        f"已有产物摘要：\n{artifacts_digest[:6000]}\n请输出复盘周报要点。"
    )
    allow_mock = bool(load_config().get("demo_mode", {}).get("allow_mock_llm", False))
    status = llm_client.provider_status()
    if not status.get("providers"):
        if allow_mock:
            return (
                f"# 战役复盘（结构演示）\n\n## 目标\n{goal}\n\n## 完成情况\n任务已按成军看板推进\n\n"
                f"## 下周 TOP3\n1. 固化获客内容\n2. 跟进高意向\n3. 沉淀话术库\n\n"
                f"## 效率估算\n预估节省 6 人时\n\n> ⚠️ mock 演示稿\n"
            )
        raise RuntimeError("复盘官：无可用 LLM provider")
    out = llm_client.call_llm(prompt, fallback="", system_prompt=SYSTEM, temperature=0.4, thinking=False)
    if not out:
        llm_client.bump_fail()
        if allow_mock:
            return f"# 复盘（mock）\n\n{goal}\n"
        raise RuntimeError("复盘官：LLM 调用失败")
    llm_client.bump_ok()
    op_logger.log("agent_review", "复盘完成")
    return out
