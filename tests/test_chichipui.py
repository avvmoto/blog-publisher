"""chichipui.py の純粋ロジック（parse_post_meta）に対する仕様テスト。

ブラウザ操作コード（ChichiPuiPlatform._post）はE2E相当のためテスト対象外
（CLAUDE.md 2a）。
"""

import pytest

from blog_publisher.platforms.chichipui import parse_post_meta


def test_plain_yamlを辞書に変換する():
    meta = parse_post_meta("title: タイトル\ncaption: キャプション")
    assert meta["title"] == "タイトル"
    assert meta["caption"] == "キャプション"


def test_タグリストを正しく解析する():
    meta = parse_post_meta("title: T\ntags:\n  - 女の子\n  - オリジナル")
    assert meta["tags"] == ["女の子", "オリジナル"]


def test_markdown_frontmatterを辞書に変換する():
    content = "---\ntitle: タイトル\ntags: [a, b]\n---\n本文（無視）"
    meta = parse_post_meta(content)
    assert meta["title"] == "タイトル"
    assert meta["tags"] == ["a", "b"]


def test_frontmatterの本文は無視される():
    content = "---\ntitle: T\n---\nこの本文は含まれない"
    meta = parse_post_meta(content)
    assert "本文" not in str(meta)
    assert set(meta.keys()) == {"title"}


def test_空文字列は空dictを返す():
    assert parse_post_meta("") == {}


def test_空のyamlは空dictを返す():
    assert parse_post_meta("{}") == {}


def test_数値フィールドを正しく読む():
    meta = parse_post_meta("title: T\nage_limit: 2\ntaste: 1")
    assert meta["age_limit"] == 2
    assert meta["taste"] == 1
