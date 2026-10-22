# Local HTTP API

Start `python -m web_crawling web --index-file demo_index.json`. The server binds to `127.0.0.1:8000` by default.

| Endpoint | Purpose |
| --- | --- |
| `/api/search?q=crawler` | Structured search results |
| `/api/export?q=crawler&format=json` | JSON or CSV download |
| `/api/insights` | Aggregated request logs |
| `/api/insights/export?format=csv` | JSON or CSV analytics report |
| `/api/crawl/report` | Crawl report; 404 if absent |
| `/api/performance/history` | Offline benchmark history |
| `/health` | Process health response |

Search requires a non-empty `q`. `page` defaults to 1. `limit` defaults to 20, with a maximum of 200 for search and 100 for export. Sorting supports `relevance`, `frequency_desc`, `score_desc`, `page_asc`, and `page_desc`. Phrase queries support `bucket=all|conjunctive|term_at_a_time|per_word`. Invalid options return JSON errors with HTTP 400.

Responses retain existing result structures and include `meta.cached` and `meta.took_ms`. Search pagination includes totals. Export `format` is `json` or `csv`. Access logs rotate by date in the working directory's `logs/` folder. Demo reports use `demo_report.json`; the web API's default crawl-report path remains `crawl_report.json`.

This API is intended for local trusted use. It has no authentication, tenant isolation or public deployment hardening.
