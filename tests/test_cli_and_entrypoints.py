import argparse
import runpy

from web_crawling import cli


def test_handle_command_build_calls_pipeline(monkeypatch, tmp_path):
    index_path = tmp_path / 'index.json'
    called = {}

    monkeypatch.setattr(
        cli,
        'crawl_website_by_mode',
        lambda *args, **kwargs: ([['hello', 'world']], ['https://example.com'], [1]),
    )
    monkeypatch.setattr(
        cli,
        'build_index',
        lambda pages, path, urls, links: {'hello': [{'Page': 0, 'URL': urls[0], 'Frequency': 1, 'Positions': [0], 'Links': 1}]},
    )
    monkeypatch.setattr(
        cli,
        'generate_crawl_report',
        lambda report_file, pages, urls, links, index_data, stats: called.update({'report_file': report_file}),
    )
    monkeypatch.setattr(
        cli,
        'get_last_crawl_stats',
        lambda: {
            'base_url': 'https://example.com',
            'pages_crawled': 1,
            'pages_failed': 0,
            'unique_tokens': 2,
            'duration_seconds': 0.1,
        },
    )

    cli.handle_command(
        'build',
        str(index_path),
        'https://example.com',
        0,
        max_pages=5,
        report_file=str(tmp_path / 'crawl_report.json'),
        crawl_mode='async',
        async_concurrency=3,
    )

    assert called['report_file'].endswith('crawl_report.json')


def test_handle_command_load_calls_ensure(monkeypatch):
    hit = {'value': False}

    def fake_ensure(path):
        hit['value'] = True

    monkeypatch.setattr(cli, 'ensure_index_loaded', fake_ensure)
    cli.handle_command('load', 'index.json', 'https://example.com', 0)

    assert hit['value'] is True


def test_cli_main_benchmark_branch(monkeypatch):
    calls = {'summary': None}

    monkeypatch.setattr(
        cli,
        'parse_args',
        lambda: argparse.Namespace(
            command='benchmark',
            index_file='invert_index.json',
            history_file='logs/perf_history.jsonl',
            runs=1,
            query=[],
            fail_on_regression=False,
        ),
    )
    monkeypatch.setattr(
        cli,
        'run_benchmark_suite',
        lambda **kwargs: {
            'metrics': {'operations': 1, 'avg_ms': 1.0, 'p95_ms': 1.0, 'qps': 10, 'non_empty_rate': 100.0},
            'regression_detected': False,
        },
    )
    monkeypatch.setattr(cli, '_print_benchmark_summary', lambda payload: calls.update({'summary': payload}))

    cli.main()

    assert calls['summary']['metrics']['operations'] == 1


def test_entrypoints_delegate_to_cli(monkeypatch):
    called = {'count': 0}

    def fake_main():
        called['count'] += 1

    import web_crawling
    import web_crawling.cli as cli_module

    monkeypatch.setattr(cli_module, 'main', fake_main)

    web_crawling.main()
    runpy.run_module('web_crawling.__main__', run_name='__main__')
    runpy.run_module('search', run_name='__main__')

    assert called['count'] == 3
