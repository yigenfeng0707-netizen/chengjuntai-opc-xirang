# -*- coding: utf-8 -*-
"""
司令 Agent：自然语言目标 → 结构化任务树（JSON）
禁止静默失败：LLM 不可用时抛错或返回明确 error 字段。
"""
import json
import re
import llm_client
import op_logger

TEMPLATES = {
    "lead_gen": {
        "name": "AI获客跟进",
        "roles": ["research", "content", "data", "ops", "review"],
        "hint": (
            "一人公司获客无人可用：拆成渠道调研、种草内容包、问数佐证、"
            "10人跟进表+话术、渠道投放节奏、可验收周报复盘"
        ),
    },
    "industry_brief": {
        "name": "行业综述沉淀",
        "roles": ["research", "content", "data", "review"],
        "hint": (
            "行业机会速研、中标/市场问数佐证、可入库长文综述、知识沉淀清单与下周行动"
        ),
    },
}

SYSTEM = """你是「成军台」司令 Agent。把用户目标拆成可执行任务树。
只输出 JSON，不要 Markdown 代码围栏。Schema:
{
  "summary": "一句话战役摘要",
  "hours_saved_est": 数字,
  "tasks": [
    {
      "id": "T1",
      "role": "research|content|data|ops|review",
      "title": "任务标题",
      "brief": "给执行 Agent 的指令（必须具体、可验收）",
      "depends_on": [],
      "needs_human_gate": false
    }
  ],
  "gate_message": "人审时需要确认的要点"
}
角色说明：
- research: 调研官 — 客群/渠道/竞品/机会点
- content: 内容官 — 可发布文案、话题、话术包
- data: 数据参谋 — NL2SQL 或市场问数佐证
- ops: 运营官 — 跟进表（≥10行）、节奏、渠道投放计划
- review: 复盘官 — 可验收周报要点 / Word 交付清单
任务 4~7 个，覆盖模板所需角色。
若模板是 AI获客跟进：ops 的 brief 必须要求输出「10条跟进表（客户画像/渠道/话术/优先级）+ 本周渠道投放计划」。
若模板是行业综述：content 的 brief 必须要求「机会点/风险/可落地知识库要点」三段齐全。"""


def _fallback_plan(goal: str, template: str) -> dict:
    """仅在显式允许 mock 时使用；默认演示路径不应静默走这里。"""
    tpl = TEMPLATES.get(template, TEMPLATES["lead_gen"])
    if template == "industry_brief":
        tasks = [
            {
                "id": "T1", "role": "research", "title": "行业趋势与机会速研",
                "brief": (
                    f"围绕「{goal}」输出：市场背景、3个机会点、3个风险、对标玩家、"
                    "可验证指标。Markdown 带标题。"
                ),
                "depends_on": [], "needs_human_gate": False,
            },
            {
                "id": "T2", "role": "data", "title": "中标/市场数据佐证",
                "brief": "查询通信/信息化相关项目按行业或地区的数量与金额，用于佐证综述。",
                "depends_on": ["T1"], "needs_human_gate": False,
            },
            {
                "id": "T3", "role": "content", "title": "撰写行业综述长文（可入库）",
                "brief": (
                    f"基于调研与数据写「{goal}」综述：机会点 / 风险 / 可落地知识库要点。"
                    "含小标题与条目列表，便于导出 Word。"
                ),
                "depends_on": ["T1", "T2"], "needs_human_gate": True,
            },
            {
                "id": "T4", "role": "review", "title": "知识沉淀与下周行动清单",
                "brief": "输出可入库条目、缺口、下周 TOP3 行动，标明可导出成军周报 Word。",
                "depends_on": ["T3"], "needs_human_gate": False,
            },
        ]
    else:
        tasks = [
            {
                "id": "T1", "role": "research", "title": "目标客群与渠道调研",
                "brief": (
                    f"调研获客路径「{goal}」：ICP 客群、3条主渠道、竞品观察、本周可试点动作。"
                ),
                "depends_on": [], "needs_human_gate": False,
            },
            {
                "id": "T2", "role": "content", "title": "种草内容与跟进话术包",
                "brief": (
                    f"产出可发布内容包「{goal}」：3条短文案、5个话题标签、"
                    "首触/跟进/逼单 3套话术。"
                ),
                "depends_on": ["T1"], "needs_human_gate": False,
            },
            {
                "id": "T3", "role": "data", "title": "市场情报问数佐证",
                "brief": "用 NL2SQL 问数补充行业热度（各行业项目数/金额），无法问数时显式标注非真实库。",
                "depends_on": ["T1"], "needs_human_gate": False,
            },
            {
                "id": "T4", "role": "ops", "title": "意向客户跟进表与渠道计划",
                "brief": (
                    "必须输出 Markdown：① 10 条跟进表（ID/画像/触达渠道/话术摘要/优先级/下次跟进日）；"
                    "② 本周渠道投放计划（渠道×动作×负责人×验收标准）；③ 转化漏斗指标。"
                ),
                "depends_on": ["T2"], "needs_human_gate": True,
            },
            {
                "id": "T5", "role": "review", "title": "战役复盘周报要点",
                "brief": "汇总产物与缺口，给出可验收周报结构，提示评委导出 Word 成军周报。",
                "depends_on": ["T3", "T4"], "needs_human_gate": False,
            },
        ]
    return {
        "summary": f"{tpl['name']}｜{goal[:60]}",
        "hours_saved_est": 6.0,
        "tasks": tasks,
        "gate_message": "请确认：跟进表/话术/渠道计划是否可验收，再放行执行",
        "_fallback": True,
    }


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("司令 Agent 未返回 JSON")
    return json.loads(m.group())


def plan_campaign(goal: str, template: str = "lead_gen", allow_mock: bool = False) -> dict:
    """
    生成任务树。
    allow_mock=False（默认）：LLM 全失败则抛 RuntimeError，禁止静默降级。
    """
    tpl = TEMPLATES.get(template)
    if not tpl:
        raise ValueError(f"未知模板: {template}")

    status = llm_client.provider_status()
    prompt = (
        f"战役模板：{tpl['name']}（{tpl['hint']}）\n"
        f"用户目标：{goal}\n"
        f"必须覆盖角色：{', '.join(tpl['roles'])}"
    )

    if not status.get("enabled") or not status.get("providers"):
        if allow_mock:
            op_logger.log("commander", "LLM 未配置，使用结构 fallback（已标注）", level="WARN")
            plan = _fallback_plan(goal, template)
            plan["llm_status"] = status
            return plan
        raise RuntimeError("LLM 未配置或无可用 provider，无法生成任务树。请配置息壤/星辰 TokenHub。")

    raw = llm_client.call_llm(
        prompt,
        fallback="",
        system_prompt=SYSTEM,
        temperature=0.3,
        max_tokens=2048,
        thinking=False,
    )
    if not raw:
        llm_client.bump_fail()
        if allow_mock:
            op_logger.log("commander", "LLM 返回空，使用结构 fallback", level="WARN")
            plan = _fallback_plan(goal, template)
            plan["llm_status"] = status
            return plan
        raise RuntimeError("司令 Agent LLM 调用失败（全部 provider 失败或返回空）。请检查息壤 API Key。")

    try:
        plan = _parse_json(raw)
    except Exception as ex:
        if allow_mock:
            op_logger.log("commander", f"JSON 解析失败，fallback: {ex}", level="WARN")
            plan = _fallback_plan(goal, template)
            plan["llm_status"] = status
            return plan
        raise RuntimeError(f"司令 Agent 输出无法解析为 JSON: {ex}") from ex

    tasks = plan.get("tasks") or []
    for i, t in enumerate(tasks):
        t.setdefault("id", f"T{i+1}")
        t.setdefault("depends_on", [])
        t.setdefault("needs_human_gate", False)
        t.setdefault("status", "pending")
        t.setdefault("result_artifact_id", None)
    plan["tasks"] = tasks
    plan["template"] = template
    plan["llm_status"] = status
    plan["_fallback"] = False
    llm_client.bump_ok()
    op_logger.log("commander", f"任务树生成完成 tasks={len(tasks)} provider={status.get('active_name')}")
    return plan
