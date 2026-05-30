"""全プラットフォーム共通の抽象基底 `BaseBlogPlatform`。

具象メソッド（login / import_article / upload_images / set_thumbnail）は
Playwright によるブラウザ操作＝E2E 相当のため、各サブクラスで実装し、
本リポジトリのユニットテスト対象には含めない（CLAUDE.md 2a 参照）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from .params import PublishParams


class BaseBlogPlatform(ABC):
    """ブログ投稿操作の抽象基底。

    config はそのプラットフォーム用設定（URL・セレクタ等）、credentials は
    .env 由来の機密情報、auth_path は storage_state の保存/読込先。
    これらは外側（publish）から注入され、サブクラスはブラウザ操作に専念する。
    """

    def __init__(
        self,
        config: dict,
        credentials: dict,
        auth_path: str | Path,
    ) -> None:
        self.config = config
        self.credentials = credentials
        self.auth_path = Path(auth_path)

    @abstractmethod
    def login(self) -> None:
        """初回は手動ログイン→storage_state を auth_path に保存。以降は再利用。"""

    @abstractmethod
    def import_article(self, post_file: str) -> None:
        """本文ファイルをブログのインポート機能で取り込む。"""

    @abstractmethod
    def upload_images(self, image_paths: Sequence[str]) -> None:
        """複数画像をアップロードする（順序は呼び出し側で確定済み）。"""

    @abstractmethod
    def set_thumbnail(self, thumbnail: str) -> None:
        """指定の1枚をサムネイルに設定する。"""

    def run(self, params: PublishParams, image_paths: Sequence[str]) -> None:
        """4ステップを定型順で実行するテンプレートメソッド。

        image_paths は I/O 境界（publish）で収集・整列済みのものを受け取る。
        ここ自体はサブクラスの副作用メソッドを呼ぶだけで純粋ではない。
        """
        self.login()
        self.import_article(params.post_file)
        self.upload_images(image_paths)
        if params.thumbnail is not None:
            self.set_thumbnail(params.thumbnail)
