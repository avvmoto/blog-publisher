"""blog-publisher — Playwright でブログ投稿操作を自動化するライブラリ。

公開 API は `publish()`。プラットフォーム実装は platforms/ 配下で
`register()` を使って登録する（Factory）。
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseBlogPlatform
from .config import collect_image_paths, load_config, load_credentials
from .params import (
    SUPPORTED_SITES,
    PublishParams,
    ValidationError,
    validate_params,
)

__version__ = "0.1.0"

__all__ = [
    "publish",
    "register",
    "get_platform",
    "PublishParams",
    "ValidationError",
    "BaseBlogPlatform",
]

# site 名 -> 実装クラス。各プラットフォームが import 時に register で登録する。
_REGISTRY: dict[str, type[BaseBlogPlatform]] = {}


def register(site: str):
    """プラットフォーム実装クラスを site 名で登録するデコレータ。"""

    def decorator(cls: type[BaseBlogPlatform]) -> type[BaseBlogPlatform]:
        _REGISTRY[site] = cls
        return cls

    return decorator


def get_platform(site: str) -> type[BaseBlogPlatform]:
    """site に対応する実装クラスを返す。

    意図はしているが未実装のサイトは NotImplementedError、そもそも想定外の
    サイトは ValidationError として、原因を区別できるようにする。
    """
    if site in _REGISTRY:
        return _REGISTRY[site]
    if site in SUPPORTED_SITES:
        raise NotImplementedError(
            f"{site!r} の実装は未登録です（platforms/ に追加してください）"
        )
    raise ValidationError(f"未対応のサイト: {site!r}")


def publish(
    site: str,
    post_file: str,
    image_dir: str,
    thumbnail: str | None = None,
    *,
    config_path: str | Path = "config.yaml",
    auth_dir: str | Path = "auth",
    dry_run: bool = False,
) -> None:
    """ブログへ投稿する。本文・画像・サムネイルは生成済みである前提。

    dry_run=True のときは公開直前で止まる（タイトル・本文・画像まで入力して停止）。

    I/O 境界として、検証 → 設定/認証読込 → 画像収集を行ってから、
    プラットフォーム実装の副作用メソッド群を run() で実行する。
    """
    params = PublishParams(
        site=site, post_file=post_file, image_dir=image_dir, thumbnail=thumbnail
    )
    validate_params(params)
    # I/O より前に Factory を解決し、未対応/未実装は早期に失敗させる。
    platform_cls = get_platform(site)

    config = load_config(config_path)
    credentials = load_credentials()
    platform = platform_cls(
        config=config.get(site, {}),
        credentials=credentials,
        auth_path=Path(auth_dir) / f"{site}.json",
    )

    image_paths = collect_image_paths(image_dir)
    platform.run(params, image_paths, dry_run=dry_run)


# プラットフォーム実装を登録する（register が定義された後に import する）。
from . import platforms  # noqa: E402, F401
