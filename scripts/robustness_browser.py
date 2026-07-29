# -*- coding: utf-8 -*-
"""Browser robustness walk via Playwright (ASCII selectors only)."""
from __future__ import annotations

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8090"


def wait_health(timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(BASE + "/api/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    from playwright.sync_api import sync_playwright

    if not wait_health():
        print("FAIL: health not ready")
        return 1

    console_errors = []
    page_errors = []
    sethtml_skips = []
    notes = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.on("console", lambda msg: (
            console_errors.append(msg.text) if msg.type == "error"
            else sethtml_skips.append(msg.text) if (msg.type == "warning" and "setHTML skipped" in (msg.text or ""))
            else None
        ))
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(600)

        page.fill("#lu", "admin")
        page.fill("#lp", "chengjun2026")
        page.click('button[onclick="doLogin()"]')
        page.wait_for_selector("#appBox", state="visible", timeout=15000)
        page.wait_for_timeout(1000)

        for v in ["home", "campaigns", "artifacts", "nl2sql", "bid", "metrics", "factory", "logs", "users", "insights"]:
            page.locator(f'a.nav[data-v="{v}"]').click()
            page.wait_for_timeout(900)
            notes.append(f"nav:{v}")

        # factory tabs
        page.locator('a.nav[data-v="factory"]').click()
        page.wait_for_timeout(600)
        for ft in ["topics", "articles", "pipeline", "vector", "schedule", "queue", "bid"]:
            btn = page.locator(f'#ftabs button[data-ft="{ft}"]')
            if btn.count():
                btn.first.click()
                page.wait_for_timeout(700)
                notes.append(f"factoryTab:{ft}")

        # open campaign from list (race previously caused innerHTML null)
        page.locator('a.nav[data-v="campaigns"]').click()
        page.wait_for_timeout(800)
        open_btn = page.locator('#content button.btn.sm')
        if open_btn.count():
            open_btn.first.click()
            page.wait_for_timeout(1500)
            notes.append("opened_campaign")
            # preview if any
            prev = page.locator('button[onclick*="previewArtInline"], button:text-is("Preview")')
            # use Chinese via evaluate to avoid encoding in source file
            clicked = page.evaluate(
                """() => {
                  const btns = [...document.querySelectorAll('button')];
                  const p = btns.find(b => (b.textContent||'').includes('预览'));
                  if (p) { p.click(); return 'preview'; }
                  const o = btns.find(b => (b.textContent||'').includes('打开产物'));
                  if (o) { o.click(); return 'open_art'; }
                  return 'none';
                }"""
            )
            notes.append("art_action:" + clicked)
            page.wait_for_timeout(1000)

            # export word if button exists
            exp = page.evaluate(
                """() => {
                  const b = [...document.querySelectorAll('button')].find(x => (x.textContent||'').includes('导出 Word'));
                  if (!b) return 'no_btn';
                  b.click();
                  return 'clicked';
                }"""
            )
            notes.append("export_word:" + exp)
            page.wait_for_timeout(2500)

        # nl2sql
        page.locator('a.nav[data-v="nl2sql"]').click()
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('button')].find(x => (x.textContent||'') === '查询');
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(2500)
        notes.append("nl2sql_query")

        # artifacts -> factory preview path (known fragile)
        page.locator('a.nav[data-v="artifacts"]').click()
        page.wait_for_timeout(900)
        page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('button')].find(x => (x.textContent||'').includes('预览'));
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(1500)
        notes.append("artifacts_preview")

        # race: open then switch
        page.locator('a.nav[data-v="campaigns"]').click()
        page.wait_for_timeout(500)
        page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('#content button')].find(x => (x.textContent||'').includes('打开'));
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(80)
        page.locator('a.nav[data-v="metrics"]').click()
        page.wait_for_timeout(900)
        notes.append("race_open_then_metrics")

        # vector search empty-safe
        page.locator('a.nav[data-v="factory"]').click()
        page.wait_for_timeout(500)
        page.locator('#ftabs button[data-ft="vector"]').click()
        page.wait_for_timeout(400)
        page.fill("#vq", "MCP")
        page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('button')].find(x => (x.textContent||'') === '检索');
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(1200)
        notes.append("vector_search")

        browser.close()

    # Treat setHTML skips as failures for robustness (DOM missing = UX bug)
    hard_skips = [s for s in sethtml_skips if "articlePreview" in s or "campPanel" in s or "artBox" in s or "factoryBody" in s]

    report = {
        "ok": not console_errors and not page_errors and not hard_skips,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "sethtml_skips": sethtml_skips,
        "hard_skips": hard_skips,
        "notes": notes,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
