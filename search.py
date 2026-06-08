"""Backward-compatible entry point.

This shim keeps `python search.py ...` working while the implementation
lives inside the web_crawling package.
"""

from web_crawling.cli import main
from web_crawling.core import search_query


if __name__ == '__main__':
    main()
