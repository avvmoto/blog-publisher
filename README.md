# blog-publisher

ブログ・画像投稿サイトへの投稿操作（画像アップロード・タイトル・タグ設定・公開）を
Playwright で自動化する Python ライブラリ。他リポジトリから import して使う。

```python
from blog_publisher import publish

# ちちぷい
publish(
    site="chichipui",
    post_file="post.yaml",
    image_dir="output/images/",
    thumbnail="output/thumb.png",  # 省略可。指定するとカバー画像になる
)

# note.com
publish(
    site="note",
    post_file="output/post.md",   # Markdown frontmatter（title/tags）+ 本文
    image_dir="output/images/",
    thumbnail="output/thumb.jpg",  # 省略可。ヘッダー画像になる
)
```

---

## セットアップ（初回のみ）

```bash
uv sync
uv run playwright install chromium
```

---

## ログイン認証について

### ちちぷい（Googleログイン）

パスワードの保存は不要。初回だけ手動ログインしてセッションを保存する。

**手順（初回 or セッション切れ時）:**

1. PowerShell で Chrome を起動:
   ```powershell
   & "C:\Program Files\Google\Chrome\Application\chrome.exe" `
     --remote-debugging-port=9222 `
     --remote-debugging-address=0.0.0.0 `
     --user-data-dir="C:\temp\chrome-debug"
   ```

2. WSL で実行:
   ```bash
   uv run python tools/save_auth.py
   ```

3. 開いたブラウザでちちぷいにGoogleログイン → ターミナルで Enter

以降は `auth/chichipui.json` のセッションが使われる。**Chrome の起動は不要**。
セッションが切れたら（数週間〜数ヶ月後）この手順をもう一度やるだけ。

### note.com（メール/パスワードログイン）

`.env` に記入するだけ。初回実行時に自動でログイン→セッション保存される。

```env
NOTE_EMAIL=your@email.com
NOTE_PASSWORD=yourpassword
```

`.env` は `.gitignore` に含まれており、git には入らない。

---

## 通常の使い方

### 投稿ファイル形式

**ちちぷい（YAML）**

```yaml
# post.yaml
title: "投稿タイトル"
caption: "キャプション（任意）"
tags:
  - 女の子
  - オリジナル
age_limit: 1   # 1=全年齢, 4=R-15, 2=R-18, 3=R-18G
taste: 1       # 1=イラスト, 2=フォト, 99=未分類
prompt: |      # AI生成プロンプト（任意）
  1girl, solo
```

**note.com（Markdown frontmatter）**

```markdown
---
title: "記事タイトル"
tags:
  - タグ1
  - タグ2
---

記事本文をここに書く。
```

### 投稿実行

```python
from blog_publisher import publish

# ちちぷい
publish(
    site="chichipui",
    post_file="post.yaml",
    image_dir="images/",
    thumbnail="images/cover.png",
)

# note.com
publish(
    site="note",
    post_file="post.md",
    image_dir="images/",
    thumbnail="images/cover.jpg",  # ヘッダー画像
)
```

---

## ファイル構成

```
blog-publisher/
├── src/blog_publisher/       # ライブラリ本体
│   ├── platforms/
│   │   ├── chichipui.py      # ちちぷい実装
│   │   └── note.py           # note.com 実装
│   ├── base.py               # BaseBlogPlatform (ABC)
│   ├── params.py             # PublishParams・バリデーション
│   └── config.py             # 設定・環境変数ローダー
├── tools/
│   └── save_auth.py          # ちちぷい初回ログイン用ヘルパー
├── auth/                     # セッション保存先（git管理外）
├── config.yaml               # URL・セレクター・デフォルト値
└── .env                      # 機密情報（git管理外）
```

---

## 対応プラットフォーム

| サイト | 認証方式 | 状態 |
|--------|----------|------|
| ちちぷい (chichi-pui.com) | Google OAuth | ✅ 実装済み |
| note.com | メール/パスワード | ✅ 実装済み |
