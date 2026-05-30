"""params.py の純粋ロジックに対する仕様テスト。

外部アクセス・モックなし、ミリ秒で終わる決定論的テストのみ（CLAUDE.md 2）。
検証対象は「契約（入力→結果/送出）」であり、内部実装には依存しない。
"""

import pytest

from blog_publisher.params import (
    PublishParams,
    ValidationError,
    filter_image_files,
    validate_params,
)


def _params(**overrides) -> PublishParams:
    """有効な既定値から、注目したい項目だけ差し替えてケースを作る。"""
    base = dict(
        site="note",
        post_file="output/post.md",
        image_dir="output/images/",
        thumbnail="output/thumb.jpg",
    )
    base.update(overrides)
    return PublishParams(**base)


# --- validate_params: 正常系 ---


def test_有効なパラメータは検証を通過する():
    # 契約: 問題がなければ何も送出せず None を返す
    assert validate_params(_params()) is None


def test_サムネイル省略は許容される():
    # 契約: thumbnail は任意。None ならサムネイル設定をスキップする要求として有効
    assert validate_params(_params(thumbnail=None)) is None


# --- validate_params: 異常系 ---


def test_未対応サイトは拒否される():
    with pytest.raises(ValidationError):
        validate_params(_params(site="unknown-blog"))


def test_対応サイトは引数で注入でき決定論的に判定される():
    # 既定では未対応の "foo" も、対応集合に入れれば通る（I/O非依存の確認）
    assert validate_params(_params(site="foo"), supported_sites={"foo"}) is None


def test_本文ファイルが空なら拒否される():
    with pytest.raises(ValidationError):
        validate_params(_params(post_file="   "))


def test_画像ディレクトリが空なら拒否される():
    with pytest.raises(ValidationError):
        validate_params(_params(image_dir=""))


def test_サムネイルが非画像拡張子なら拒否される():
    with pytest.raises(ValidationError):
        validate_params(_params(thumbnail="output/thumb.txt"))


# --- filter_image_files ---


def test_画像のみ抽出し非画像を除外する():
    names = ["a.png", "note.txt", "b.JPG", "readme.md", "c.webp"]
    assert filter_image_files(names) == ["a.png", "b.JPG", "c.webp"]


def test_結果は名前順で安定する():
    # 契約: アップロード順を再現可能にするため決定論的に整列して返す
    assert filter_image_files(["c.png", "a.png", "b.png"]) == [
        "a.png",
        "b.png",
        "c.png",
    ]


def test_画像が無ければ空リスト():
    assert filter_image_files(["x.txt", "y.doc"]) == []
