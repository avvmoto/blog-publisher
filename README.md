# blog-publisher

ブログ投稿操作（ログイン・本文インポート・画像アップロード・サムネイル設定）を
Playwright で自動化する Python ライブラリ。他リポジトリから import して使う。

```python
from blog_publisher import publish

publish(
    site="note",
    post_file="output/post.md",
    image_dir="output/images/",
    thumbnail="output/thumb.jpg",
)
```

## セットアップ

```bash
uv sync
uv run playwright install chromium
cp .env.example .env   # ID/パスワードを記入
```

詳細な設計方針は [CLAUDE.md](CLAUDE.md) を参照。
