# -*- coding: utf-8 -*-
"""
可选实网：将一篇稿件推送到微信公众号草稿箱。
仅当本机已配置 WECHAT_APP_ID/SECRET（或 config.wechat.local.yaml）时执行。
用法：
  python scripts/live_wechat_draft.py ART2026........
切勿在命令行 echo 完整 AppSecret。
"""
import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "content_factory")
sys.path.insert(0, CF)


def main():
    os.chdir(CF)
    import wechat_publisher

    st = wechat_publisher.status_summary()
    print(json.dumps(st, ensure_ascii=False, indent=2))
    if not st.get("configured"):
        print("\nSKIP: 未配置公众号凭证。请自行在本机填写 config.wechat.local.yaml 或环境变量。")
        print("见 docs/WECHAT_PUBLISH.md — 勿把密钥贴到聊天。")
        return 2

    aid = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not aid:
        arts = []
        adir = os.path.join(CF, "articles")
        if os.path.isdir(adir):
            for fn in sorted(os.listdir(adir)):
                if fn.endswith(".md") and fn.startswith("ART"):
                    arts.append(fn.split("_")[0])
                    break
        if not arts:
            print("用法: python scripts/live_wechat_draft.py <article_id>")
            return 2
        aid = arts[0]
        print(f"未指定 article_id，使用样例: {aid}")

    if not st.get("has_thumb_media_id") and not st.get("has_cover_image_path"):
        print("WARN: 未配置 thumb_media_id / cover_image，推送很可能失败（微信要求封面）。")

    result = wechat_publisher.publish_article_to_draft(aid)
    # 不打印任何可能含 secret 的调试 URL
    safe = {k: v for k, v in result.items() if k not in ("access_token", "app_secret")}
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("\nOK: 请到公众平台草稿箱核对。")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
