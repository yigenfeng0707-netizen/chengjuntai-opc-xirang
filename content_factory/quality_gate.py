# -*- coding: utf-8 -*-
"""
第三层：质量门控 + 发布通道
1. 自动化规则校验：篇幅、代码完整性、无效链接、空段落筛查
2. 校验不通过输出整改建议；校验通过自动排版
3. 预留公众号草稿推送接口，参数统一外部配置
4. 全流程操作日志持久化 logs/
"""
import os
import re
import json
import datetime
from config_loader import ARTICLES_DIR, DATA_DIR, load_config
import op_logger

QA_REPORT = os.path.join(DATA_DIR, "qa_reports.json")


def check_article(article_text: str) -> dict:
    """自动化规则校验，返回校验结果与整改建议"""
    cfg = load_config().get("article", {})
    min_words = cfg.get("target_min_words", 800)
    require_code = cfg.get("require_code_block", True)
    issues = []

    # 1. 篇幅校验
    word_count = len(re.sub(r"\s", "", article_text))
    if word_count < min_words:
        issues.append(f"篇幅不足：{word_count}字 < {min_words}字")

    # 2. 代码块完整性（成对的 ```）
    code_blocks = re.findall(r"```", article_text)
    if len(code_blocks) % 2 != 0:
        issues.append("代码块不完整：``` 未成对闭合")

    # 3. 无效链接
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", article_text)
    for text, url in links:
        if url.startswith("http") and "example" in url:
            issues.append(f"疑似无效链接: {url}")

    # 4. 空段落筛查（连续空行）
    if re.search(r"\n\s*\n\s*\n\s*\n", article_text):
        issues.append("存在连续空段落")

    # 5. 占位符筛查
    placeholders = re.findall(r"\b(xxx|TODO|FIXME|待补充|占位)\b", article_text, re.I)
    if placeholders:
        issues.append(f"发现占位符: {placeholders}")

    passed = len(issues) == 0
    if require_code and "```" not in article_text:
        issues.append("缺少代码块（配置要求必须含代码）")
        passed = False

    suggestion = "" if passed else "请按以上问题点逐项整改后重新提交校验。"
    return {"pass": passed, "word_count": word_count, "issues": issues, "suggestion": suggestion}


def format_article(article_text: str) -> str:
    """校验通过自动排版：统一标题层级、清理多余空行"""
    text = re.sub(r"\n{3,}", "\n\n", article_text).strip()
    return text + "\n"


def run_quality_check(article_id: str = None, file_path: str = None) -> dict:
    """执行稿件质量校验"""
    if not file_path and article_id:
        # 通过 id 查找文件
        for fn in os.listdir(ARTICLES_DIR):
            if fn.startswith(article_id):
                file_path = os.path.join(ARTICLES_DIR, fn)
                break
    if not file_path or not os.path.exists(file_path):
        return {"error": f"稿件文件不存在: {file_path}"}

    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read()
    # 去掉 frontmatter
    body = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.S)

    result = check_article(body)
    if result["pass"]:
        formatted = format_article(body)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(raw.replace(body, formatted, 1))
        op_logger.log("quality_gate", f"{article_id or file_path} 校验通过，已自动排版")
    else:
        op_logger.log("quality_gate", f"{article_id or file_path} 校验未通过: {result['issues']}", level="WARN")

    # 持久化报告
    reports = []
    if os.path.exists(QA_REPORT):
        try:
            with open(QA_REPORT, "r", encoding="utf-8") as f:
                reports = json.load(f)
        except Exception:
            reports = []
    reports.append({"article_id": article_id, "file": file_path,
                    "ts": datetime.datetime.now().isoformat(), **result})
    with open(QA_REPORT, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    return result


def publish_to_wechat_draft(article_id: str) -> dict:
    """预留公众号草稿推送接口（参数统一外部配置，未配置返回未启用）"""
    op_logger.log("publish_wechat", f"公众号推送预占位调用[{article_id}]（未配置实际接口，跳过）", level="WARN")
    return {"status": "skipped", "reason": "公众号接口未配置，已预留"}


if __name__ == "__main__":
    sample = "# 测试\n## 引言\n正文内容\n```python\nprint(1)\n```\n"
    print(json.dumps(check_article(sample), ensure_ascii=False, indent=2))
