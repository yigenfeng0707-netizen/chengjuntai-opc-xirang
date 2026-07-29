# -*- coding: utf-8 -*-
"""微信草稿推送单元/冒烟：默认 mock HTTP，不访问真实微信。"""
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "content_factory")
sys.path.insert(0, CF)

import wechat_publisher  # noqa: E402
import quality_gate  # noqa: E402


class TestMarkdownHtml(unittest.TestCase):
    def test_basic_md(self):
        html = wechat_publisher.markdown_to_wechat_html("# 标题\n\n一段**粗体**与`代码`\n\n```py\nprint(1)\n```\n")
        self.assertIn("<h1>", html)
        self.assertIn("<strong>粗体</strong>", html)
        self.assertIn("<pre><code>", html)


class TestCredentials(unittest.TestCase):
    def test_missing_is_not_configured(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in ("WECHAT_APP_ID", "WECHAT_APP_SECRET", "WECHAT_THUMB_MEDIA_ID"):
                os.environ.pop(k, None)
            with mock.patch.object(wechat_publisher, "_load_local_wechat_file", return_value={}):
                with mock.patch("wechat_publisher.load_config", return_value={}):
                    wechat_publisher._token_cache.update({"token": None, "expires_at": 0, "app_id": None})
                    self.assertFalse(wechat_publisher.credentials_configured())
                    st = wechat_publisher.status_summary()
                    self.assertFalse(st["configured"])
                    self.assertIn("未配置", st["hint"])

    def test_placeholder_rejected(self):
        creds = {"app_id": "YOUR_WECHAT_APP_ID", "app_secret": "YOUR_WECHAT_APP_SECRET"}
        self.assertFalse(wechat_publisher.credentials_configured(creds))

    def test_env_configured(self):
        with mock.patch.dict(os.environ, {
            "WECHAT_APP_ID": "wx1234567890abcd",
            "WECHAT_APP_SECRET": "abcdef0123456789abcdef0123456789",
        }):
            with mock.patch.object(wechat_publisher, "_load_local_wechat_file", return_value={}):
                with mock.patch("wechat_publisher.load_config", return_value={}):
                    self.assertTrue(wechat_publisher.credentials_configured())
                    st = wechat_publisher.status_summary()
                    self.assertTrue(st["configured"])
                    self.assertNotIn("abcdef0123456789", json.dumps(st))


class TestPublishFlow(unittest.TestCase):
    def test_skip_without_creds(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in ("WECHAT_APP_ID", "WECHAT_APP_SECRET"):
                os.environ.pop(k, None)
            with mock.patch.object(wechat_publisher, "_load_local_wechat_file", return_value={}):
                with mock.patch("wechat_publisher.load_config", return_value={}):
                    r = quality_gate.publish_to_wechat_draft("ART_FAKE")
                    self.assertEqual(r.get("status"), "skipped")
                    self.assertIn("未配置公众号凭证", r.get("reason", ""))
                    self.assertFalse(r.get("ok"))

    def test_draft_add_mocked(self):
        sample_md = os.path.join(CF, "articles")
        # pick any existing article id if present
        article_id = None
        if os.path.isdir(sample_md):
            for fn in os.listdir(sample_md):
                if fn.endswith(".md") and fn.startswith("ART"):
                    article_id = fn.split("_")[0]
                    if article_id.startswith("ART"):
                        break
        if not article_id:
            self.skipTest("无本地 articles 样例")

        env = {
            "WECHAT_APP_ID": "wx1234567890abcd",
            "WECHAT_APP_SECRET": "abcdef0123456789abcdef0123456789",
            "WECHAT_THUMB_MEDIA_ID": "THUMB_MEDIA_MOCK_ID_1234567890",
        }
        with mock.patch.dict(os.environ, env):
            with mock.patch.object(wechat_publisher, "_load_local_wechat_file", return_value={}):
                with mock.patch("wechat_publisher.load_config", return_value={}):
                    wechat_publisher._token_cache.update({"token": None, "expires_at": 0, "app_id": None})

                    def fake_get(url, timeout=20):
                        self.assertIn("token", url)
                        self.assertIn("grant_type=client_credential", url)
                        return {"access_token": "TOKEN_MOCK", "expires_in": 7200}

                    def fake_post(url, payload, timeout=20):
                        self.assertIn("draft/add", url)
                        self.assertIn("articles", payload)
                        art = payload["articles"][0]
                        self.assertTrue(art.get("title"))
                        self.assertTrue(art.get("content"))
                        self.assertEqual(art.get("thumb_media_id"), env["WECHAT_THUMB_MEDIA_ID"])
                        return {"media_id": "MEDIA_MOCK_DRAFT_001"}

                    with mock.patch.object(wechat_publisher, "_http_get_json", side_effect=fake_get):
                        with mock.patch.object(wechat_publisher, "_http_post_json", side_effect=fake_post):
                            r = wechat_publisher.publish_article_to_draft(article_id)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r.get("status"), "ok")
        self.assertEqual(r.get("media_id"), "MEDIA_MOCK_DRAFT_001")

    def test_ip_whitelist_error_loud(self):
        with mock.patch.dict(os.environ, {
            "WECHAT_APP_ID": "wx1234567890abcd",
            "WECHAT_APP_SECRET": "abcdef0123456789abcdef0123456789",
        }):
            with mock.patch.object(wechat_publisher, "_load_local_wechat_file", return_value={}):
                with mock.patch("wechat_publisher.load_config", return_value={}):
                    wechat_publisher._token_cache.update({"token": None, "expires_at": 0, "app_id": None})
                    with mock.patch.object(
                        wechat_publisher,
                        "_http_get_json",
                        return_value={"errcode": 40164, "errmsg": "invalid ip 1.2.3.4 not in whitelist"},
                    ):
                        r = wechat_publisher.get_access_token()
        self.assertFalse(r.get("ok"))
        self.assertIn("白名单", r.get("error", ""))


if __name__ == "__main__":
    unittest.main()
