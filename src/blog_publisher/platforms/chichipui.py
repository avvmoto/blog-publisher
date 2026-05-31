"""chichi-pui (ちちぷい) プラットフォーム実装。

NOTE: ブラウザ操作コードはPlaywright E2E相当のためテスト対象外（CLAUDE.md 2a）。
parse_post_meta() のみ純粋関数として分離しテスト対象とする。

Cloudflare対策: playwright-stealth を使用。
認証: Googleログインのため初回は tools/save_auth.py で手動実施し
      auth/chichipui.json に storage_state を保存。以降は再利用。
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Sequence

import yaml
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from blog_publisher import register
from blog_publisher.base import BaseBlogPlatform
from blog_publisher.params import PublishParams

logger = logging.getLogger(__name__)

UPLOAD_URL = "https://www.chichi-pui.com/posts/upload/"
_POST_URL_PATTERN = re.compile(r".+/posts/[a-z0-9-]+/$")


def parse_post_meta(content: str) -> dict:
    """YAML または Markdown frontmatter を辞書に変換する（純粋関数）。

    plain YAML:
        title: タイトル
        tags: [女の子, オリジナル]

    Markdown frontmatter:
        ---
        title: タイトル
        tags: [女の子]
        ---
        本文（無視される）
    """
    stripped = content.strip()
    if stripped.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---", stripped, re.DOTALL)
        if m:
            return yaml.safe_load(m.group(1)) or {}
    try:
        return yaml.safe_load(stripped) or {}
    except yaml.YAMLError:
        return {}


@register("chichipui")
class ChichiPuiPlatform(BaseBlogPlatform):
    """ちちぷい実装。全ブラウザ操作を run() の非同期コンテキストで完結させる。

    BaseBlogPlatform の抽象メソッドは Playwright のセッションを跨げないため
    テンプレートメソッドパターンは使わず run() をオーバーライドする。
    login / import_article / upload_images / set_thumbnail はスタブ。
    """

    def login(self) -> None:
        pass

    def import_article(self, post_file: str) -> None:
        pass

    def upload_images(self, image_paths: Sequence[str]) -> None:
        pass

    def set_thumbnail(self, thumbnail: str) -> None:
        pass

    def run(self, params: PublishParams, image_paths: Sequence[str]) -> None:
        asyncio.run(self._post(params, list(image_paths)))

    async def _post(self, params: PublishParams, image_paths: list[str]) -> None:
        post_file = Path(params.post_file)
        if not post_file.exists():
            raise FileNotFoundError(f"post_file が見つかりません: {params.post_file}")

        meta = parse_post_meta(post_file.read_text(encoding="utf-8"))

        if not meta.get("title"):
            raise ValueError("post_file に title が設定されていません")

        # サムネイル（=先頭画像）を決定する。
        # ちちぷいは最初にアップロードした画像がカバー画像になる仕様のため、
        # thumbnail 指定があればそれを先頭に並び替える。
        if params.thumbnail:
            thumb = Path(params.thumbnail).resolve()
            ordered = [str(thumb)] + [
                p for p in image_paths if Path(p).resolve() != thumb
            ]
        else:
            ordered = image_paths

        if not ordered:
            raise ValueError("アップロードする画像がありません")

        missing = [p for p in ordered if not Path(p).exists()]
        if missing:
            raise FileNotFoundError(f"画像ファイルが見つかりません: {missing}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=str(self.auth_path))
            await Stealth().apply_stealth_async(context)
            page = await context.new_page()

            try:
                await page.goto(UPLOAD_URL, wait_until="networkidle")
            except Exception as e:
                raise RuntimeError(f"投稿ページへのアクセスに失敗しました: {e}") from e

            title = await page.title()
            if "Cloudflare" in title or "Attention Required" in title:
                await browser.close()
                raise RuntimeError(
                    "Cloudflare にブロックされました。しばらく待ってから再試行してください"
                )

            if "login" in page.url:
                await browser.close()
                raise RuntimeError(
                    "セッションが切れています。tools/save_auth.py を再実行してください"
                )

            logger.info("投稿ページを開きました: %s", page.url)

            # 画像アップロード（先頭がカバー画像）
            logger.info("画像をアップロード中: %d 枚", len(ordered))
            upload_input = page.locator("input.image_posts_upload_image_input").first
            await upload_input.set_input_files(ordered)
            await page.wait_for_timeout(1500)

            # タイトル（必須）
            await page.fill("input[name='title']", meta["title"])

            # キャプション
            if caption := meta.get("caption", ""):
                await page.fill("textarea[name='caption']", str(caption))

            # プロンプト（AI生成画像の生成プロンプト）
            if prompt := meta.get("prompt", ""):
                await page.fill("textarea[name='prompt']", str(prompt))

            # タグ（Enterで1件ずつ追加）
            tag_input = page.locator("input[placeholder*='タグを入力']")
            for tag in meta.get("tags", []):
                await tag_input.fill(str(tag))
                await tag_input.press("Enter")
                await page.wait_for_timeout(200)

            # 年齢制限（default: 1=全年齢）
            age = str(meta.get("age_limit", self.config.get("default_age_limit", 1)))
            await page.check(f"input[name='age_limit'][value='{age}']")

            # テイスト（default: 1=イラスト）
            taste = str(meta.get("taste", self.config.get("default_taste", 1)))
            await page.check(f"input[name='taste'][value='{taste}']")

            # 投稿する
            logger.info("投稿ボタンをクリックします")
            await page.locator("button.button.is-primary.is-large").click()

            try:
                await page.wait_for_url(_POST_URL_PATTERN, timeout=30_000)
            except PlaywrightTimeout as e:
                await browser.close()
                raise RuntimeError(
                    "投稿後のページ遷移がタイムアウトしました。"
                    "投稿は完了している可能性があります。ちちぷいで確認してください。"
                ) from e

            logger.info("投稿完了: %s", page.url)
            await browser.close()
