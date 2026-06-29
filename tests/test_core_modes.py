import pytest

from web_crawling import core


def test_url_normalization_and_same_site_helpers():
    root = 'https://example.com'
    assert core._normalize_url(root, '/a/b/') == 'https://example.com/a/b'
    assert core._normalize_url(root, '#section') is None
    assert core._is_same_site(root, 'https://example.com/x') is True
    assert core._is_same_site(root, 'https://other.com/x') is False


def test_extract_internal_links_filters_external():
    html = '''
        <html><body>
            <a href="/a">A</a>
            <a href="https://example.com/b">B</a>
            <a href="https://external.com/c">C</a>
        </body></html>
    '''
    links = core._extract_internal_links(html, 'https://example.com', 'https://example.com')
    assert 'https://example.com/a' in links
    assert 'https://example.com/b' in links
    assert all('external.com' not in item for item in links)


def test_crawl_website_by_mode_sync(monkeypatch):
    pages_html = {
        'https://example.com/login': '<html><body><span class="text">login page</span><a href="/a">A</a></body></html>',
        'https://example.com': '<html><body><span class="text">home page</span><a href="/a">A</a></body></html>',
        'https://example.com/a': '<html><body><span class="text">deep page</span></body></html>',
    }

    monkeypatch.setattr(core, 'fetch_page', lambda url, politeness_interval, session=None: pages_html.get(url))

    pages, urls, links = core.crawl_website_by_mode(
        'https://example.com',
        politeness_interval=0,
        max_pages=3,
        include_sitemap=False,
        crawl_mode='sync',
    )

    assert len(pages) >= 2
    assert any(url.endswith('/a') for url in urls)
    assert len(links) == len(pages)


def test_crawl_website_by_mode_async(monkeypatch):
    if core.httpx is None:
        pytest.skip('httpx is not installed in current runtime')

    pages_html = {
        'https://example.com/login': '<html><body><span class="text">login page</span><a href="/a">A</a></body></html>',
        'https://example.com': '<html><body><span class="text">home page</span><a href="/a">A</a></body></html>',
        'https://example.com/a': '<html><body><span class="text">deep page</span></body></html>',
    }

    async def fake_fetch_page_async(url, politeness_interval, client):
        return pages_html.get(url)

    monkeypatch.setattr(core, 'fetch_page_async', fake_fetch_page_async)

    pages, urls, links = core.crawl_website_by_mode(
        'https://example.com',
        politeness_interval=0,
        max_pages=3,
        include_sitemap=False,
        crawl_mode='async',
        concurrency=2,
    )

    assert len(pages) >= 2
    assert any(url.endswith('/a') for url in urls)
    assert len(links) == len(pages)


def test_generate_crawl_report(tmp_path):
    report_file = tmp_path / 'crawl_report.json'
    pages = [['hello', 'world'], ['hello']]
    urls = ['https://example.com', 'https://example.com/a']
    links = [2, 1]
    index_data = {
        'hello': [{'Page': 0, 'URL': urls[0], 'Frequency': 1, 'Positions': [0], 'Links': 2}],
        'world': [{'Page': 0, 'URL': urls[0], 'Frequency': 1, 'Positions': [1], 'Links': 2}],
    }
    stats = {
        'base_url': 'https://example.com',
        'pages_crawled': 2,
        'pages_failed': 0,
        'duration_seconds': 0.2,
        'unique_tokens': 2,
    }

    report = core.generate_crawl_report(str(report_file), pages, urls, links, index_data, stats)

    assert report_file.exists()
    assert report['index_stats']['unique_terms'] == 2
    assert report['crawl_stats']['pages_crawled'] == 2
