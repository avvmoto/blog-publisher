# blog-publisher — プロジェクト概要

## 目的

ブログ投稿操作（ログイン・本文インポート・画像アップロード・サムネイル設定）を
Playwright で自動化する **Python ライブラリ**。

## 利用形態

このリポジトリは単体CLIではなく、**他リポジトリから import して使う Python パッケージ**として設計する。

```python
# img-gen など他のリポジトリからの利用例
from blog_publisher import publish

publish(
    site="note",
    post_file="output/post.md",
    image_dir="output/images/",
    thumbnail="output/thumb.jpg",
)
```

## 自動化する操作

投稿に必要なコンテンツ（本文・画像・サムネイル）は事前に外部で生成済みであることを前提とする。
このライブラリは**投稿操作のみ**を担う。

| ステップ | 内容 |
|----------|------|
| 1. ログイン | 初回のみ手動 → `storage_state` 保存。以降は再利用 |
| 2. 本文インポート | 毎回異なるファイルをブログのインポート機能で取り込む |
| 3. 画像アップロード | 毎回異なるフォルダから複数画像をアップロード |
| 4. サムネイル設定 | 指定された1枚の画像をサムネイルとして設定 |

## 複数プラットフォーム対応

複数のブログサービスに対応する。プラットフォームごとに実装を分離する。

対応予定（追加していく）：
- note.com
- ちちぷい
- （その他）

## アーキテクチャ方針

- `src/blog_publisher/base.py` — `BaseBlogPlatform` (ABC) を定義
- `src/blog_publisher/platforms/` — プラットフォームごとの実装
- `auth/` — `storage_state` 保存ディレクトリ（`.gitignore` 必須）
- `config.yaml` — セレクタ・URL等の設定（プラットフォームごと）
- `.env` — ID・パスワード等の機密情報

## 技術スタック

- Python 3.12+
- Playwright (Python) + playwright-stealth（Cloudflare対策）
- uv（パッケージ管理）
- ruff（リンター）、mypy（型チェック）、pytest（テスト）

## 対応済みプラットフォーム

| サイト | 認証方式 | ステータス |
|--------|----------|-----------|
| ちちぷい (chichi-pui.com) | Google OAuth → storage_state | ✅ 実装済み |
| note.com | メール/パスワード → .env | ✅ 実装済み |

---

# Claude Code Rules

## PR workflow

機能追加・バグ修正はすべてフィーチャーブランチ → PR 経由。`main` への直接コミット・プッシュ禁止。

```bash
# ブランチ作成
git switch -c feat/<short-description>

# 実装 → コミット（複数可）

# PR 作成
gh pr create --title "<title>" --body "$(cat <<'EOF'
## What & Why

<説明>

## Checklist

- [x] ruff passes
- [x] mypy passes
- [x] pytest passes
EOF
)"
```

- ブランチ名は `feat/`, `fix/`, `chore/` プレフィックスを付ける
- PR タイトルは英語・70文字以内
- CI (ruff / mypy / pytest) が全部グリーンになってからマージする
- マージ後はブランチを削除する: `git branch -d feat/<name>`

## Git commits

- Never stage `auth/` or any file containing secrets/credentials
- Never stage `.env`
- Stage source files by name — avoid `git add .` or `git add -A`
- Always create a new commit (never amend without explicit instruction)
- Commit message: concise English, focus on "why" not "what"
- Always append `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`

## コード品質チェック（pre-commit hook で自動実行）

`.githooks/pre-commit` が ruff・mypy・pytest を自動実行する。
hook は初回セットアップ時に一度だけ有効化が必要:

```bash
git config core.hooksPath .githooks
```

ruff の自動修正: `uv run ruff check --fix src/ tests/`

## ロギング

ライブラリコード内では `print()` を使わない。必ず `logging` モジュールを使う。

```python
import logging
logger = logging.getLogger(__name__)

logger.info("投稿完了: %s", url)     # 正常系
logger.warning("...")                # 注意
logger.error("...")                  # エラー
```

呼び出し側（ユーザーのスクリプト）が `logging.basicConfig()` でレベルを制御する。

## エラーハンドリング

ユーザーが「何をすれば直るか」分かるメッセージを返す。例外の種類を使い分ける。

| 状況 | 使う例外 |
|------|----------|
| ファイルが存在しない | `FileNotFoundError("...パス...")` |
| 設定値・入力値が不正 | `ValueError("...何が不正か...")` |
| ブラウザ操作の失敗（Cloudflare・セッション切れ等） | `RuntimeError("...復旧手順...")` |

Playwright の `TimeoutError` は必ず catch し、「投稿完了している可能性がある」など復旧ヒントを添えて `RuntimeError` に変換する。

## デバッグ用スクリプト

調査・確認のために作る一時スクリプト（`tools/dump_*.py` 等）は `.gitignore` に追加する。
リポジトリに入れない。

## 新プラットフォーム追加時のチェックリスト

### Step 0（必須）：操作を録画してセレクターを確定する

**コードを一行も書く前に** `playwright codegen` で実際の操作を録画する。
推測でセレクターを書くと、デバッグに実装の何倍もの時間がかかる（note.com で実証済み）。

```bash
uv run playwright codegen https://<site-url>
```

録画する操作（この順に全部やること）：
1. ログイン（メール/パスワード or OAuth）
2. 新規投稿ページを開く
3. タイトル入力
4. 本文入力
5. インライン画像アップロード（`+`メニュー等）
6. ヘッダー/サムネイル画像アップロード（アップロード後のモーダルも含む）
7. 公開設定ページ/モーダルを開く
8. タグ入力
9. ★投稿ボタンは押さない

生成コードから以下を抜き出して `config.yaml` に書く：
- ログインフォームの input セレクター
- タイトル・本文エリアのセレクター
- 各ボタンのテキスト or aria-label
- 公開設定ページの URL パターン（モーダル vs ページ遷移）

### Step 1〜：実装

1. `params.py` の `SUPPORTED_SITES` に追加
2. `src/blog_publisher/platforms/<name>.py` を作成し `@register("<name>")` を付ける
3. `src/blog_publisher/platforms/__init__.py` に `from . import <name>` を追加
4. `config.yaml` に設定セクションを追加（Step 0 で確定したセレクターを記入）
5. `examples/post_<name>.md` を追加（利用例）
6. README・CLAUDE.md の対応プラットフォーム表を更新
7. 純粋ロジック（パーサー等）のテストを `tests/test_<name>.py` に追加
8. `publish(dry_run=True)` で本文→画像→公開設定ページまで動作確認してからコミット
9. コミット（pre-commit hook が ruff・mypy・pytest を自動検証する）

# AI Guidelines (Senior Engineer / Pragmatic TDD)

あなたは実用主義のシニアエンジニアです。以下の設計思想と厳格なルールに従ってコードを出力してください。ブラウザ操作のE2Eテストは不要です。

## 1. 開発ワークフロー（Interface First）
1. **インターフェース先行:** 実装の前に、入出力とエラー境界を定義したインターフェース（型・シグネチャ）を設計する。
2. **純粋なロジックの抽出:** 外部依存を持たない、本質的なビジネスロジックのみを切り出す。
3. **ミニマムTDD:** 実装前に、対象ロジックの最小限の「正常系」と「異常系」のテストを書く。

## 2. テストの絶対制約（厳守）
- **モック/スタブ禁止:** モックが必要な設計を避け、純粋関数としてロジックを分離すること。
- **外部アクセス・DBアクセス禁止:** API通信、ブラウザ操作、ファイルI/Oを含む副作用はテスト対象外。
- **遅いテスト禁止:** ミリ秒単位で終わる完全なステートレス・決定論的テストのみ書く。
- **カバレッジ非重視:** 網羅率は無視し、バグを防ぐ本質的なテストのみ書く。
- **既存分への遡及テスト不要:** テストは「今回改修・新規追加する範囲」にのみ順次追加する。

## 2a. テストを書かなくてよいケース
以下に該当する場合はテストを書かず、その理由をテストファイルのモジュールdocstringにコメントとして残す。

- **Playwrightによるブラウザ操作コード:** ページ遷移・クリック・ファイルアップロード等はE2E相当のため対象外。
- **設計が悪い既存コードを編集するとき:** 純粋関数に切り出せていないコードは無理にテストを書かない。リファクタ後に追加する旨を記す。
- **テストファイルのコメントで除外が明示されているとき:** `NOTE: …テストを書かない` と記載がある箇所には追加しない。

## 2b. テスト対象（純粋ロジック）の例
- 投稿パラメータのバリデーション
- 画像パスの収集・フィルタリングロジック
- プラットフォーム別の設定値マッピング
- CLIの引数パース結果の検証

## 2c. よいテストケースの観点
- **仕様記述になっているか:** 「この関数はこういう契約を持つ」が読める。テスト名はWHATではなくWHYを表す。
- **リファクタ耐性があるか:** 実装の内部構造ではなく、振る舞い（入力→出力の契約）を検証する。
- **故障診断性があるか:** 落ちたとき「何が壊れたか」が一読で分かる。1テスト1観点。

## 3. Playwrightの設計方針
- **フォルダ構成:** `src/platforms/` 配下にサイト固有の実装を置く。`src/base_blog.py` に `BaseBlogPlatform` (ABC) を定義し、`login`, `upload_images`, `post_article` などを抽象メソッドとする。各プラットフォームのクラスはこれを継承する。
- **エントリーポイント:** `src/main.py` は `--site` 引数を argparse で受け取り、対応するクラスを動的に呼び出す Factory として機能させる。
- **設定と機密情報の分離:** セレクタ・URLは `config.yaml`、ID/パスワードは `.env` から `os.getenv` 経由で読み込む。ソースコードにベタ書きしない。
- **認証状態の保存・再利用:** ログインは初回のみ手動実施し `auth/<platform>.json` に `storage_state` として保存。以降は保存済み状態を使う。`auth/` は `.gitignore` に必須。
- **パラメータ化:** 投稿ファイル・画像フォルダ・サムネイルはCLI引数で受け取る。ハードコード禁止。
- **コードgen活用:** 新プラットフォーム追加時は `playwright codegen <url>` で操作を録画し、たたき台を生成してからリファクタする。

## 3a. Playwright 実装の既知の落とし穴（note.com 実装で判明）

**テキスト入力：**
- ProseMirror 等のリッチテキストエディターは `page.fill()` や `document.execCommand()` では React の内部 state が更新されない。`page.keyboard.type(text, delay=0)` を使うこと。
- React 管理の `<textarea>` には `page.fill()` で OK（DOM input event が発火するため）。

**ファイルアップロード：**
- `input[type="file"]` が DOM に常駐していないことが多い。`page.expect_file_chooser()` でボタンクリックを囲むパターンを使う。
- アップロードフローが多段になっている場合がある（例：ボタン → パネル → アップロードボタン → ファイル選択 → クロップモーダル → 保存）。codegen で全ステップを確認すること。

**タイミング：**
- `wait_for_load_state("networkidle")` はリクエスト開始前に解決する場合がある（race condition）。代わりに「処理完了を示す UI 要素の出現/消滅」を待つ。例：クロップモーダルはアップロード完了後に開く → モーダル出現待ちがアップロード完了の確認になる。
- モーダルが閉じた後も後処理（draft_save 等）が続くことがある。確実に待てない場合は固定スリープ（`wait_for_timeout`）も選択肢に入れる。

**公開フロー：**
- 「公開設定」が別ページ遷移になっているサービスがある（モーダルと決め打ちしない）。codegen で実際の URL の変化を確認する。

## 4. シニアエンジニアの思考
- **KISS & YAGNI:** 推測による過剰な抽象化を避け、テストを通すための最短・最簡潔な実装を行う。
- **副作用の局所化:** I/Oや状態（ファイルパス・認証情報）は外側に押し出し、コアドメインを純粋に保つ。
