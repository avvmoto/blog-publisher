"""ちちぷいのログインセッションを auth/chichipui.json に保存するヘルパー。

Googleログインを使うため、Playwright内ブラウザではOAuth認証がブロックされる。
代わりにリアルなWindowsのChromeに接続してセッションをコピーする方式を使う。

使い方:
    1. PowerShellでChromeをデバッグポート付きで起動:
       & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 --user-data-dir="C:\\temp\\chrome-debug"
    2. このスクリプトを実行:
       uv run python tools/save_auth.py
    3. 開いたタブでGoogleログインを完了し、ターミナルでEnterを押す
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

AUTH_PATH = Path("auth/chichipui.json")
CDP_URL = "http://127.0.0.1:9222"
LOGIN_URL = "https://www.chichi-pui.com/"


async def main() -> None:
    async with async_playwright() as p:
        print(f"Chrome({CDP_URL})に接続中...")
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"接続失敗: {e}")
            print("Chromeが --remote-debugging-port=9222 で起動しているか確認してください")
            return

        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()

        pages = context.pages
        page = pages[0] if pages else await context.new_page()

        print(f"{LOGIN_URL} を開きます...")
        await page.goto(LOGIN_URL)

        print("\nGoogleログインを完了してください。")
        print("ログインできたら、このターミナルで Enter を押してください...")
        await asyncio.get_event_loop().run_in_executor(None, input)

        await context.storage_state(path=str(AUTH_PATH))
        print(f"✓ セッションを {AUTH_PATH} に保存しました")


if __name__ == "__main__":
    asyncio.run(main())
