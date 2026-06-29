import json
import time

import pytest

from web_crawling import benchmark


def _write_index(path):
    payload = {
        'hello': [{'Page': 0, 'URL': 'u0', 'Frequency': 2, 'Positions': [0, 2], 'Links': 1}],
        'world': [{'Page': 0, 'URL': 'u0', 'Frequency': 1, 'Positions': [1], 'Links': 1}],
    }
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_run_benchmark_suite_writes_history(tmp_path):
    index_path = tmp_path / 'index.json'
    history_path = tmp_path / 'perf_history.jsonl'
    _write_index(index_path)

    report = benchmark.run_benchmark_suite(
        index_path=str(index_path),
        history_file=str(history_path),
        runs=2,
        queries=['hello', 'hello world'],
    )

    assert report['metrics']['operations'] == 4
    assert report['metrics']['avg_ms'] >= 0
    assert history_path.exists()
    history = benchmark.load_benchmark_history(str(history_path))
    assert len(history) == 1


def test_benchmark_regression_detection_can_fail(tmp_path, monkeypatch):
    index_path = tmp_path / 'index.json'
    history_path = tmp_path / 'perf_history.jsonl'
    _write_index(index_path)

    benchmark.run_benchmark_suite(index_path=str(index_path), history_file=str(history_path), runs=1, queries=['hello'])

    original_search = benchmark.search_query

    def delayed_search(query, index_data):
        time.sleep(0.01)
        return original_search(query, index_data)

    monkeypatch.setattr(benchmark, 'search_query', delayed_search)

    with pytest.raises(RuntimeError):
        benchmark.run_benchmark_suite(
            index_path=str(index_path),
            history_file=str(history_path),
            runs=1,
            queries=['hello'],
            fail_on_regression=True,
            regression_tolerance=0.01,
        )
