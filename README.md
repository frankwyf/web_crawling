# Web Crawler and Search Tool

Lightweight Python crawler + inverted-index search project with CLI, web UI, JSON API, and analytics dashboard.

## What Is New In This Upgrade

This project has been upgraded from a basic crawler/search demo into a portfolio-grade Python crawling system:

- Resilient crawling engine with connection pooling and retry backoff.
- Async crawling mode with configurable concurrency.
- Internal-link traversal with optional sitemap seeding.
- Generic HTML content extraction by default, with an explicit Quotes to Scrape profile.
- Configurable crawl scale using `--max-pages`.
- Machine-readable crawl report export (`crawl_report.json`).
- Dashboard-level crawl quality visibility (`/api/crawl/report` + dashboard panel).
- Replayable benchmark history with regression detection (`logs/perf_history.jsonl`).
- Portfolio storyboard page combining crawl quality, query quality, and performance trend.
- Expanded quality pipeline: lint, tests, coverage gate, package build artifacts.
- Multi-version CI validation across Python 3.10 / 3.11 / 3.12.

## macOS Quick Start

The project supports Python 3.10 and later; use Python 3.12 for the local setup shown here. Create a project-local environment, install the development dependencies, run the tests, then load the included sample index:

When developing from an external SSD, create the cache and temporary directories on that volume, then verify that each path is on the mounted SSD before installing. Set `PIP_CACHE_DIR`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, and `TMPDIR` in the same shell that runs installation; for uv-based installs, set its cache, Python, and tool paths there too. In particular, verify `TMPDIR` exists and resolves to the external volume before installing.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m web_crawling load
```

## Install (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

For development:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

## Python Version Mapping

This project targets `>=3.10` and is validated on `3.10`, `3.11`, and `3.12`.

- CI mapping: GitHub Actions matrix in `.github/workflows/ci.yml`.
- Local mapping: `tox.ini` defines `py310`, `py311`, `py312`, and `lint` environments.

If you use `pyenv-win`, install the mapped versions first so `tox` can run all environments.

## Run

CLI and module entry points are equivalent:

```powershell
.\.venv\Scripts\python .\search.py load
.\.venv\Scripts\python -m web_crawling load
.\.venv\Scripts\python .\search.py print quotes
.\.venv\Scripts\python .\search.py find life is beautiful
.\.venv\Scripts\python .\search.py interactive
.\.venv\Scripts\python .\search.py build --politeness-interval 1
.\.venv\Scripts\python .\search.py build --politeness-interval 1 --max-pages 120 --report-file crawl_report.json
.\.venv\Scripts\python .\search.py build --crawl-mode async --async-concurrency 8 --max-pages 120
.\.venv\Scripts\python .\search.py benchmark --index-file invert_index.json --history-file logs/perf_history.jsonl --runs 3
```

Web UI:

```powershell
.\.venv\Scripts\python .\search.py web
```

## Crawl Profiles

The default `generic` profile indexes the document title and the first `<main>` or `<article>` section, falling back to the page body. It removes scripts, styles, navigation, forms, and other non-content sections before tokenizing. It starts at `--base-url` and may also seed same-origin URLs from the sitemap; it does not add a `/login` seed.

Use `--profile quotes` to enable the Quotes to Scrape selectors and its legacy `/login` seed behavior:

```sh
python -m web_crawling build --base-url https://quotes.toscrape.com --profile quotes --max-pages 120
```

For another site, the default profile can be used directly:

```sh
python -m web_crawling build --base-url https://example.org --profile generic --max-pages 120
```

Open `http://127.0.0.1:8000/` for search and `http://127.0.0.1:8000/dashboard` for analytics.

Portfolio visualization page: `http://127.0.0.1:8000/portfolio`

## Crawling Strategy

The crawler focuses on reliability and explainability:

- Uses a reusable HTTP session for better performance.
- Applies automatic retry policy to transient failures (`429/5xx`).
- Enforces request timeout and politeness interval.
- Follows only same-origin links and sitemap entries (matching scheme, hostname, and effective port), records same-origin redirect destinations, and rejects cross-origin redirects.
- Optionally seeds with `/sitemap.xml` URLs when available.

URL normalization keeps content query parameters, including repeated parameters, in their original order; it does not sort them. Query fields are decoded and re-encoded using standard form encoding, so spaces are written as `+`. It drops case-insensitive names matching `utm_*`, `gclid`, `dclid`, `fbclid`, `msclkid`, `mc_cid`, and `mc_eid`, while retaining unknown fields such as `ref` because they may affect page content.

After each build, a structured crawl report is generated to summarize quality and scale.

## API

- Search: `/api/search?q=life%20is%20beautiful`
- Export results: `/api/export?q=life%20is%20beautiful&format=json|csv`
- Dashboard insights: `/api/insights`
- Export dashboard report: `/api/insights/export?format=json|csv`
- Crawl report: `/api/crawl/report`
- Performance history: `/api/performance/history`
- Health check: `/health`

Query options:

- `page` defaults to `1`
- `limit` defaults to `20` and max is `200` for search, `100` for export
- `sort` supports `relevance`, `frequency_desc`, `score_desc`, `page_asc`, `page_desc`
- `bucket` supports `all`, `conjunctive`, `term_at_a_time`, `per_word`

API responses include `cached` and `took_ms`, and access logs rotate daily under `logs/access_YYYYMMDD.log`.

## Visual Validation

The Web UI now supports direct observability and verification links:

- Search page quick links for dashboard, JSON export, CSV export, and crawl report.
- Dashboard "Crawl Quality Snapshot" panel showing crawl totals and index scale.
- Portfolio page with three linked views: crawl quality, query quality, and performance trend.

This provides a visual checkpoint for crawl quality and search-system health.

## Testing

```powershell
.\.venv\Scripts\python -m pytest -q
```

Multi-version local test run (recommended):

```powershell
.\.venv\Scripts\python -m tox -e py310,py311,py312,lint
```

If some interpreters are missing locally, `tox` is configured to skip those environments while still running available ones.

Lint and coverage checks:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m coverage run -m pytest
.\.venv\Scripts\python -m coverage report -m
```

Coverage threshold is enforced in `pyproject.toml` and can be tightened over time as test depth increases.
Current gate is set to `65%` with branch coverage enabled.

## CI/CD

GitHub Actions pipeline validates:

- Lint (`ruff check`)
- Tests + coverage report
- Multi-version matrix (`3.10`, `3.11`, `3.12`)
- Package build (`python -m build`) with uploaded `dist/` artifact

Pipeline file: `.github/workflows/ci.yml`

## Project Layout

- `search.py`: backward-compatible shim for `python search.py ...`
- `web_crawling/`: package code for CLI, core logic, and web UI
- `web_crawling/templates/`: HTML templates for search and dashboard views
- `invert_index.json`: sample prebuilt index for demos
- `tests/`: regression tests for search and web behavior
- `pyproject.toml`: package metadata and console script
- `requirements*.txt`: install entry points
- `.github/workflows/ci.yml`: continuous integration pipeline
- `crawl_report.json`: generated crawl report for observability and portfolio demos

Open-source support files are included at the repo root and under `.github/`.
