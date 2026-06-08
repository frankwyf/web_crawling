# Web Crawler and Search Tool

Lightweight Python crawler + inverted-index search project with CLI, web UI, JSON API, and analytics dashboard.

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
```

Web UI:

```powershell
.\.venv\Scripts\python .\search.py web
```

Open `http://127.0.0.1:8000/` for search and `http://127.0.0.1:8000/dashboard` for analytics.

## API

- Search: `/api/search?q=life%20is%20beautiful`
- Export results: `/api/export?q=life%20is%20beautiful&format=json|csv`
- Dashboard insights: `/api/insights`
- Export dashboard report: `/api/insights/export?format=json|csv`
- Health check: `/health`

Query options:

- `page` defaults to `1`
- `limit` defaults to `20` and max is `200` for search, `100` for export
- `sort` supports `relevance`, `frequency_desc`, `score_desc`, `page_asc`, `page_desc`
- `bucket` supports `all`, `conjunctive`, `term_at_a_time`, `per_word`

API responses include `cached` and `took_ms`, and access logs rotate daily under `logs/access_YYYYMMDD.log`.

## Testing

```powershell
.\.venv\Scripts\python -m pytest -q
```

## Project Layout

- `search.py`: backward-compatible shim for `python search.py ...`
- `web_crawling/`: package code for CLI, core logic, and web UI
- `web_crawling/templates/`: HTML templates for search and dashboard views
- `invert_index.json`: sample prebuilt index for demos
- `tests/`: regression tests for search and web behavior
- `pyproject.toml`: package metadata and console script
- `requirements*.txt`: install entry points

Open-source support files are included at the repo root and under `.github/`.
