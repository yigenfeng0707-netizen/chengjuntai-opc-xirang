# -*- coding: utf-8 -*-
"""写入标书演示项目清单（离线 demo，无需爬虫）。

用法:
  python scripts/seed_bid_demo.py
  python scripts/seed_bid_demo.py --force

产出:
  content_factory/data/bid_projects.json
  （若配置了 bid_pipeline_root，则写入 <root>/projects/project_list.json）

配套问数演示库:
  python seed_demo_db.py
  scripts\\start_nl2sql_demo.bat
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "content_factory")
if CF not in sys.path:
    sys.path.insert(0, CF)


def main():
    ap = argparse.ArgumentParser(description="Seed BidAutoPipeline demo projects")
    ap.add_argument("--force", action="store_true", help="覆盖已有清单")
    args = ap.parse_args()
    import bid_pipeline_link
    info = bid_pipeline_link.ensure_demo_projects(force=args.force)
    print("=== Bid demo seed ===")
    print(f"path:   {info['path']}")
    print(f"seeded: {info['seeded']}")
    print(f"count:  {info['count']}")
    print(f"ids:    {', '.join(info.get('ids') or [])}")
    print()
    print("Next:")
    print("  1) Web :8090 → 侧栏「标书工作台」查看项目清单")
    print("  2) 可选: scripts\\start_nl2sql_demo.bat 启动智能问数")
    print("  3) 文档: docs/BID_PIPELINE.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
