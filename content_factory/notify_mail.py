# -*- coding: utf-8 -*-
"""
模块7：邮件告警模块
1. 任务执行失败、连续重试失效、大批量内容生成完成触发邮件通知
2. 支持多收件人配置
3. 邮件附带简要执行日志、异常原因
4. SMTP 参数统一在 config.yaml 配置
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config_loader import load_config
import op_logger


def _smtp_ready() -> bool:
    cfg = load_config()
    return bool(cfg.get("smtp_server") and cfg.get("smtp_user") and cfg.get("mail_receivers"))


def send_mail(subject: str, body: str, level: str = "INFO") -> dict:
    """发送邮件告警；未配置 SMTP 时降级为仅记日志"""
    cfg = load_config()
    if not _smtp_ready():
        op_logger.log("notify_mail", f"[邮件未配置-降级] {subject}: {body[:200]}", level=level)
        return {"status": "skipped", "reason": "SMTP 未配置，已记录到日志"}
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[内容工厂告警] {subject}"
        msg["From"] = cfg["smtp_user"]
        msg["To"] = ",".join(cfg["mail_receivers"])
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP_SSL(cfg["smtp_server"], int(cfg.get("smtp_port", 465)), timeout=15)
        server.login(cfg["smtp_user"], cfg["smtp_password"])
        server.sendmail(cfg["smtp_user"], cfg["mail_receivers"], msg.as_string())
        server.quit()
        op_logger.log("notify_mail", f"邮件已发送: {subject} -> {cfg['mail_receivers']}")
        return {"status": "sent", "receivers": cfg["mail_receivers"]}
    except Exception as ex:
        op_logger.log("notify_mail", f"邮件发送失败: {ex}", level="ERROR")
        return {"status": "failed", "error": str(ex)}


def alert_task_failed(task_name: str, reason: str):
    send_mail(f"任务失败: {task_name}", f"任务 {task_name} 执行失败。\n原因: {reason}", level="ERROR")


def alert_batch_done(count: int):
    send_mail(f"批量生成完成({count}篇)", f"内容工厂批量内容生成完成，共{count}篇稿件。")


def test_mail_channel() -> dict:
    """测试邮件告警通道"""
    return send_mail("测试通知", "这是一条来自内容工厂的测试告警邮件。")
