"""投稿UIのHTML構造を調査するための一時スクリプト。実装後は削除してよい。"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

AUTH_PATH = "auth/chichipui.json"
OUT_PATH = "/tmp/chichipui_post.html"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=AUTH_PATH)
        await Stealth().apply_stealth_async(context)
        page = await context.new_page()

        # まずホームへ行き、投稿ボタンのhrefを探す
        await page.goto("https://www.chichi-pui.com/", wait_until="networkidle")
        # 投稿関連リンクを列挙
        links = await page.eval_on_selector_all("a", "els => els.map(e => ({text: e.textContent.trim(), href: e.href}))")
        post_links = [l for l in links if any(k in l['text'] for k in ["投稿", "作品", "アップ", "create", "upload", "post"])]
        print("投稿関連リンク:", post_links)
        await page.goto("https://www.chichi-pui.com/posts/upload/", wait_until="networkidle")
        print("URL:", page.url)
        print("Title:", await page.title())

        html = await page.content()
        Path(OUT_PATH).write_text(html, encoding="utf-8")
        print(f"HTML saved to {OUT_PATH} ({len(html)} bytes)")

        await browser.close()

asyncio.run(main())
