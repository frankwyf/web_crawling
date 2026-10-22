# Architecture

The CLI (`cli.py`) selects offline demo, crawling, indexing, searching, benchmarking, or the local web UI. `search.py`, the module entry point and the installed console script delegate to it.

- `core.py`: same-origin discovery, sync/async fetching, HTML extraction, positional inverted index and legacy search ranking.
- `storage.py`: index validation, reads and atomic JSON replacement. It has no HTTP dependencies.
- `demo.py` and `data/`: two authored HTML pages available through package resources, including from an installed wheel.
- `webui.py`: Flask app factory, search/export APIs, request logs and dashboard views.
- `benchmark.py`: offline query replay and JSONL history.

The crawler returns parallel page-token, URL and outgoing-link arrays. The index maps terms to positional postings. Search retains the existing ranking and API result buckets. Reports describe crawl/index totals; they are separate from the persisted index.

## Current boundaries

The process still shares a module-level index and web query cache. Creating several apps with different indexes in one process is not isolated; run one dataset per process. This release does not introduce a distributed queue, database, authentication or browser rendering. Network redirects are inspected after fetching, so origin filtering does not provide SSRF protection.

The pipeline gates source tests and actual installed packages. A tag release reuses CI, validates its version against both package artifacts, then publishes those validated artifacts and checksums. Dependencies remain declared in `pyproject.toml`; requirement files are install entry points.
