# Index format and recovery

The on-disk format remains a JSON object mapping non-empty terms to posting lists:

```json
{
  "hello": [{"Page": 0, "URL": "https://example.org", "Frequency": 2, "Positions": [0, 3], "Links": 1}]
}
```

`Page` and `Links` are non-negative integers; `Frequency` is a positive integer. Booleans are not accepted as integers. `Positions` contains non-negative, strictly increasing integers and its length equals `Frequency`. A term cannot repeat a page ID. `URL` is a non-empty string; legacy non-HTTP document identifiers remain valid. Additional posting fields are preserved. Empty indexes and empty posting lists can be loaded.

Validation completes before the shared in-memory index changes. Invalid JSON, invalid UTF-8 and structurally invalid indexes fail with a clear error. `load` and file-backed entry points read the explicitly requested file even if another index was previously loaded.

Building zero pages fails and preserves the previous index. The CLI rejects identical index/report paths before crawling or writing. Output directories are created as needed. Index/report writes use a sibling temporary file, flush and fsync it, close it, then call `os.replace`. Ordinary write or replace failures leave the old destination intact and clean up the temporary file. This is a single-file replacement guarantee, not an index/report transaction, concurrent-writer lock, or guarantee against every filesystem/power-loss failure. A forced process kill can leave an unused sibling `.tmp` file. Replacing a symbolic-link destination replaces the link itself.

If an old file fails validation, keep a backup and rebuild it from an authorized source. Do not manually drop required fields to bypass validation. Index validation does not cap input size or make untrusted data safe to serve publicly.
