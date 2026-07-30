# -*- coding: utf-8 -*-
"""
刷新浙江政采网真实标讯 → bid_telecom.db

用法：
  python scripts/refresh_real_bids.py              # 增量抓取（全量区县）
  python scripts/refresh_real_bids.py --quick      # 快速：12 区县 + 跳过详情
  python scripts/refresh_real_bids.py --full-rebuild
  python scripts/refresh_real_bids.py --max-districts 20 --skip-detail
  python scripts/refresh_real_bids.py --timeout 600

退出码：0 成功；1 失败（保留库内上次成功数据）
"""
from __future__ import annotations

import argparse
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fetch_real_data as frd  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="刷新真实标讯到 bid_telecom.db")
    parser.add_argument("--full-rebuild", action="store_true")
    parser.add_argument("--fetch-only", action="store_true")
    parser.add_argument("--max-districts", type=int, default=0)
    parser.add_argument("--skip-detail", action="store_true")
    parser.add_argument("--quick", action="store_true", help="快速冒烟：12 区县 + skip-detail")
    parser.add_argument("--timeout", type=int, default=0, help="秒；超时后仍保留已写入数据，标记失败")
    parser.add_argument("--max-pages", type=int, default=0, help="category 每关键词最大页数")
    parser.add_argument("--page-size", type=int, default=0, help="category 每页条数")
    parser.add_argument("--days-back", type=int, default=0, help="发布日回溯天数")
    parser.add_argument("--with-districts", action="store_true", help="额外补区县首屏")
    args = parser.parse_args(argv)

    max_d = args.max_districts or (12 if args.quick else None)
    skip = args.skip_detail or args.quick

    print("=== 成军台 · 刷新真实标讯 ===")
    print(f"DB: {frd.DB_PATH}")
    before = frd.db_stats()
    print(
        f"刷新前: rows={before.get('row_count')} real={before.get('real_count')} "
        f"demo={before.get('demo_count')} last_refresh={before.get('last_refresh')}"
    )

    result_box = {"result": None}

    def _run():
        result_box["result"] = frd.run_fetch(
            full_rebuild=args.full_rebuild,
            fetch_only=args.fetch_only,
            max_districts=max_d,
            skip_detail=skip,
            max_pages=args.max_pages or None,
            page_size=args.page_size or None,
            days_back=args.days_back or None,
            use_district_crawl=args.with_districts,
        )

    if args.timeout and args.timeout > 0:
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=args.timeout)
        if t.is_alive():
            msg = f"超时 {args.timeout}s：抓取仍在后台线程，请查看 logs/fetch_status.json / fetch.log"
            print(f"[WARN] {msg}")
            frd.write_status(
                running=True,
                phase="timeout",
                ok=None,
                message=msg,
                error=msg,
            )
            # 不强制杀线程（daemon 会随进程退出）；这里退出码 1
            after = frd.db_stats()
            print(
                f"当前库: rows={after.get('row_count')} real={after.get('real_count')} "
                f"（可能含部分增量）"
            )
            return 1
    else:
        _run()

    result = result_box["result"] or {"ok": False, "error": "no result"}
    print("---")
    print(
        f"结果 ok={result.get('ok')} fetched={result.get('fetched')} "
        f"inserted={result.get('inserted')} rows={result.get('row_count')} "
        f"real={result.get('real_count')}"
    )
    if result.get("error"):
        print(f"错误: {result.get('error')}")
        print("操作建议: 检查网络/站点反爬；保留库内上次成功数据；稍后重试 --quick 或全量。")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
