"""投稿パラメータの型と、外部依存を持たない純粋な検証ロジック。

このモジュールは I/O を一切行わない（ファイル存在確認などは publish() 側の
I/O 境界で行う）。ここに置くのは「与えられた値が投稿要求として筋が通っているか」
を判定する決定論的ロジックのみ。
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass

# 投稿として受け付ける画像拡張子（小文字・ドット付き）。
IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".webp"}
)

# 対応を「意図している」サイト。実装済みかどうかは get_platform() 側で判定する。
SUPPORTED_SITES: frozenset[str] = frozenset({"note", "chichipui"})


class ValidationError(ValueError):
    """投稿パラメータが不正なときに送出する。メッセージは何が不正かを述べる。"""


@dataclass(frozen=True)
class PublishParams:
    """publish() への入力一式。不変。

    thumbnail は任意（None ならサムネイル設定をスキップする契約）。
    """

    site: str
    post_file: str
    image_dir: str
    thumbnail: str | None = None


def validate_params(
    params: PublishParams, supported_sites: Collection[str] = SUPPORTED_SITES
) -> None:
    """パラメータが投稿要求として成立するか検証する。問題があれば送出する。

    supported_sites を引数で受けるのは、検証を I/O やグローバル状態から切り離し
    決定論的にテストできるようにするため（依存性注入）。
    成功時は None を返す（副作用なし）。
    """
    if params.site not in supported_sites:
        allowed = ", ".join(sorted(supported_sites)) or "(なし)"
        raise ValidationError(
            f"未対応のサイト: {params.site!r}（対応: {allowed}）"
        )
    if not params.post_file.strip():
        raise ValidationError("post_file が空です")
    if not params.image_dir.strip():
        raise ValidationError("image_dir が空です")
    if params.thumbnail is not None:
        if not params.thumbnail.strip():
            raise ValidationError("thumbnail が空文字です（不要なら None を渡す）")
        if not _has_image_extension(params.thumbnail):
            allowed = ", ".join(sorted(IMAGE_EXTENSIONS))
            raise ValidationError(
                f"thumbnail は画像拡張子である必要があります: "
                f"{params.thumbnail!r}（対応: {allowed}）"
            )


def filter_image_files(names: Iterable[str]) -> list[str]:
    """ファイル名の集合から画像のみを抽出し、決定論的に並べて返す。

    ディレクトリ走査（I/O）は呼び出し側の責務。ここは渡された名前の振り分けと
    並べ替えという純粋な変換のみを担う。並び順を固定するのはアップロード順を
    再現可能にするため。
    """
    images = [name for name in names if _has_image_extension(name)]
    return sorted(images)


def _has_image_extension(name: str) -> bool:
    """末尾の拡張子（大文字小文字無視）が画像拡張子集合に含まれるか。"""
    dot = name.rfind(".")
    if dot == -1:
        return False
    return name[dot:].lower() in IMAGE_EXTENSIONS
