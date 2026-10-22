"""A small authored corpus that works from an installed wheel without network access."""

from importlib.resources import files

from .core import build_index, extract_text, generate_crawl_report
from .storage import validate_output_paths


def run_demo(index_path, report_path):
    validate_output_paths(index_path, report_path)
    names = ('overview', 'reliability')
    extracted = [extract_text(files('web_crawling').joinpath(f'data/{name}.html').read_text(encoding='utf-8')) for name in names]
    pages = [words for words, _ in extracted]
    links = [count for _, count in extracted]
    urls = [f'https://example.invalid/demo/{name}' for name in names]
    built = build_index(pages, index_path, urls, links)
    stats = {
        'source': 'offline-demo',
        'base_url': 'https://example.invalid/demo/',
        'pages_crawled': len(pages),
        'pages_failed': 0,
        'total_tokens': sum(map(len, pages)),
        'unique_tokens': len(built),
        'duration_seconds': 0,
    }
    generate_crawl_report(report_path, pages, urls, links, built, stats)
    return built
