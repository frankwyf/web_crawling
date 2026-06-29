import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from .core import load_index_json, search_query

DEFAULT_QUERY_SET = [
    'life',
    'love',
    'inspirational',
    'truth',
    'humor',
    'life is beautiful',
    'be yourself',
]


def _result_count(result):
    if result['type'] == 'single':
        return len(result.get('ranked_pages', []))
    if result['type'] == 'phrase':
        return (
            len(result.get('phrase_result', []))
            + len(result.get('any_order_result', []))
            + len(result.get('each_query_result', []))
        )
    return 0


def load_benchmark_history(history_file, limit=200):
    history_path = Path(history_file)
    if not history_path.exists():
        return []

    records = []
    for line in history_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return records[-limit:]


def run_benchmark_suite(
    index_path,
    history_file='logs/perf_history.jsonl',
    runs=3,
    queries=None,
    fail_on_regression=False,
    regression_tolerance=0.25,
):
    if runs < 1:
        raise ValueError('runs must be >= 1')

    query_set = [q.strip() for q in (queries or DEFAULT_QUERY_SET) if q.strip()]
    if not query_set:
        raise ValueError('queries must contain at least one non-empty query')

    index_data = load_index_json(index_path)

    latencies_ms = []
    result_sizes = []
    started = time.perf_counter()
    for _ in range(runs):
        for query in query_set:
            q_started = time.perf_counter()
            result = search_query(query, index_data)
            took_ms = (time.perf_counter() - q_started) * 1000
            latencies_ms.append(round(took_ms, 3))
            result_sizes.append(_result_count(result))

    total_duration_ms = round((time.perf_counter() - started) * 1000, 3)
    total_ops = len(latencies_ms)
    avg_ms = round(sum(latencies_ms) / total_ops, 3)
    p95_ms = round(statistics.quantiles(latencies_ms, n=100)[94], 3) if total_ops > 1 else avg_ms
    max_ms = max(latencies_ms)
    min_ms = min(latencies_ms)
    qps = round((total_ops * 1000) / total_duration_ms, 3) if total_duration_ms > 0 else 0.0
    non_empty_rate = round((sum(1 for x in result_sizes if x > 0) / len(result_sizes)) * 100, 1)
    avg_result_size = round(sum(result_sizes) / len(result_sizes), 3)

    history_path = Path(history_file)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history = load_benchmark_history(history_file)
    previous = history[-1] if history else None

    regression_detected = False
    regression_details = None
    if previous:
        prev_avg = previous.get('metrics', {}).get('avg_ms')
        if isinstance(prev_avg, (int, float)) and prev_avg > 0:
            threshold = prev_avg * (1 + regression_tolerance)
            if avg_ms > threshold:
                regression_detected = True
                regression_details = {
                    'previous_avg_ms': prev_avg,
                    'current_avg_ms': avg_ms,
                    'threshold_ms': round(threshold, 3),
                    'tolerance': regression_tolerance,
                }

    report = {
        'version': 1,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'index_path': str(index_path),
        'query_set': query_set,
        'runs': runs,
        'metrics': {
            'operations': total_ops,
            'duration_ms': total_duration_ms,
            'avg_ms': avg_ms,
            'p95_ms': p95_ms,
            'min_ms': min_ms,
            'max_ms': max_ms,
            'qps': qps,
            'non_empty_rate': non_empty_rate,
            'avg_result_size': avg_result_size,
        },
        'regression_detected': regression_detected,
        'regression_details': regression_details,
    }

    with history_path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(report, ensure_ascii=False) + '\n')

    if fail_on_regression and regression_detected:
        details = regression_details or {}
        raise RuntimeError(
            'Performance regression detected: '
            f"previous_avg_ms={details.get('previous_avg_ms')} current_avg_ms={details.get('current_avg_ms')}"
        )

    return report
