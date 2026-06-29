# Web Crawler and Search Tool

Lightweight Python crawler + inverted-index search project with CLI, web UI, JSON API, and analytics dashboard.

## What Is New In This Upgrade

This project has been upgraded from a basic crawler/search demo into a portfolio-grade Python crawling system:

- Resilient crawling engine with connection pooling and retry backoff.
- Internal-link traversal with optional sitemap seeding.
- Configurable crawl scale using `--max-pages`.
- Machine-readable crawl report export (`crawl_report.json`).
- Dashboard-level crawl quality visibility (`/api/crawl/report` + dashboard panel).
- Expanded quality pipeline: lint, tests, coverage gate, package build artifacts.
- Multi-version CI validation across Python 3.10 / 3.11 / 3.12.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

For development:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

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
```

Web UI:

```powershell
.\.venv\Scripts\python .\search.py web
```

Open `http://127.0.0.1:8000/` for search and `http://127.0.0.1:8000/dashboard` for analytics.

## Crawling Strategy

The crawler focuses on reliability and explainability:

- Uses a reusable HTTP session for better performance.
- Applies automatic retry policy to transient failures (`429/5xx`).
- Enforces request timeout and politeness interval.
- Follows only internal links (same host) to prevent scope drift.
- Optionally seeds with `/sitemap.xml` URLs when available.

After each build, a structured crawl report is generated to summarize quality and scale.

## API

- Search: `/api/search?q=life%20is%20beautiful`
- Export results: `/api/export?q=life%20is%20beautiful&format=json|csv`
- Dashboard insights: `/api/insights`
- Export dashboard report: `/api/insights/export?format=json|csv`
- Crawl report: `/api/crawl/report`
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

This provides a visual checkpoint for crawl quality and search-system health.

## Testing

```powershell
.\.venv\Scripts\python -m pytest -q
```

Lint and coverage checks:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m coverage run -m pytest
.\.venv\Scripts\python -m coverage report -m
```

Coverage threshold is enforced in `pyproject.toml` and can be tightened over time as test depth increases.

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
