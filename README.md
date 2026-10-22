# Web Crawling Search

[![CI](https://github.com/frankwyf/web_crawling/actions/workflows/ci.yml/badge.svg)](https://github.com/frankwyf/web_crawling/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/frankwyf/web_crawling)](https://github.com/frankwyf/web_crawling/releases)

A small Python HTML crawler and inverted-index search tool with a CLI, local web UI, JSON API, and offline benchmark. Crawl an authorized same-origin site, save a portable JSON index, then search it without contacting the site again.

**Status:** pre-1.0, intended for learning, local search, and small authorized crawls. Python 3.10–3.12 is tested on Linux; Python 3.12 is also tested on macOS and Windows. The search API and existing index field names remain compatible in v0.2.0.

## Try it offline

From an installed release or development environment:

```sh
web-crawling --version
web-crawling demo
web-crawling find crawler --index-file demo_index.json
web-crawling web --index-file demo_index.json
```

The demo uses two bundled HTML pages, creates `demo_index.json` and `demo_report.json` in your working directory, and makes no network requests. Its `example.invalid` URLs are sample document identifiers. The default demo output files are replaced on subsequent demo runs; pass `--index-file` and `--report-file` to choose other paths.

Open <http://127.0.0.1:8000/> for search, `/dashboard` for analytics, or `/portfolio` for the project overview. Stop the development server with Ctrl+C. `python -m web_crawling` and the legacy `python search.py` entry points are supported. Running without a command opens the interactive shell.

## Install a release

Download the wheel from [GitHub Releases](https://github.com/frankwyf/web_crawling/releases). Each new release includes a wheel, source distribution, and `SHA256SUMS`. Create a project-local `.venv`, then install the downloaded wheel with that environment's Python. The package is distributed through GitHub Releases; these instructions do not assume a PyPI publication.

For an external SSD setup, first verify the repository's physical path, mounted device, filesystem and free space (`pwd -P`, `diskutil info`, `df -h` on macOS). Stop if the intended volume is unavailable. Before creating environments or installing anything, use the storage configuration below; it keeps dependency caches, managed interpreters, tools and temporary files under this repository's `.venv`.

## Development setup

macOS / Linux, from the repository root:

```sh
. ./scripts/dev_env.sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m web_crawling demo
.venv/bin/python -m pytest
```

Windows PowerShell:

```powershell
. .\scripts\dev_env.ps1
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m web_crawling demo
.\.venv\Scripts\python -m pytest
```

For a runtime-only source install, use `requirements.txt` instead. After installing a release wheel, use the same interpreter with `-m web_crawling` if the console script is not on PATH. Cache redirects affect this shell and its child processes; macOS and existing applications can still create their own small system caches.

## Crawl your own authorized site

```sh
python -m web_crawling build --base-url https://example.org --profile generic --max-pages 50 --politeness-interval 1 --index-file site.json --report-file site-report.json
python -m web_crawling find search terms --index-file site.json
```

The generic profile extracts the title and first `<main>` or `<article>`, falling back to the body. Scripts, styles, navigation, forms and similar non-content nodes are excluded. It starts at the supplied URL and may seed same-origin URLs from `/sitemap.xml`. It adds no login seed.

The explicit Quotes to Scrape profile preserves the original selectors and `/login` seed:

```sh
python -m web_crawling build --base-url https://quotes.toscrape.com --profile quotes --max-pages 50
```

Add `--crawl-mode async --async-concurrency 4` for asynchronous crawling. The returned/indexed pages and discovered links must match the starting scheme, hostname and effective port. Redirect responses are checked after the HTTP client follows them; this is **not** a network sandbox or SSRF defense.

Query parameters that distinguish content are preserved, including their order and repetitions. Form encoding normalizes spaces to `+`. Case-insensitive `utm_*`, `gclid`, `dclid`, `fbclid`, `msclkid`, `mc_cid`, and `mc_eid` are removed; unknown fields such as `ref` remain. Query ordering can therefore still create distinct crawl URLs.

Flat namespaced and unnamespaced sitemap URL sets are supported using the Python standard library. Malformed XML is ignored; recursive sitemap indexes are not traversed.

**Crawl responsibly:** obtain authorization and check the site's terms and robots policy yourself. Automatic robots enforcement, host-wide async rate limiting and async retry parity are not implemented yet. Sync mode retries selected transient HTTP failures. Use the local UI with trusted indexes and URLs; its Flask development server is not a hardened public service.

## Data and command contract

Indexes retain the existing term-to-postings JSON format (`Page`, `URL`, `Frequency`, `Positions`, `Links`). Reads now validate this structure before replacing in-memory state; `load` always reads the requested file. Old malformed files may need rebuilding. See [index format and recovery](docs/index-format.md).

Index and report files are written completely to a sibling temporary file before replacement. A zero-page crawl fails without replacing an existing index. Each file is replaced separately: the index/report pair is not one transaction. CLI operational errors go to stderr and exit with status 1; argument errors use status 2.

## API and quality checks

The local UI exposes `/api/search?q=crawler`, `/api/export?q=crawler&format=json`, `/api/insights`, `/api/insights/export`, `/api/crawl/report`, `/api/performance/history`, and `/health`. [API reference](docs/api.md) covers pagination, sorting and result buckets.

```sh
python -m ruff check .
python -m coverage run -m pytest
python -m coverage report -m
python -m web_crawling benchmark --index-file invert_index.json --history-file logs/perf_history.jsonl --runs 3
python -m build
python scripts/check_package.py --dist dist --venv "$TMPDIR/package-smoke"
```

The last command installs the built wheel and its dependencies into a new disposable environment; choose a new external-SSD path for local use. Tests reject non-loopback socket connections and use fixtures/Mocks. CI enforces branch coverage of at least 65%, checks five OS/Python combinations, builds/installs packages on all three operating systems, and audits installed dependencies with pip-audit. The dependency audit contacts the advisory service; crawler and search tests remain offline. Release tags rerun these gates before publication.

See [contributing](CONTRIBUTING.md), [architecture](docs/architecture.md), [roadmap](docs/roadmap.md), [release procedure](docs/releasing.md), [changelog](CHANGELOG.md), and [security policy](SECURITY.md). Licensed under [MIT](LICENSE).
