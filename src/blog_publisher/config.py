"""設定（config.yaml）と機密情報（.env）の読み込み、および画像ディレクトリ走査。

NOTE: このモジュールはファイル I/O・環境変数アクセスという副作用のみを担うため
ユニットテストは書かない（CLAUDE.md 2a）。純粋な振り分けロジックは params.py 側
（filter_image_files）にあり、そちらをテストする。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .params import filter_image_files


def load_config(config_path: str | Path) -> dict:
    """config.yaml を読み込んで dict で返す。"""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_credentials() -> dict[str, str]:
    """.env を読み込み、環境変数として見える値を dict で返す。

    ソースに機密をベタ書きしないため、値は呼び出し側で os.getenv 相当に参照する。
    ここでは load_dotenv で .env をプロセス環境へ反映するのが主目的。
    """
    load_dotenv()
    return dict(os.environ)


def collect_image_paths(image_dir: str | Path) -> list[str]:
    """ディレクトリ直下の画像ファイルを絶対パスで列挙する（I/O）。

    画像判定と整列という純粋な部分は filter_image_files に委譲する。
    """
    directory = Path(image_dir)
    names = [p.name for p in directory.iterdir() if p.is_file()]
    return [str(directory / name) for name in filter_image_files(names)]
