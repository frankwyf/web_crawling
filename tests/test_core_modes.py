import asyncio
from types import SimpleNamespace

import pytest

from web_crawling import core


class FakeRedirectSession:
    def __init__(self, responses):
        self.responses = responses

    def get(self, url, **kwargs):
        return self.responses.get(
            url,
            SimpleNamespace(
                url=url,
                text='<span class="text">fallback</span>',
                raise_for_status=lambda: None,
            ),
        )

    def close(self):
        pass


class FakeAsyncRedirectClient:
    def __init__(self, responses):
        self.responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def get(self, url, **kwargs):
        return self.responses.get(
            url,
            SimpleNamespace(
                url=url,
                text='<span class="text">fallback</span>',
                raise_for_status=lambda: None,
            ),
        )


def _run_crawl_mode(mode):
    kwargs = dict(
        base_url='https://example.com',
        politeness_interval=0,
        max_pages=3,
        include_sitemap=False,
    )
    if mode == 'sync':
        return core.crawl_website(**kwargs)
    return asyncio.run(core.crawl_website_async(**kwargs))


def test_url_normalization_and_same_origin_helpers():
    root = 'https://example.com'
    assert core._normalize_url(root, '/a/b/') == 'https://example.com/a/b'
    assert core._normalize_url(root, '#section') is None
    assert core._is_same_origin(root, 'https://example.com/x') is True
    assert core._is_same_origin(root, 'https://other.com/x') is False


@pytest.mark.parametrize(
    ('base_url', 'candidate', 'expected'),
    [
        ('https://example.com', 'https://example.com/a', True),
        ('https://example.com', 'http://example.com/a', False),
        ('https://example.com', 'https://example.com:443/a', True),
        ('https://example.com', 'https://example.com:8443/a', False),
        ('https://example.com', 'https://EXAMPLE.com/a', True),
        ('http://example.com', 'http://example.com:80/a', True),
        ('https://example.com:bad', 'https://example.com:bad/a', False),
    ],
)
def test_same_origin_helper_uses_origin_components(base_url, candidate, expected):
    assert core._is_same_origin(base_url, candidate) is expected


def test_extract_internal_links_rejects_cross_origin_links():
    html = '''
        <a href="/internal">Internal</a>
        <a href="http://example.com/insecure">HTTP downgrade</a>
        <a href="https://example.com:8443/other-port">Other port</a>
    '''

    links = core._extract_internal_links(html, 'https://example.com', 'https://example.com')

    assert links == {'https://example.com/internal'}


def test_sitemap_candidates_reject_cross_origin_seeds(monkeypatch):
    sitemap_urls = [
        'https://example.com/secure',
        'http://example.com/insecure',
        'https://example.com:8443/other-port',
    ]
    response = SimpleNamespace(
        status_code=200,
        text='<urlset></urlset>',
        url='https://example.com/sitemap.xml',
    )
    session = SimpleNamespace(get=lambda *args, **kwargs: response)
    fake_soup = SimpleNamespace(
        find_all=lambda tag: [SimpleNamespace(text=url) for url in sitemap_urls]
    )
    monkeypatch.setattr(core, 'BeautifulSoup', lambda *args: fake_soup)

    assert core._sitemap_candidates('https://example.com', session) == {'https://example.com/secure'}


def test_sitemap_candidates_reject_cross_origin_redirect(monkeypatch):
    response = SimpleNamespace(
        status_code=200,
        text='<urlset><url><loc>https://example.com/injected</loc></url></urlset>',
        url='https://offsite.example/sitemap.xml',
    )
    session = SimpleNamespace(get=lambda *args, **kwargs: response)
    fake_soup = SimpleNamespace(
        find_all=lambda tag: [SimpleNamespace(text='https://example.com/injected')]
    )
    monkeypatch.setattr(core, 'BeautifulSoup', lambda *args: fake_soup)

    assert core._sitemap_candidates('https://example.com', session) == set()


@pytest.mark.parametrize('mode', ['sync', 'async'])
def test_crawler_uses_final_same_origin_redirect_url_for_relative_links(monkeypatch, mode):
    login_url = 'https://example.com/login'
    base_url = 'https://example.com'
    redirected_url = 'https://example.com/redirected/home'
    child_url = 'https://example.com/redirected/next'

    def response(url, html):
        return SimpleNamespace(url=url, text=html, raise_for_status=lambda: None)

    responses = {
        login_url: response(login_url, '<span class="text">login</span>'),
        base_url: response(
            redirected_url,
            '<span class="text">home</span><a href="next">Next</a>',
        ),
        child_url: response(child_url, '<span class="text">child</span>'),
    }
    session = FakeRedirectSession(responses)
    monkeypatch.setattr(core, '_build_session', lambda: session)
    monkeypatch.setattr(
        core.httpx,
        'AsyncClient',
        lambda **kwargs: FakeAsyncRedirectClient(responses),
    )

    _, urls, _ = _run_crawl_mode(mode)

    assert urls == [login_url, redirected_url, child_url]


@pytest.mark.parametrize('mode', ['sync', 'async'])
def test_crawler_rejects_cross_origin_redirects(monkeypatch, mode):
    login_url = 'https://example.com/login'
    base_url = 'https://example.com'

    def response(url, html):
        return SimpleNamespace(url=url, text=html, raise_for_status=lambda: None)

    responses = {
        login_url: response(login_url, '<span class="text">login</span>'),
        base_url: response(
            'https://offsite.example/landing',
            '<span class="text">offsite</span><a href="https://example.com/reinjected">link</a>',
        ),
    }
    session = FakeRedirectSession(responses)
    monkeypatch.setattr(core, '_build_session', lambda: session)
    monkeypatch.setattr(
        core.httpx,
        'AsyncClient',
        lambda **kwargs: FakeAsyncRedirectClient(responses),
    )

    _, urls, _ = _run_crawl_mode(mode)

    assert urls == [login_url]
    assert core.LAST_CRAWL_STATS.pages_failed == 1


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

    monkeypatch.setattr(
        core,
        '_fetch_page_result',
        lambda url, politeness_interval, session=None: (
            core._FetchedPage(pages_html[url], url, url) if url in pages_html else None
        ),
    )

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

    async def fake_fetch_page_result_async(url, politeness_interval, client):
        if url not in pages_html:
            return None
        return core._FetchedPage(pages_html[url], url, url)

    monkeypatch.setattr(core, '_fetch_page_result_async', fake_fetch_page_result_async)

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
