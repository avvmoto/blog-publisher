"""note.com プラットフォーム実装。

NOTE: ブラウザ操作コードはPlaywright E2E相当のためテスト対象外（CLAUDE.md 2a）。
parse_note_post() のみ純粋関数として分離しテスト対象とする。

認証: メール/パスワード（.env の NOTE_EMAIL, NOTE_PASSWORD）→ storage_state 保存・再利用。

エディター: note.com/notes/new → editor.note.com/notes/{id}/edit/ へリダイレクト。
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

    def run(
        self, params: PublishParams, image_paths: Sequence[str], dry_run: bool = False
    ) -> None:
        asyncio.run(self._post(params, list(image_paths), dry_run=dry_run))

    def _sel(self, key: str, default: str) -> str:
        """config.yaml の selectors[key] を返す。未設定なら default を使う。"""
        return self.config.get("selectors", {}).get(key, default) or default

    async def _post(
        self, params: PublishParams, image_paths: list[str], dry_run: bool = False
    ) -> None:
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

            ctx_kwargs: dict = {}
            if self.auth_path.exists():
                ctx_kwargs["storage_state"] = str(self.auth_path)

            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()

            # note.com/notes/new → ログイン済みなら editor.note.com へリダイレクト
            try:
                await page.goto(EDITOR_URL, wait_until="networkidle")
            except Exception as e:
                raise RuntimeError(f"エディターページへのアクセスに失敗しました: {e}") from e

            if "login" in page.url:
                logger.info("ログインが必要です")
                await self._do_login(page, email, password)
                await context.storage_state(path=str(self.auth_path))
                logger.info("認証情報を保存しました: %s", self.auth_path)
                await page.goto(EDITOR_URL, wait_until="networkidle")

            if "login" in page.url:
                await browser.close()
                raise RuntimeError(
                    "ログインに失敗しました。.env の NOTE_EMAIL / NOTE_PASSWORD を確認してください"
                )

            logger.info("エディターを開きました: %s", page.url)

            # ① タイトル
            title_sel = self._sel("title_input", 'textarea[placeholder="記事タイトル"]')
            await page.fill(title_sel, meta["title"])
            logger.info("タイトルを入力しました: %s", meta["title"])

            # ② 本文（keyboard.type でProseMirrorのトランザクションを正しく発火させる）
            if body:
                body_sel = self._sel("body_input", '[role="textbox"].ProseMirror')
                await page.locator(body_sel).click()
                await page.keyboard.press("Control+a")
                await page.keyboard.press("Delete")
                await page.keyboard.type(body, delay=0)
                await page.wait_for_timeout(800)
                logger.info("本文を入力しました")

            # ③ インライン画像をD&Dで末尾に追加
            thumb_resolved = Path(params.thumbnail).resolve() if params.thumbnail else None
            inline = [p for p in image_paths if Path(p).resolve() != thumb_resolved]
            if inline:
                await self._append_images(page, inline)

            # ④ ヘッダー画像（サムネイル）
            if params.thumbnail:
                await self._set_header_image(page, params.thumbnail)

            # ⑤ 公開設定ページ → タグ入力 → 投稿
            await self._publish(page, meta.get("tags", []), dry_run=dry_run)

            if not dry_run:
                logger.info("投稿完了: %s", page.url)
            await browser.close()

    async def _do_login(self, page, email: str, password: str) -> None:
        """メール/パスワードでログインし、ログイン後ページへの遷移を待つ。"""
        await page.goto(LOGIN_URL, wait_until="networkidle")

        await page.fill(self._sel("email_input", "#email"), email)
        await page.fill(self._sel("password_input", "#password"), password)
        await page.click(self._sel("login_button", 'button:has-text("ログイン")'))

        try:
            await page.wait_for_url(
                re.compile(r"note\.com(?!/login)"), timeout=15_000
            )
        except PlaywrightTimeout as e:
            raise RuntimeError(
                "ログイン後のリダイレクトがタイムアウトしました。認証情報を確認してください"
            ) from e

        logger.info("ログイン完了")

    async def _append_images(self, page, image_paths: list[str]) -> None:
        """本文末尾に画像をメニュー経由でアップロードする。

        各画像ごとに「メニューを開く」→「画像」→ファイルチューザーの手順を踏む。
        これはユーザーがD&Dで行う操作と同等のフローをFileChooserで代替したもの。
        """
        logger.info("インライン画像を追加中: %d 枚", len(image_paths))
        body_sel = '[role="textbox"].ProseMirror'
        menu_btn_sel = 'button[aria-label="メニューを開く"]'

        for image_path in image_paths:
            # カーソルを末尾に移動して新規段落を作る
            await page.locator(body_sel).click()
            await page.keyboard.press("Control+End")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(300)

            # メニューを開いて「画像」をクリック → ファイルチューザー
            try:
                async with page.expect_file_chooser(timeout=10_000) as fc_info:
                    await page.locator(menu_btn_sel).last.click()
                    await page.wait_for_timeout(300)
                    await page.locator('button:has-text("画像")').first.click()
                fc = await fc_info.value
                await fc.set_files(image_path)
                # アップロード完了まで待つ（ネットワークが落ち着くまで）
                await page.wait_for_load_state("networkidle", timeout=30_000)
                logger.info("画像を追加しました: %s", Path(image_path).name)
            except PlaywrightTimeout as e:
                logger.warning("画像アップロードがタイムアウトしました: %s — %s", image_path, e)

    async def _set_header_image(self, page, thumbnail: str) -> None:
        """ヘッダー画像（記事カバー）を設定する。

        「画像を追加」→「画像をアップロード」→ ファイルチューザー → クロップモーダル「保存」
        （DOM実測: 2026-06-01）
        """
        try:
            # パネルを開く
            await page.click('button[aria-label="画像を追加"]')
            await page.wait_for_timeout(500)
            # パネル内のアップロードボタン → ファイルチューザー
            async with page.expect_file_chooser(timeout=10_000) as fc_info:
                await page.locator('button:has-text("画像をアップロード")').first.click()
            fc = await fc_info.value
            await fc.set_files(thumbnail)
            # クロップモーダルはアップロード完了後に開く（タイムアウト60s で完了を兼ねて待機）
            await page.wait_for_selector(".CropModal__overlay", timeout=60_000)
            await page.locator(".CropModal__overlay").get_by_role(
                "button", name="保存", exact=True
            ).click()
            await page.wait_for_selector(
                ".CropModal__overlay", state="hidden", timeout=15_000
            )
            await page.wait_for_timeout(10_000)
            logger.info("ヘッダー画像を設定しました: %s", thumbnail)
        except PlaywrightTimeout as e:
            logger.warning("ヘッダー画像の設定がタイムアウトしました: %s", e)

    async def _publish(self, page, tags: list, dry_run: bool = False) -> None:
        """公開設定ページへ遷移し、タグを設定して投稿する。

        「公開に進む」クリック → editor.note.com/notes/{id}/publish/ へ遷移
        → ハッシュタグ入力 → 「投稿する」クリック
        dry_run=True のときはタグ入力後で停止する。
        （DOM実測: 2026-06-01）
        """
        publish_btn_sel = self._sel("publish_button", 'button:has-text("公開に進む")')
        await page.wait_for_timeout(500)  # React state の確定を待つ
        await page.click(publish_btn_sel)
        # /publish/ ページへの遷移を待つ（URL に /publish/ が含まれるまで）
        await page.wait_for_url(re.compile(r"/publish/"), timeout=30_000)
        logger.info("公開設定ページに遷移しました: %s", page.url)

        if tags:
            tag_input_sel = self._sel(
                "tag_input", 'input[placeholder="ハッシュタグを追加する"]'
            )
            tag_input = page.locator(tag_input_sel)
            for tag in tags:
                await tag_input.fill(str(tag))
                await tag_input.press("Enter")
                await page.wait_for_timeout(300)
                logger.info("タグを追加しました: %s", tag)

        if dry_run:
            logger.info("dry_run=True: タグ入力後で停止しました。ブラウザを確認してください。")
            input("確認後 Enter を押すとブラウザを閉じます...")
            return

        post_btn_sel = self._sel("post_button", 'button:has-text("投稿する")')
        await page.click(post_btn_sel)
        logger.info("投稿ボタンをクリックしました")
