# Web Crawler and Search Tool

[中文](#中文说明) | [日本語](#日本語) | [English](#english)

## 中文说明

这是一个基于 Python 的课程项目，功能包括：

- 抓取 `https://quotes.toscrape.com`
- 提取页面文本并构建倒排索引
- 支持单词查询与短语查询
- 使用简单的链接数评分对结果进行排序

### 项目结构

- `search.py`：主程序，支持交互模式和命令行模式
- `invert_index.json`：已生成的示例倒排索引，可直接用于演示
- `requirements.txt`：运行依赖

### 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python .\search.py load
.\.venv\Scripts\python .\search.py print quotes
.\.venv\Scripts\python .\search.py find life is beautiful
```

### 交互模式

```powershell
.\.venv\Scripts\python .\search.py interactive
```

支持命令：`build`、`load`、`print <word>`、`find <phrase>`、`exit`

### 重新抓取并构建索引

```powershell
.\.venv\Scripts\python .\search.py build --politeness-interval 1
```

说明：仓库默认保留了一份 `invert_index.json`，这样无需重新抓取即可直接运行演示。

## 日本語

これは Python で書かれた授業課題ベースの小規模プロジェクトで、以下を行います。

- `https://quotes.toscrape.com` のクロール
- ページ本文の抽出と転置インデックスの作成
- 単語検索とフレーズ検索
- 外部リンク数を使った簡易ランキング

### ファイル構成

- `search.py`: メインスクリプト。対話モードと CLI モードの両方を提供
- `invert_index.json`: すぐ試せるサンプルインデックス
- `requirements.txt`: 必要な Python パッケージ

### セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python .\search.py load
.\.venv\Scripts\python .\search.py print quotes
.\.venv\Scripts\python .\search.py find life is beautiful
```

### 対話モード

```powershell
.\.venv\Scripts\python .\search.py interactive
```

利用可能なコマンドは `build`、`load`、`print <word>`、`find <phrase>`、`exit` です。

### インデックス再生成

```powershell
.\.venv\Scripts\python .\search.py build --politeness-interval 1
```

補足：デモをすぐに実行できるよう、生成済みの `invert_index.json` を同梱しています。

## English

This repository contains a small Python coursework project that:

- crawls `https://quotes.toscrape.com`
- extracts page text and builds an inverted index
- supports single-word and phrase queries
- applies a simple link-count-based ranking score

### Repository Layout

- `search.py`: main entry point with both interactive and CLI workflows
- `invert_index.json`: prebuilt sample index for quick demos
- `requirements.txt`: Python dependencies

### Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python .\search.py load
.\.venv\Scripts\python .\search.py print quotes
.\.venv\Scripts\python .\search.py find life is beautiful
```

### Interactive Mode

```powershell
.\.venv\Scripts\python .\search.py interactive
```

Available commands: `build`, `load`, `print <word>`, `find <phrase>`, `exit`

### Rebuild the Index

```powershell
.\.venv\Scripts\python .\search.py build --politeness-interval 1
```

The repository intentionally keeps a generated `invert_index.json` so the project can be demonstrated without recrawling the site first.