# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Local web UI entry via `python search.py web`.
- Open-source project files: LICENSE, CONTRIBUTING, SECURITY, Code of Conduct.
- GitHub issue and pull request templates.
- Module entry via `python -m web_crawling`.
- Base test suite with pytest for query behavior.
- CI workflow to run tests on push and pull request.
- JSON API endpoint at `/api/search` for machine-friendly search output.
- Packaging metadata via `pyproject.toml` and `web-crawling` script entry.
- Export endpoint at `/api/export` supporting `json` and `csv` formats.
- API integration tests for `/api/search` and `/api/export`.
- API pagination parameters (`page`, `limit`) for `/api/search` and `/api/export`.
- Search response metadata including cache hit and query time.
- API sorting parameter (`sort`) for `/api/search` and `/api/export`.
- Additional tests for sort behavior and sort validation errors.
- UI page navigation links (previous/next) based on query pagination.
- Request access log file with endpoint, status, latency, and cache flag.
- Export filenames now include timestamps.
- Export API limit guard tightened to max 100 rows per section page.

### Changed

- Search logic now exposes reusable structured query results for CLI and UI.
- Project code structure refactored from single file into package modules (`core`, `cli`, `webui`).
- Root `search.py` now acts as a backward-compatible shim.
- Web UI template moved from inline string to `web_crawling/templates/search.html`.
- API layer now uses app-factory pattern with in-memory LRU-style query cache.
