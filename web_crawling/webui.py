import csv
import io
import json
import math
import re
import shlex
import time
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, Response, jsonify, render_template, request

from .benchmark import load_benchmark_history
from .core import BLUE_COLOR, ensure_index_loaded, index, search_query

_CACHE_MAX_SIZE = 128
_SEARCH_CACHE = OrderedDict()
_SUPPORTED_SORTS = {'relevance', 'frequency_desc', 'score_desc', 'page_asc', 'page_desc'}
_SUPPORTED_BUCKETS = {'all', 'conjunctive', 'term_at_a_time', 'per_word'}
_EXPORT_LIMIT_MAX = 100
_DEFAULT_LIMIT = 20
_LOG_LINE_PREFIX = re.compile(r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<rest>.*)$')
_DEFAULT_CRAWL_REPORT_PATH = 'crawl_report.json'
_DEFAULT_PERF_HISTORY_PATH = 'logs/perf_history.jsonl'


def _normalize_query(query):
    return ' '.join(query.strip().lower().split())


def _cached_search(query):
    cache_key = _normalize_query(query)
    if cache_key in _SEARCH_CACHE:
        _SEARCH_CACHE.move_to_end(cache_key)
        return _SEARCH_CACHE[cache_key], True

    result = search_query(query, index)
    _SEARCH_CACHE[cache_key] = result
    if len(_SEARCH_CACHE) > _CACHE_MAX_SIZE:
        _SEARCH_CACHE.popitem(last=False)
    return result, False


def _parse_positive_int(raw_value, default_value, field_name, max_value):
    if raw_value is None or raw_value == '':
        return default_value, None
    try:
        value = int(raw_value)
    except ValueError:
        return None, f'{field_name} must be an integer'
    if value < 1:
        return None, f'{field_name} must be >= 1'
    if value > max_value:
        return None, f'{field_name} must be <= {max_value}'
    return value, None


def _parse_sort(raw_value):
    if raw_value is None or raw_value == '':
        return 'relevance', None
    sort_mode = raw_value.strip().lower()
    if sort_mode not in _SUPPORTED_SORTS:
        return None, f"sort must be one of {', '.join(sorted(_SUPPORTED_SORTS))}"
    return sort_mode, None


def _parse_bucket(raw_value):
    if raw_value is None or raw_value == '':
        return 'all', None
    bucket = raw_value.strip().lower()
    if bucket not in _SUPPORTED_BUCKETS:
        return None, f"bucket must be one of {', '.join(sorted(_SUPPORTED_BUCKETS))}"
    return bucket, None


def _sort_items(items, sort_mode):
    if sort_mode == 'relevance' or len(items) < 2:
        return items
    if sort_mode == 'frequency_desc':
        return sorted(items, key=lambda x: (-x.get('frequency', 0), x.get('page', 0)))
    if sort_mode == 'score_desc':
        return sorted(items, key=lambda x: (-x.get('score', 0), x.get('page', 0)))
    if sort_mode == 'page_desc':
        return sorted(items, key=lambda x: -x.get('page', 0))
    return sorted(items, key=lambda x: x.get('page', 0))


def _paginate(items, page, limit):
    total = len(items)
    total_pages = math.ceil(total / limit) if total > 0 else 0
    start = (page - 1) * limit
    end = start + limit
    paged = items[start:end] if start < total else []
    return paged, {
        'page': page,
        'limit': limit,
        'total': total,
        'total_pages': total_pages,
        'returned': len(paged),
    }


def _to_json_payload(query, result, page, limit, took_ms, cached, sort_mode, bucket):
    payload = {
        'query': query,
        'type': result['type'],
        'meta': {
            'cached': cached,
            'took_ms': took_ms,
            'page': page,
            'limit': limit,
            'sort': sort_mode,
            'bucket': bucket,
        },
    }

    if result['type'] == 'single':
        all_results = [
            {
                'page': page_id,
                'url': url,
                'frequency': frequency,
                'score': score,
            }
            for page_id, url, frequency, score in result['ranked_pages']
        ]
        all_results = _sort_items(all_results, sort_mode)
        page_items, page_meta = _paginate(all_results, page, limit)
        payload['results'] = page_items
        payload['pagination'] = page_meta
    elif result['type'] == 'phrase':
        conjunctive = [
            {
                'page': page_id,
                'url': url,
                'frequency': frequency,
                'score': score,
            }
            for page_id, url, frequency, _positions, score in result['phrase_result']
        ]
        term_at_a_time = [
            {
                'page': page_id,
                'url': url,
                'frequency': frequency,
                'score': score,
            }
            for page_id, url, frequency, score in result['any_order_result']
        ]
        per_word = [
            {
                'page': page_id,
                'url': url,
                'frequency': frequency,
                'score': score,
                'word': word,
            }
            for page_id, url, frequency, score, word in result['each_query_result']
        ]

        conjunctive = _sort_items(conjunctive, sort_mode)
        term_at_a_time = _sort_items(term_at_a_time, sort_mode)
        per_word = _sort_items(per_word, sort_mode)

        if bucket in {'all', 'conjunctive'}:
            payload['conjunctive'], payload['conjunctive_meta'] = _paginate(conjunctive, page, limit)
        if bucket in {'all', 'term_at_a_time'}:
            payload['term_at_a_time'], payload['term_at_a_time_meta'] = _paginate(term_at_a_time, page, limit)
        if bucket in {'all', 'per_word'}:
            payload['per_word'], payload['per_word_meta'] = _paginate(per_word, page, limit)
    else:
        payload['results'] = []
        payload['pagination'] = {
            'page': page,
            'limit': limit,
            'total': 0,
            'total_pages': 0,
            'returned': 0,
        }
    return payload


def _result_sections_from_payload(query, payload):
    sections = []
    if payload['type'] == 'single':
        if payload.get('results'):
            sections.append({'title': f"Word matches for '{query}'", 'items': payload['results']})
    elif payload['type'] == 'phrase':
        mapping = [
            ('Conjunctive phrase matches', payload.get('conjunctive', [])),
            ('Term-at-a-time matches', payload.get('term_at_a_time', [])),
            ('Per-word fallback matches', payload.get('per_word', [])),
        ]
        for title, records in mapping:
            if records:
                sections.append({'title': title, 'items': records})
    return sections


def _to_csv_text(payload):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['bucket', 'page', 'url', 'frequency', 'score', 'word'])
    writer.writeheader()

    if payload['type'] == 'single':
        for item in payload.get('results', []):
            writer.writerow({'bucket': 'results', **item, 'word': ''})
    elif payload['type'] == 'phrase':
        for item in payload.get('conjunctive', []):
            writer.writerow({'bucket': 'conjunctive', **item, 'word': ''})
        for item in payload.get('term_at_a_time', []):
            writer.writerow({'bucket': 'term_at_a_time', **item, 'word': ''})
        for item in payload.get('per_word', []):
            writer.writerow({'bucket': 'per_word', **item})

    return output.getvalue()


def _dashboard_to_csv_text(dashboard):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['section', 'label', 'value'])
    writer.writeheader()

    for key, value in dashboard.get('index', {}).items():
        writer.writerow({'section': 'index', 'label': key, 'value': value})

    for key, value in dashboard.get('requests', {}).items():
        writer.writerow({'section': 'requests', 'label': key, 'value': value})

    for section_name in ['top_queries', 'top_endpoints', 'top_status_codes', 'top_sorts', 'top_buckets', 'daily_volume']:
        for item in dashboard.get(section_name, []):
            writer.writerow({'section': section_name, 'label': item.get('label', ''), 'value': item.get('count', '')})

    for item in dashboard.get('recent_requests', []):
        label = f"{item.get('timestamp', '')} {item.get('endpoint', '')}".strip()
        writer.writerow({'section': 'recent_requests', 'label': label, 'value': item.get('query', '')})

    writer.writerow({'section': 'generated_at', 'label': 'generated_at', 'value': dashboard.get('generated_at', '')})
    writer.writerow({'section': 'generated_at', 'label': 'log_files', 'value': len(dashboard.get('log_files', []))})
    return output.getvalue()


def _pagination_for_ui(payload):
    if payload['type'] == 'single':
        return payload.get('pagination', {'page': 1, 'total_pages': 0, 'total': 0})

    bucket = payload['meta'].get('bucket', 'all')
    if bucket == 'conjunctive':
        return payload.get('conjunctive_meta', {'page': 1, 'total_pages': 0, 'total': 0})
    if bucket == 'term_at_a_time':
        return payload.get('term_at_a_time_meta', {'page': 1, 'total_pages': 0, 'total': 0})
    if bucket == 'per_word':
        return payload.get('per_word_meta', {'page': 1, 'total_pages': 0, 'total': 0})

    metas = [
        payload.get('conjunctive_meta', {'total_pages': 0, 'total': 0}),
        payload.get('term_at_a_time_meta', {'total_pages': 0, 'total': 0}),
        payload.get('per_word_meta', {'total_pages': 0, 'total': 0}),
    ]
    page = payload['meta']['page']
    total_pages = max(item.get('total_pages', 0) for item in metas)
    total = max(item.get('total', 0) for item in metas)
    return {'page': page, 'total_pages': total_pages, 'total': total}


def _build_page_url(query, page, limit, sort_mode, bucket):
    params = {'q': query, 'page': page, 'limit': limit, 'sort': sort_mode, 'bucket': bucket}
    return '/?' + urlencode(params)


def _resolve_log_path(log_path):
    if not log_path:
        return None
    day_stamp = datetime.now().strftime('%Y%m%d')
    if '{date}' in log_path:
        return log_path.replace('{date}', day_stamp)
    path_obj = Path(log_path)
    if path_obj.name.endswith('.log'):
        stem = path_obj.stem
        return str(path_obj.with_name(f'{stem}_{day_stamp}.log'))
    return str(path_obj)


def _dashboard_log_files(log_path):
    if not log_path:
        return []

    path_obj = Path(log_path)
    parent = path_obj.parent if str(path_obj.parent) != '.' else Path('.')
    name = path_obj.name

    if '{date}' in name:
        pattern = name.replace('{date}', '*')
    elif re.search(r'_\d{8}\.log$', name):
        pattern = re.sub(r'_\d{8}(?=\.log$)', '_*', name)
    elif name.endswith('.log'):
        pattern = f'{path_obj.stem}*.log'
    else:
        pattern = f'{name}*'

    return sorted(parent.glob(pattern))


def _parse_access_log_line(line):
    match = _LOG_LINE_PREFIX.match(line.strip())
    if not match:
        return None

    record = {'timestamp': match.group('timestamp')}
    try:
        for token in shlex.split(match.group('rest')):
            if '=' not in token:
                continue
            key, value = token.split('=', 1)
            record[key] = value
    except ValueError:
        return None
    return record


def _load_access_log_records(log_path):
    records = []
    for file_path in _dashboard_log_files(log_path):
        if not file_path.exists():
            continue
        for line in file_path.read_text(encoding='utf-8').splitlines():
            record = _parse_access_log_line(line)
            if record:
                records.append(record)
    return records


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _top_counts(counter, limit=5):
    return [{'label': label, 'count': count} for label, count in counter.most_common(limit)]


def _percentile(values, percentile):
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    return lower_value + (upper_value - lower_value) * (rank - lower)


def _build_dashboard_payload(log_path):
    records = _load_access_log_records(log_path)
    total_requests = len(records)
    search_requests = [record for record in records if record.get('endpoint') == '/api/search']
    export_requests = [record for record in records if record.get('endpoint') == '/api/export']
    insight_requests = [record for record in records if record.get('endpoint') == '/api/insights']
    dashboard_requests = [record for record in records if record.get('endpoint') == '/dashboard']
    cache_hits = sum(1 for record in records if record.get('cached', '').lower() == 'true')
    latencies = [_safe_float(record.get('took_ms')) for record in records]
    avg_latency = round(sum(latencies) / len(latencies), 3) if latencies else 0.0
    p95_latency = round(_percentile(latencies, 0.95), 3) if latencies else 0.0
    success_total = sum(1 for record in records if 200 <= _safe_int(record.get('status')) < 400)
    error_total = total_requests - success_total

    query_counter = Counter(record.get('query', '') for record in search_requests if record.get('query'))
    endpoint_counter = Counter(record.get('endpoint', 'unknown') for record in records)
    status_counter = Counter(record.get('status', 'unknown') for record in records)
    sort_counter = Counter(record.get('sort', 'relevance') for record in search_requests if record.get('sort'))
    bucket_counter = Counter(record.get('bucket', 'all') for record in search_requests if record.get('bucket'))
    daily_counter = Counter(record.get('timestamp', '')[:10] for record in records if record.get('timestamp'))
    hourly_counter = Counter(record.get('timestamp', '')[11:13] for record in records if record.get('timestamp'))
    daily_series = [
        {'label': date, 'count': count}
        for date, count in sorted(daily_counter.items())
    ]
    hourly_series = [
        {'label': f'{hour}:00', 'count': hourly_counter.get(f'{hour:02d}', 0)}
        for hour in range(24)
    ]
    total_search_queries = sum(query_counter.values())
    top_query_share = round((query_counter.most_common(1)[0][1] / total_search_queries) * 100, 1) if total_search_queries else 0.0

    recent_requests = [
        {
            'timestamp': record.get('timestamp', ''),
            'endpoint': record.get('endpoint', ''),
            'status': _safe_int(record.get('status')),
            'latency': _safe_float(record.get('took_ms')),
            'cached': record.get('cached', 'False'),
            'query': record.get('query', ''),
            'sort': record.get('sort', ''),
            'bucket': record.get('bucket', ''),
        }
        for record in records[-10:]
    ][::-1]

    unique_pages = set()
    for entries in index.values():
        for entry in entries:
            unique_pages.add(entry.get('URL'))

    return {
        'index': {
            'unique_terms': len(index),
            'unique_pages': len(unique_pages),
        },
        'requests': {
            'total': total_requests,
            'search_total': len(search_requests),
            'export_total': len(export_requests),
            'insight_total': len(insight_requests),
            'dashboard_total': len(dashboard_requests),
            'cache_hits': cache_hits,
            'cache_hit_rate': round((cache_hits / total_requests) * 100, 1) if total_requests else 0.0,
            'avg_latency_ms': avg_latency,
            'p95_latency_ms': p95_latency,
            'success_rate': round((success_total / total_requests) * 100, 1) if total_requests else 0.0,
            'error_rate': round((error_total / total_requests) * 100, 1) if total_requests else 0.0,
        },
        'engagement': {
            'unique_queries': len(query_counter),
            'top_query_share': top_query_share,
            'active_days': len(daily_series),
        },
        'top_queries': _top_counts(query_counter),
        'top_endpoints': _top_counts(endpoint_counter),
        'top_status_codes': _top_counts(status_counter),
        'top_sorts': _top_counts(sort_counter),
        'top_buckets': _top_counts(bucket_counter),
        'daily_volume': daily_series[-7:],
        'hourly_volume': hourly_series,
        'recent_requests': recent_requests,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'log_files': [str(path) for path in _dashboard_log_files(log_path)],
    }


def _load_crawl_report(crawl_report_path):
    if not crawl_report_path:
        return None
    report_file = Path(crawl_report_path)
    if not report_file.exists():
        return None
    try:
        return json.loads(report_file.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return None


def _performance_series(perf_history):
    if not perf_history:
        return []
    series = []
    for item in perf_history[-12:]:
        metrics = item.get('metrics', {})
        series.append(
            {
                'label': item.get('timestamp', '')[-8:],
                'avg_ms': metrics.get('avg_ms', 0),
                'p95_ms': metrics.get('p95_ms', 0),
                'qps': metrics.get('qps', 0),
            }
        )
    return series


def _write_access_log(log_path, endpoint, status_code, took_ms, cached):
    if not log_path:
        return
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    query = request.args.get('q', '').replace('\n', ' ')
    page = request.args.get('page', '')
    limit = request.args.get('limit', '')
    sort_mode = request.args.get('sort', '')
    bucket = request.args.get('bucket', '')
    output_format = request.args.get('format', '')
    line = (
        f"{timestamp} method={request.method} endpoint={endpoint} status={status_code} "
        f"took_ms={took_ms:.3f} cached={cached} query=\"{query}\" page={page} limit={limit} "
        f"sort={sort_mode} bucket={bucket} format={output_format}"
    )
    resolved = _resolve_log_path(log_path)
    path_obj = Path(resolved)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with path_obj.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def create_app(
    index_path=None,
    index_data=None,
    log_file_path='logs/access_{date}.log',
    crawl_report_path=_DEFAULT_CRAWL_REPORT_PATH,
    perf_history_path=_DEFAULT_PERF_HISTORY_PATH,
):
    app = Flask(__name__, template_folder='templates')
    app.config['LOG_FILE_PATH'] = log_file_path
    app.config['CRAWL_REPORT_PATH'] = crawl_report_path
    app.config['PERF_HISTORY_PATH'] = perf_history_path

    if index_data is not None:
        _SEARCH_CACHE.clear()
        index.clear()
        index.update(index_data)
    elif index_path:
        ensure_index_loaded(index_path)

    @app.get('/')
    def home():
        query = request.args.get('q', '').strip()
        sections = []
        error = None
        page, page_error = _parse_positive_int(request.args.get('page'), 1, 'page', 100000)
        limit, limit_error = _parse_positive_int(request.args.get('limit'), _DEFAULT_LIMIT, 'limit', 200)
        sort_mode, sort_error = _parse_sort(request.args.get('sort'))
        bucket, bucket_error = _parse_bucket(request.args.get('bucket'))
        if page_error or limit_error or sort_error or bucket_error:
            error = page_error or limit_error or sort_error or bucket_error

        view_meta = {
            'page': page or 1,
            'limit': limit or _DEFAULT_LIMIT,
            'sort': sort_mode or 'relevance',
            'bucket': bucket or 'all',
        }
        pagination = {'page': view_meta['page'], 'total_pages': 0, 'total': 0}

        if query and not error:
            started = time.perf_counter()
            result, cached = _cached_search(query)
            took_ms = round((time.perf_counter() - started) * 1000, 3)
            payload = _to_json_payload(query, result, page, limit, took_ms, cached, sort_mode, bucket)
            sections = _result_sections_from_payload(query, payload)
            view_meta = payload['meta']
            pagination = _pagination_for_ui(payload)

        prev_url = None
        next_url = None
        if query and pagination['page'] > 1:
            prev_url = _build_page_url(
                query,
                pagination['page'] - 1,
                view_meta['limit'],
                view_meta['sort'],
                view_meta.get('bucket', 'all'),
            )
        if query and pagination['total_pages'] > 0 and pagination['page'] < pagination['total_pages']:
            next_url = _build_page_url(
                query,
                pagination['page'] + 1,
                view_meta['limit'],
                view_meta['sort'],
                view_meta.get('bucket', 'all'),
            )

        return render_template(
            'search.html',
            query=query,
            sections=sections,
            error=error,
            view_meta=view_meta,
            pagination=pagination,
            prev_url=prev_url,
            next_url=next_url,
        )

    @app.get('/health')
    def health():
        return {'status': 'ok', 'index_words': len(index), 'cache_size': len(_SEARCH_CACHE)}

    @app.get('/api/insights')
    def api_insights():
        payload = _build_dashboard_payload(app.config.get('LOG_FILE_PATH'))
        payload['crawl_report'] = _load_crawl_report(app.config.get('CRAWL_REPORT_PATH'))
        return jsonify(payload)

    @app.get('/api/crawl/report')
    def api_crawl_report():
        report = _load_crawl_report(app.config.get('CRAWL_REPORT_PATH'))
        if report is None:
            return jsonify({'error': 'crawl report not found', 'path': app.config.get('CRAWL_REPORT_PATH')}), 404
        return jsonify(report)

    @app.get('/api/performance/history')
    def api_performance_history():
        return jsonify(
            {
                'history': load_benchmark_history(app.config.get('PERF_HISTORY_PATH')),
                'path': app.config.get('PERF_HISTORY_PATH'),
            }
        )

    @app.get('/api/insights/export')
    def api_insights_export():
        started = time.perf_counter()
        endpoint = '/api/insights/export'
        output_format = request.args.get('format', 'json').strip().lower()
        if output_format not in {'json', 'csv'}:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': 'format must be json or csv'}), 400

        dashboard = _build_dashboard_payload(app.config.get('LOG_FILE_PATH'))
        took_ms = round((time.perf_counter() - started) * 1000, 3)

        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if output_format == 'json':
            text = json.dumps(dashboard, ensure_ascii=False, indent=2)
            filename = f'insights_report_{stamp}.json'
            content_type = 'application/json; charset=utf-8'
        else:
            text = _dashboard_to_csv_text(dashboard)
            filename = f'insights_report_{stamp}.csv'
            content_type = 'text/csv; charset=utf-8'

        _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 200, took_ms, False)
        return Response(
            text,
            headers={'Content-Disposition': f'attachment; filename={filename}'},
            content_type=content_type,
        )

    @app.get('/dashboard')
    def dashboard():
        payload = _build_dashboard_payload(app.config.get('LOG_FILE_PATH'))
        payload['crawl_report'] = _load_crawl_report(app.config.get('CRAWL_REPORT_PATH'))
        return render_template('dashboard.html', dashboard=payload)

    @app.get('/portfolio')
    def portfolio():
        dashboard_payload = _build_dashboard_payload(app.config.get('LOG_FILE_PATH'))
        crawl_report = _load_crawl_report(app.config.get('CRAWL_REPORT_PATH'))
        perf_history = load_benchmark_history(app.config.get('PERF_HISTORY_PATH'))
        return render_template(
            'portfolio.html',
            dashboard=dashboard_payload,
            crawl_report=crawl_report,
            perf_history=perf_history,
            perf_series=_performance_series(perf_history),
        )

    @app.get('/api/search')
    def api_search():
        started = time.perf_counter()
        endpoint = '/api/search'
        query = request.args.get('q', '').strip()
        if not query:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': 'Missing query parameter q'}), 400

        page, page_error = _parse_positive_int(request.args.get('page'), 1, 'page', 100000)
        if page_error:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': page_error}), 400

        limit, limit_error = _parse_positive_int(request.args.get('limit'), _DEFAULT_LIMIT, 'limit', 200)
        if limit_error:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': limit_error}), 400

        sort_mode, sort_error = _parse_sort(request.args.get('sort'))
        if sort_error:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': sort_error}), 400
        bucket, bucket_error = _parse_bucket(request.args.get('bucket'))
        if bucket_error:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': bucket_error}), 400

        result, cached = _cached_search(query)
        took_ms = round((time.perf_counter() - started) * 1000, 3)
        payload = _to_json_payload(query, result, page, limit, took_ms, cached, sort_mode, bucket)
        _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 200, took_ms, cached)
        return jsonify(payload)

    @app.get('/api/export')
    def api_export():
        started = time.perf_counter()
        endpoint = '/api/export'
        query = request.args.get('q', '').strip()
        output_format = request.args.get('format', 'json').strip().lower()

        if not query:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': 'Missing query parameter q'}), 400
        if output_format not in {'json', 'csv'}:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': 'format must be json or csv'}), 400

        page, page_error = _parse_positive_int(request.args.get('page'), 1, 'page', 100000)
        if page_error:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': page_error}), 400

        limit, limit_error = _parse_positive_int(request.args.get('limit'), _DEFAULT_LIMIT, 'limit', _EXPORT_LIMIT_MAX)
        if limit_error:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': limit_error}), 400

        sort_mode, sort_error = _parse_sort(request.args.get('sort'))
        if sort_error:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': sort_error}), 400
        bucket, bucket_error = _parse_bucket(request.args.get('bucket'))
        if bucket_error:
            took = (time.perf_counter() - started) * 1000
            _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 400, took, False)
            return jsonify({'error': bucket_error}), 400

        result, cached = _cached_search(query)
        took_ms = round((time.perf_counter() - started) * 1000, 3)
        payload = _to_json_payload(query, result, page, limit, took_ms, cached, sort_mode, bucket)

        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if output_format == 'json':
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            filename = f'search_results_{stamp}.json'
            content_type = 'application/json; charset=utf-8'
        else:
            text = _to_csv_text(payload)
            filename = f'search_results_{stamp}.csv'
            content_type = 'text/csv; charset=utf-8'

        _write_access_log(app.config.get('LOG_FILE_PATH'), endpoint, 200, took_ms, cached)
        return Response(
            text,
            headers={'Content-Disposition': f'attachment; filename={filename}'},
            content_type=content_type,
        )

    return app


def run_web_ui(index_path, host, port):
    app = create_app(index_path=index_path)

    print(BLUE_COLOR + f"Starting web UI at http://{host}:{port}" + '\033[0m')
    app.run(host=host, port=port)
