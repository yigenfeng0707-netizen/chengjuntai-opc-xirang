# -*- coding: utf-8 -*-
"""运营官 Agent：跟进清单 / 节奏 / 话术 / 渠道计划"""
import llm_client
import op_logger
from config_loader import load_config

SYSTEM = (
    "你是成军台「运营官」。必须输出可直接执行的 Markdown，结构固定：\n"
    "1) ## 本周节奏（按日）\n"
    "2) ## 意向客户跟进表（恰好 10 行 Markdown 表格："
    "ID|客户画像|触达渠道|首触话术摘要|优先级P1-P3|下次跟进日）\n"
    "3) ## 渠道投放计划（渠道|动作|素材|验收标准）\n"
    "4) ## 转化指标（曝光/线索/意向/成交目标）\n"
    "务实、可验收，避免空话。表格必须完整可复制。"
)


def run_ops(goal: str, brief: str, context: str = "") -> str:
    prompt = (
        f"战役目标：{goal}\n任务指令：{brief}\n上下文摘要：\n{context[:3000]}\n"
        "请严格按 SYSTEM 四段结构输出运营跟进方案（含 10 行跟进表）。"
    )
    allow_mock = bool(load_config().get("demo_mode", {}).get("allow_mock_llm", False))
    status = llm_client.provider_status()
    if not status.get("providers"):
        if allow_mock:
            rows = "\n".join(
                [
                    f"| C{i:02d} | 政企数字化意向{i} | 社群/私信 | "
                    f"您好，看到您在关注 AI 获客，成军台可一周拉起内容+跟进矩阵… | "
                    f"P{1 if i <= 3 else (2 if i <= 7 else 3)} | D+{i} |"
                    for i in range(1, 11)
                ]
            )
            return (
                f"# 运营跟进方案（结构演示）\n\n## 目标\n{goal}\n\n"
                f"## 本周节奏\n- D1 发布种草内容\n- D2-D5 跟进 P1/P2\n- D6 复盘导出 Word 周报\n\n"
                f"## 意向客户跟进表\n"
                f"| ID | 客户画像 | 触达渠道 | 首触话术摘要 | 优先级 | 下次跟进日 |\n"
                f"|---|---|---|---|---|---|\n{rows}\n\n"
                f"## 渠道投放计划\n"
                f"| 渠道 | 动作 | 素材 | 验收标准 |\n|---|---|---|---|\n"
                f"| 小红书/公众号 | 发 3 条种草 | 内容官话术包 | 阅读≥200 / 留资≥5 |\n"
                f"| 社群 | 日报+答疑 | 跟进话术 | 意向回复≥8 |\n"
                f"| 私域 | 一对一跟进 | 跟进表 P1 | 预约演示≥3 |\n\n"
                f"## 转化指标\n- 线索 30 → 意向 10 → 演示 3\n\n> ⚠️ mock 演示稿\n"
            )
        raise RuntimeError("运营官：无可用 LLM provider")
    out = llm_client.call_llm(prompt, fallback="", system_prompt=SYSTEM, temperature=0.5, thinking=False)
    if not out:
        llm_client.bump_fail()
        if allow_mock:
            return f"# 运营方案（mock）\n\n{goal}\n"
        raise RuntimeError("运营官：LLM 调用失败")
    llm_client.bump_ok()
    op_logger.log("agent_ops", "运营方案完成")
    return out
