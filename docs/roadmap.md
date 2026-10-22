# Roadmap toward a mature small-site search project

The v0.2 release establishes reliable data files, offline onboarding, installed-package checks and gated releases. The project remains pre-1.0. The following priorities are ordered by user impact, not treated as completed features.

## Next: responsible request policy

Implement a shared request policy for sync and async modes: robots decisions, identifiable User-Agent, bounded retries including Retry-After, a host-wide request interval and HTML/content-size limits. Enforce redirect policy before each hop. Acceptance: offline transport fixtures prove equivalent decisions, no unapproved origin requests and bounded request counts under 429/503/timeouts. Define opt-out behavior explicitly without changing profiles accidentally.

## Then: isolated application state

Replace module-level index/cache state with an explicit search service owned by each Flask app and CLI session. Acceptance: two apps with different indexes cannot leak results or cache hits; reloads invalidate only the relevant cache. Preserve the JSON index and public response structures.

## Then: measured search and crawl scale

Build a deterministic relevance corpus before changing phrase matching or ranking. Add crawl benchmarks with bounded synthetic graphs; distinguish them from existing query replay. Consider a deque and queued/attempted sets only after measuring duplicate or failed-request work. Acceptance: expected results and request counts, stable benchmark methodology, no unexplained regressions.

## Before 1.0

Review dependency security and supported Python versions on a repeatable schedule; define the public library API and deprecation policy; document resource limits and supported sitemap behavior; decide whether there is demand for PyPI distribution, a production server or persistent queues. Avoid adding these systems without a concrete use case.
