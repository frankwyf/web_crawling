# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.2.0] - 2026-10-22

### Added

- Offline `demo` command with a bundled HTML corpus and `--version` output.
- Compatible index schema validation and atomic index/report file replacement.
- Regression coverage for write interruption, malformed data, command failures and actual sitemap XML.
- External-storage shell setup, index/API contracts, architecture, release guide and maturity roadmap.
- macOS and Windows CI, installed-wheel smoke checks, reusable release gates and artifact checksums.

### Fixed

- Failed or empty crawls no longer replace an existing index with an empty file.
- Explicit index paths reload the requested data rather than silently using an unrelated loaded index.
- CLI operational failures return status 1; running without arguments starts the interactive shell.
- Flat sitemap XML no longer requires an undeclared optional parser.
- Content query parameters distinguish paginated pages while common tracking parameters deduplicate.

### Compatibility

- Existing JSON index fields and search responses are retained; malformed historical indexes now fail validation.
- Package version metadata is derived from `web_crawling.__version__`.
- Each index/report is replaced separately; the pair is not a single transaction.

### Security

- Upgrade Requests to 2.34.2 and Flask to 3.1.3 to address known upstream advisories.
- Gate package/release jobs on a strict pip-audit dependency scan and retain its JSON result.

## [0.1.0]

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
- Bucket filtering parameter (`bucket`) for scoped phrase-result output.
- Access logs now rotate daily (`access_YYYYMMDD.log`).
- Analytics dashboard at `/dashboard` plus `/api/insights` for request/log analysis.
- Exportable analytics reports at `/api/insights/export` in JSON and CSV formats.
- Dependency entry files now delegate to `pyproject.toml`, and setuptools package discovery is restricted to the application package.
- Unified the search and dashboard visuals through a shared stylesheet, and added richer dashboard KPIs and traffic trend views.

### Changed

- Search logic now exposes reusable structured query results for CLI and UI.
- Project code structure refactored from single file into package modules (`core`, `cli`, `webui`).
- Root `search.py` now acts as a backward-compatible shim.
- Web UI template moved from inline string to `web_crawling/templates/search.html`.
- API layer now uses app-factory pattern with in-memory LRU-style query cache.
