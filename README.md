# Web Crawler and Search Tool

Lightweight Python crawler + inverted index search project with both CLI and Web UI entry points.

## Features

- Crawl `https://quotes.toscrape.com`
- Build and load an inverted index from JSON
- Search by single word or phrase
- Provide ranked results based on occurrence and simple link-based score
- Support both terminal workflow and browser workflow

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 1. CLI Mode

```powershell
.\.venv\Scripts\python .\search.py load
.\.venv\Scripts\python .\search.py print quotes
.\.venv\Scripts\python .\search.py find life is beautiful
```

Standard module entry is also available:

```powershell
.\.venv\Scripts\python -m web_crawling load
```

### 2. Interactive Mode

```powershell
.\.venv\Scripts\python .\search.py interactive
```

Commands: `build`, `load`, `print <word>`, `find <phrase>`, `exit`

### 3. Web UI Mode

```powershell
.\.venv\Scripts\python .\search.py web
```

Then open `http://127.0.0.1:8000`.

Optional:

```powershell
.\.venv\Scripts\python .\search.py web --host 0.0.0.0 --port 8080
```

### 4. JSON API Mode (via web server)

After starting web mode, query JSON API directly:

```powershell
curl "http://127.0.0.1:8000/api/search?q=life%20is%20beautiful"
```

With pagination:

```powershell
curl "http://127.0.0.1:8000/api/search?q=life%20is%20beautiful&page=1&limit=20"
```

With sorting:

```powershell
curl "http://127.0.0.1:8000/api/search?q=life%20is%20beautiful&sort=score_desc"
```

Notes:

- `page` defaults to `1`
- `limit` defaults to `20` and max is `200`
- `sort` supports `relevance`, `frequency_desc`, `score_desc`, `page_asc`, `page_desc`
- response meta includes `cached` and `took_ms`
- API access logs are written to `logs/access.log`

Health check:

```powershell
curl "http://127.0.0.1:8000/health"
```

Export result files:

```powershell
curl "http://127.0.0.1:8000/api/export?q=life%20is%20beautiful&format=json" -o search_results.json
curl "http://127.0.0.1:8000/api/export?q=life%20is%20beautiful&format=csv" -o search_results.csv
```

Export also accepts `page` and `limit`.
For export, `limit` max is `100` to prevent overly large downloads.

## Rebuild Index

```powershell
.\.venv\Scripts\python .\search.py build --politeness-interval 1
```

The repository includes a prebuilt `invert_index.json` so you can run demos without recrawling.

## Testing

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q
```

## Repository Layout

- `search.py`: backward-compatible shim entry (`python search.py ...`)
- `web_crawling/core.py`: crawling, indexing, ranking, and query logic
- `web_crawling/cli.py`: CLI parsing and command routing
- `web_crawling/webui.py`: Flask UI and JSON API endpoints
- `web_crawling/templates/search.html`: UI template file
- `web_crawling/__main__.py`: module entry (`python -m web_crawling ...`)
- `invert_index.json`: sample prebuilt inverted index
- `pyproject.toml`: package metadata and script entry
- `requirements.txt`: Python dependencies
- `CHANGELOG.md`: notable changes
- `CONTRIBUTING.md`: contribution guide
- `CODE_OF_CONDUCT.md`: community behavior standards
- `SECURITY.md`: vulnerability reporting process
- `LICENSE`: open source license
- `requirements-dev.txt`: developer/test dependencies
- `tests/`: basic regression tests
- `.github/workflows/ci.yml`: GitHub Actions CI

## Open Source Files

This project includes standard community files to make collaboration easier:

- License: MIT (`LICENSE`)
- Contribution guide (`CONTRIBUTING.md`)
- Code of conduct (`CODE_OF_CONDUCT.md`)
- Security policy (`SECURITY.md`)
- Issue templates (`.github/ISSUE_TEMPLATE/`)
- Pull request template (`.github/pull_request_template.md`)

## Contributing

Contributions are welcome. Please read `CONTRIBUTING.md` before opening pull requests.
