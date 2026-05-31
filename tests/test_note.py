"""note.py の純粋ロジック（parse_note_post）に対する仕様テスト。

ブラウザ操作コード（NotePlatform._post）はE2E相当のためテスト対象外（CLAUDE.md 2a）。
"""

from blog_publisher.platforms.note import parse_note_post


def test_frontmatterと本文を正しく分離する():
    content = "---\ntitle: タイトル\n---\n本文テキスト"
    meta, body = parse_note_post(content)
    assert meta["title"] == "タイトル"
    assert body == "本文テキスト"


def test_タグリストを正しく解析する():
    content = "---\ntitle: T\ntags:\n  - タグ1\n  - タグ2\n---\n本文"
    meta, body = parse_note_post(content)
    assert meta["tags"] == ["タグ1", "タグ2"]
    assert body == "本文"


def test_frontmatterなしは空dictと全文を返す():
    content = "これは本文です"
    meta, body = parse_note_post(content)
    assert meta == {}
    assert body == "これは本文です"


def test_空の本文はempty_strを返す():
    content = "---\ntitle: T\n---"
    meta, body = parse_note_post(content)
    assert meta["title"] == "T"
    assert body == ""


def test_空文字列は空dictと空strを返す():
    meta, body = parse_note_post("")
    assert meta == {}
    assert body == ""


def test_本文に区切り線がある場合も正しく分離する():
    content = "---\ntitle: T\n---\n本文\n\n---\n区切り以降も本文"
    meta, body = parse_note_post(content)
    assert meta["title"] == "T"
    assert "区切り以降も本文" in body


def test_titleがない場合はNoneを返す():
    content = "---\ntags: [タグ]\n---\n本文"
    meta, body = parse_note_post(content)
    assert meta.get("title") is None
    assert body == "本文"


def test_複数行の本文を保持する():
    content = "---\ntitle: T\n---\n段落1\n\n段落2\n\n段落3"
    meta, body = parse_note_post(content)
    assert body == "段落1\n\n段落2\n\n段落3"
