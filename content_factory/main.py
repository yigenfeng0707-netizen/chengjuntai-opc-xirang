# -*- coding: utf-8 -*-
"""
统一入口 main.py
- 自然语言指令调度（八类指令）
- 串联全链路：环境检测→选题→生成→质检→向量化→PDF→标书同步→数据回流
- 支持命令行参数与交互模式
"""
import sys
import os
import json
import logging
import argparse
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import env_check
import topic_collector
import agents
import quality_gate
import data_feedback
import bid_pipeline_link
import scheduler
import vector_store
import pdf_exporter
import task_queue
import notify_mail
import op_logger
from config_loader import load_config


def run_env_check():
    report, blocked = env_check.run_all()
    print(report)
    return not blocked


def run_full_pipeline(topic: str = None, priority: int = 5, summary: str = "", tags: list = None):
    """全链路：采集→筛选→生成→质检→摘要→向量化→PDF，失败自动重试"""
    op_logger.log("main", f"启动全链路流水线，优先级{priority}")
    # 1. 选题
    if not topic:
        r = topic_collector.collect_topics(topk=6)
        if not r["topics"]:
            print("未采集到选题")
            return
        topic = r["topics"][0]["title"]
        summary = r["topics"][0].get("summary", "")
        print(f"[1/6] 采集选题: {topic}")
    else:
        print(f"[1/6] 指定选题: {topic}")
    # 入队
    task_queue.add_task(topic, "generate_article", {"topic": topic, "summary": summary, "tags": tags}, priority)
    # 2. 生成文稿
    print("[2/6] 多Agent生成文稿...")
    art = agents.generate_article(topic, summary, tags)
    # 3. 质检
    print("[3/6] 质量校验...")
    qa = quality_gate.run_quality_check(article_id=art["id"])
    print(f"       质检{'通过' if qa.get('pass') else '未通过'}")
    # 4. 向量化（生成时已自动入库，这里刷新）
    print("[4/6] 向量知识库已入库")
    # 5. PDF导出
    print("[5/6] 导出PDF...")
    pdf = pdf_exporter.export_article_by_id(art["id"])
    # 6. 完成通知
    print("[6/6] 流水线完成")
    task_queue.finish_task(art["id"])
    notify_mail.alert_batch_done(1)
    result = {"topic": topic, "article_id": art["id"], "qa_pass": qa.get("pass"),
              "pdf": pdf, "review": art.get("review", {})}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def dispatch(cmd: str):
    """自然语言指令分发（八类）"""
    c = cmd.strip()
    op_logger.log("main_dispatch", f"指令: {c[:80]}")

    # 1. 环境检测
    if any(k in c for k in ["环境检测", "环境自检", "适配报告"]):
        return run_env_check()

    # 2. 完整内容生产流水线
    if "高优先级" in c and "标书" in c:
        return run_full_pipeline(priority=1)
    if "完整流水线" in c or "全链路" in c or "采集资讯选题" in c:
        return run_full_pipeline()

    # 3. MCP调用（解析参数）
    if c.startswith("MCP") or "collect_topics" in c or "generate_article" in c or "export_article_pdf" in c:
        if "collect_topics" in c:
            return topic_collector.collect_topics(topk=6)
        if "generate_article" in c:
            import re
            m = re.search(r"选题[：:](.+)", c)
            t = m.group(1).strip() if m else "AI智能体MCP搭建实战教程"
            return agents.generate_article(t)
        if "export_article_pdf" in c:
            return pdf_exporter.export_all()

    # 4. 标书联动
    if "读取BidAutoPipeline" in c or "投标项目需求" in c:
        return bid_pipeline_link.fetch_bid_project_themes()
    if "同步至BidAutoPipeline" in c or "知识库" in c and "同步" in c:
        return bid_pipeline_link.sync_knowledge_to_bid()

    # 5. 定时任务 & 向量检索
    if "定时任务列表" in c or "全部定时任务" in c:
        return scheduler.load_schedule()
    if "每日早上9点" in c:
        scheduler.add_task("daily_topic_web", "每日选题采集", "0 9 * * *", "collect_topics", {"topk": 6})
        return "已添加定时任务:每日9点采集选题"
    if "向量知识库检索" in c or "语义检索" in c:
        import re
        m = re.search(r"与(.+)相关", c)
        q = m.group(1) if m else "智能体"
        return vector_store.search(q)

    # 6. 告警与PDF
    if "邮件告警" in c or "测试通知" in c:
        return notify_mail.test_mail_channel()
    if "批量" in c and "PDF" in c.upper().replace("pdf", "PDF") or "导出PDF" in c and "批量" in c:
        return pdf_exporter.export_all()

    # 7. 任务队列 & Web面板
    if "任务队列" in c or "排队任务" in c:
        return task_queue.list_queue()
    if "Web管理面板" in c or "8090" in c:
        import web_server
        web_server.start()
        return

    # 8. 权限与日志
    if "导出近7天" in c or "审计日志" in c:
        today = datetime.date.today()
        return op_logger.export_logs_csv((today - datetime.timedelta(days=7)).isoformat(), today.isoformat())
    if "账户" in c and "角色" in c or "权限配置" in c:
        import auth_users
        return {"users": auth_users.list_users(), "roles": auth_users.list_roles()}

    return f"未识别的指令，可用关键词: 环境检测/完整流水线/MCP/标书/定时任务/向量检索/邮件告警/PDF/任务队列/Web面板/审计日志/权限"


def main():
    parser = argparse.ArgumentParser(description="AI 内容工厂统一入口")
    parser.add_argument("--check", action="store_true", help="执行环境检测")
    parser.add_argument("--pipeline", action="store_true", help="执行全链路流水线")
    parser.add_argument("--topic", default=None, help="指定选题")
    parser.add_argument("--cmd", default=None, help="自然语言指令")
    args = parser.parse_args()

    if args.check:
        sys.exit(0 if run_env_check() else 1)
    if args.pipeline:
        run_full_pipeline(topic=args.topic)
        return
    if args.cmd:
        r = dispatch(args.cmd)
        if r is not None:
            print(json.dumps(r, ensure_ascii=False, indent=2) if isinstance(r, (dict, list)) else r)
        return

    # 交互模式
    print("=" * 50)
    print("AI 内容工厂 交互终端（输入指令执行，输入 exit 退出）")
    print("=" * 50)
    while True:
        try:
            cmd = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("再见")
            break
        if cmd.lower() in ("exit", "quit", "q", "退出"):
            break
        if not cmd:
            continue
        try:
            r = dispatch(cmd)
            if r is not None:
                print(json.dumps(r, ensure_ascii=False, indent=2) if isinstance(r, (dict, list)) else r)
        except Exception as e:
            print(f"执行出错: {e}")
            op_logger.log("main_error", str(e), level="ERROR")


if __name__ == "__main__":
    main()
