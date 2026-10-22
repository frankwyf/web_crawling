import json
import sys
from types import SimpleNamespace

import pytest

from web_crawling import cli, core


def test_cli_missing_index_exits_unsuccessfully(monkeypatch, tmp_path, capsys):
    core.index.clear()
    monkeypatch.setattr(sys, 'argv', ['web-crawling', 'load', '--index-file', str(tmp_path / 'missing.json')])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    assert 'Error:' in capsys.readouterr().err


def test_cli_no_command_starts_interactive_with_defaults(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['web-crawling'])
    calls = []
    monkeypatch.setattr(cli, 'interactive_loop', lambda *args, **kwargs: calls.append((args, kwargs)))

    cli.main()

    assert len(calls) == 1
    assert calls[0][1]['profile'] == 'generic'


def test_offline_demo_builds_searchable_index_and_report(monkeypatch, tmp_path):
    target = tmp_path / 'output' / 'demo.json'
    report = tmp_path / 'output' / 'report.json'
    monkeypatch.setattr(sys, 'argv', [
        'web-crawling', 'demo', '--index-file', str(target), '--report-file', str(report),
    ])

    cli.main()

    loaded = core.load_index_json(target)
    result = core.search_query('crawler', loaded)
    assert result['ranked_pages']
    assert all('example.invalid' in row[1] for row in result['ranked_pages'])
    assert json.loads(report.read_text())['crawl_stats']['source'] == 'offline-demo'


@pytest.mark.parametrize('namespace', ['', ' xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'])
def test_real_sitemap_xml_works_without_optional_parser(namespace):
    response = SimpleNamespace(
        status_code=200, url='https://example.com/sitemap.xml',
        text=f'<urlset{namespace}><url><loc>https://example.com/items?page=2</loc></url></urlset>',
    )
    session = SimpleNamespace(get=lambda *args, **kwargs: response)

    assert core._sitemap_candidates('https://example.com', session) == {'https://example.com/items?page=2'}


@pytest.mark.parametrize('xml', ['<broken', '<sitemapindex><sitemap><loc>https://example.com/sub.xml</loc></sitemap></sitemapindex>'])
def test_malformed_or_nested_sitemap_is_not_indexed_as_html(xml):
    response = SimpleNamespace(status_code=200, url='https://example.com/sitemap.xml', text=xml)
    session = SimpleNamespace(get=lambda *args, **kwargs: response)

    assert core._sitemap_candidates('https://example.com', session) == set()


def test_cli_reports_invalid_index_without_traceback(monkeypatch, tmp_path, capsys):
    target = tmp_path / 'bad.json'
    target.write_text('[]', encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['web-crawling', 'load', '--index-file', str(target)])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    assert 'Invalid index' in capsys.readouterr().err


def test_cli_benchmark_regression_returns_failure(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['web-crawling', 'benchmark', '--fail-on-regression'])

    def fail(**kwargs):
        raise RuntimeError('Performance regression detected')

    monkeypatch.setattr(cli, 'run_benchmark_suite', fail)
    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    assert 'Performance regression' in capsys.readouterr().err


@pytest.mark.parametrize('command', ['demo', 'build'])
def test_cli_rejects_identical_index_and_report_paths_before_writing(monkeypatch, tmp_path, command):
    target = tmp_path / 'output.json'
    target.write_text('previous', encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', [
        'web-crawling', command, '--index-file', str(target), '--report-file', str(target),
    ])
    monkeypatch.setattr(cli, 'crawl_website_by_mode', lambda *args, **kwargs: pytest.fail('Crawl must not start'))

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    assert target.read_text(encoding='utf-8') == 'previous'
