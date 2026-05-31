"""note.com プラットフォーム実装。

NOTE: ブラウザ操作コードはPlaywright E2E相当のためテスト対象外（CLAUDE.md 2a）。
parse_note_post() のみ純粋関数として分離しテスト対象とする。

認証: メール/パスワード（.env の NOTE_EMAIL, NOTE_PASSWORD）→ storage_state 保存・再利用。
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

from blog_publisher import register
from blog_publisher.base import BaseBlogPlatform
from blog_publisher.params import PublishParams

logger = logging.getLogger(__name__)

LOGIN_URL = "https://note.com/login"
EDITOR_URL = "https://note.com/notes/new"
_POST_URL_PATTERN = re.compile(r"note\.com/[^/]+/n/[a-z0-9]+")


def parse_note_post(content: str) -> tuple[dict, str]:
    """Markdown frontmatter と本文を分離する（純粋関数）。

    frontmatter がある場合は meta dict と残りの本文を返す。
    frontmatter がない場合は空 dict と全文を返す。

    Examples::

        ---
        title: 記事タイトル
        tags: [タグ1, タグ2]
        ---
        本文テキスト
    """
    stripped = content.strip()
    if stripped.startswith("---"):
        m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)(.*)", stripped, re.DOTALL)
        if m:
            meta = yaml.safe_load(m.group(1)) or {}
            body = m.group(2).strip()
            return meta, body
    return {}, stripped


@register("note")
class NotePlatform(BaseBlogPlatform):
    """note.com 実装。全ブラウザ操作を run() の非同期コンテキストで完結させる。

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

    def _sel(self, key: str, default: str) -> str:
        """config.yaml の selectors[key] を返す。未設定なら default を使う。"""
        return self.config.get("selectors", {}).get(key, default) or default

    async def _post(self, params: PublishParams, image_paths: list[str]) -> None:
        post_file = Path(params.post_file)
        if not post_file.exists():
            raise FileNotFoundError(f"post_file が見つかりません: {params.post_file}")

        meta, body = parse_note_post(post_file.read_text(encoding="utf-8"))

        if not meta.get("title"):
            raise ValueError("post_file の frontmatter に title が設定されていません")

        if params.thumbnail and not Path(params.thumbnail).exists():
            raise FileNotFoundError(f"thumbnail が見つかりません: {params.thumbnail}")

        missing = [p for p in image_paths if not Path(p).exists()]
        if missing:
            raise FileNotFoundError(f"画像ファイルが見つかりません: {missing}")

        email = self.credentials.get("NOTE_EMAIL", "")
        password = self.credentials.get("NOTE_PASSWORD", "")
        if not email or not password:
            raise ValueError(".env に NOTE_EMAIL / NOTE_PASSWORD が設定されていません")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)

            if self.auth_path.exists():
                context = await browser.new_context(
                    storage_state=str(self.auth_path),
                    permissions=["clipboard-read", "clipboard-write"],
                )
            else:
                context = await browser.new_context(
                    permissions=["clipboard-read", "clipboard-write"],
                )

            page = await context.new_page()

            try:
                await page.goto(EDITOR_URL, wait_until="networkidle")
            except Exception as e:
                raise RuntimeError(f"エディターページへのアクセスに失敗しました: {e}") from e

            # セッション切れ or 未ログインの場合はログイン
            if "/login" in page.url or "/notes/new" not in page.url:
                logger.info("ログインが必要です")
                await self._do_login(page, email, password)
                await context.storage_state(path=str(self.auth_path))
                logger.info("認証情報を保存しました: %s", self.auth_path)
                await page.goto(EDITOR_URL, wait_until="networkidle")

            if "/login" in page.url:
                await browser.close()
                raise RuntimeError(
                    "ログインに失敗しました。.env の NOTE_EMAIL / NOTE_PASSWORD を確認してください"
                )

            logger.info("エディターを開きました: %s", page.url)

            # タイトル入力
            title_sel = self._sel("title_input", '[data-placeholder="タイトル"]')
            await page.click(title_sel)
            await page.fill(title_sel, meta["title"])
            logger.info("タイトルを入力しました: %s", meta["title"])

            # 本文入力（execCommand で貼り付け）
            if body:
                body_sel = self._sel("body_input", ".ProseMirror")
                await page.click(body_sel)
                await page.keyboard.press("Control+a")
                await page.evaluate(
                    "(text) => document.execCommand('insertText', false, text)", body
                )
                await page.wait_for_timeout(500)
                logger.info("本文を入力しました")

            # インライン画像アップロード（thumbnail と同一パスは除外）
            if image_paths:
                await self._upload_inline_images(page, image_paths, params.thumbnail)

            # ヘッダー画像設定
            if params.thumbnail:
                await self._set_header_image(page, params.thumbnail)

            # 公開設定 → タグ → 投稿
            await self._publish(page, meta.get("tags", []))

            try:
                await page.wait_for_url(_POST_URL_PATTERN, timeout=30_000)
            except PlaywrightTimeout as e:
                await browser.close()
                raise RuntimeError(
                    "投稿後のページ遷移がタイムアウトしました。"
                    "投稿は完了している可能性があります。note.com で確認してください。"
                ) from e

            logger.info("投稿完了: %s", page.url)
            await browser.close()

    async def _do_login(self, page, email: str, password: str) -> None:
        """メール/パスワードでログインし、ログイン後ページへの遷移を待つ。"""
        await page.goto(LOGIN_URL, wait_until="networkidle")

        email_sel = self._sel("email_input", 'input[name="email"]')
        password_sel = self._sel("password_input", 'input[name="password"]')
        login_btn_sel = self._sel("login_button", 'button[type="submit"]')

        await page.fill(email_sel, email)
        await page.fill(password_sel, password)
        await page.click(login_btn_sel)

        try:
            await page.wait_for_url(
                re.compile(r"note\.com(?!/login)"), timeout=15_000
            )
        except PlaywrightTimeout as e:
            raise RuntimeError(
                "ログイン後のリダイレクトがタイムアウトしました。"
                "認証情報を確認してください"
            ) from e

        logger.info("ログイン完了")

    async def _upload_inline_images(
        self, page, image_paths: list[str], thumbnail: str | None
    ) -> None:
        """エディター内にインライン画像を追加する。

        thumbnail と同一パスはヘッダー画像として別途設定するためスキップする。
        """
        thumb_resolved = Path(thumbnail).resolve() if thumbnail else None
        inline = [p for p in image_paths if Path(p).resolve() != thumb_resolved]
        if not inline:
            return

        logger.info("インライン画像をアップロード中: %d 枚", len(inline))
        image_input_sel = self._sel(
            "image_upload_input", 'input[type="file"][accept*="image"]'
        )
        try:
            upload_input = page.locator(image_input_sel).first
            await upload_input.set_input_files(inline)
            await page.wait_for_timeout(3000)
        except PlaywrightTimeout as e:
            logger.warning(
                "インライン画像のアップロードがタイムアウトしました。"
                "config.yaml の image_upload_input セレクターを確認してください: %s",
                e,
            )

    async def _set_header_image(self, page, thumbnail: str) -> None:
        """ヘッダー画像（記事カバー画像）を設定する。"""
        thumb_btn_sel = self._sel("thumbnail_button", 'button[aria-label*="ヘッダー"]')
        try:
            await page.click(thumb_btn_sel)
            file_input = page.locator('input[type="file"]').last
            await file_input.set_input_files(thumbnail)
            await page.wait_for_timeout(2000)
            logger.info("ヘッダー画像を設定しました: %s", thumbnail)
        except PlaywrightTimeout as e:
            logger.warning(
                "ヘッダー画像の設定がタイムアウトしました。"
                "config.yaml の thumbnail_button セレクターを確認してください: %s",
                e,
            )

    async def _publish(self, page, tags: list) -> None:
        """公開設定モーダルを開き、タグを設定して投稿する。"""
        publish_btn_sel = self._sel("publish_button", 'button:has-text("公開設定")')
        await page.click(publish_btn_sel)
        await page.wait_for_timeout(1000)

        if tags:
            tag_input_sel = self._sel("tag_input", 'input[placeholder*="タグ"]')
            tag_input = page.locator(tag_input_sel)
            for tag in tags:
                await tag_input.fill(str(tag))
                await tag_input.press("Enter")
                await page.wait_for_timeout(300)

        post_btn_sel = self._sel("post_button", 'button:has-text("投稿する")')
        await page.click(post_btn_sel)
        logger.info("投稿ボタンをクリックしました")
