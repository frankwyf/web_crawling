import csv
import io
import json
import math
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, Response, jsonify, render_template, request

from .core import BLUE_COLOR, ensure_index_loaded, index, search_query

_CACHE_MAX_SIZE = 128
_SEARCH_CACHE = OrderedDict()
_SUPPORTED_SORTS = {'relevance', 'frequency_desc', 'score_desc', 'page_asc', 'page_desc'}
_EXPORT_LIMIT_MAX = 100
_DEFAULT_LIMIT = 20


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


def _to_json_payload(query, result, page, limit, took_ms, cached, sort_mode):
    payload = {
        'query': query,
        'type': result['type'],
        'meta': {
            'cached': cached,
            'took_ms': took_ms,
            'page': page,
            'limit': limit,
            'sort': sort_mode,
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

        payload['conjunctive'], payload['conjunctive_meta'] = _paginate(conjunctive, page, limit)
        payload['term_at_a_time'], payload['term_at_a_time_meta'] = _paginate(term_at_a_time, page, limit)
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


def _pagination_for_ui(payload):
    if payload['type'] == 'single':
        return payload.get('pagination', {'page': 1, 'total_pages': 0, 'total': 0})

    metas = [
        payload.get('conjunctive_meta', {'total_pages': 0, 'total': 0}),
        payload.get('term_at_a_time_meta', {'total_pages': 0, 'total': 0}),
        payload.get('per_word_meta', {'total_pages': 0, 'total': 0}),
    ]
    page = payload['meta']['page']
    total_pages = max(item.get('total_pages', 0) for item in metas)
    total = max(item.get('total', 0) for item in metas)
    return {'page': page, 'total_pages': total_pages, 'total': total}


def _build_page_url(query, page, limit, sort_mode):
    params = {'q': query, 'page': page, 'limit': limit, 'sort': sort_mode}
    return '/?' + urlencode(params)


def _write_access_log(log_path, endpoint, status_code, took_ms, cached):
    if not log_path:
        return
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    query = request.args.get('q', '').replace('\n', ' ')
    line = (
        f"{timestamp} method={request.method} endpoint={endpoint} status={status_code} "
        f"took_ms={took_ms:.3f} cached={cached} query=\"{query}\""
    )
    path_obj = Path(log_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with path_obj.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def create_app(index_path=None, index_data=None, log_file_path='logs/access.log'):
    app = Flask(__name__, template_folder='templates')
    app.config['LOG_FILE_PATH'] = log_file_path

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
        if page_error or limit_error or sort_error:
            error = page_error or limit_error or sort_error

        view_meta = {'page': page or 1, 'limit': limit or _DEFAULT_LIMIT, 'sort': sort_mode or 'relevance'}
        pagination = {'page': view_meta['page'], 'total_pages': 0, 'total': 0}

        if query and not error:
            started = time.perf_counter()
            result, cached = _cached_search(query)
            took_ms = round((time.perf_counter() - started) * 1000, 3)
            payload = _to_json_payload(query, result, page, limit, took_ms, cached, sort_mode)
            sections = _result_sections_from_payload(query, payload)
            view_meta = payload['meta']
            pagination = _pagination_for_ui(payload)

        prev_url = None
        next_url = None
        if query and pagination['page'] > 1:
            prev_url = _build_page_url(query, pagination['page'] - 1, view_meta['limit'], view_meta['sort'])
        if query and pagination['total_pages'] > 0 and pagination['page'] < pagination['total_pages']:
            next_url = _build_page_url(query, pagination['page'] + 1, view_meta['limit'], view_meta['sort'])

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

        result, cached = _cached_search(query)
        took_ms = round((time.perf_counter() - started) * 1000, 3)
        payload = _to_json_payload(query, result, page, limit, took_ms, cached, sort_mode)
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

        result, cached = _cached_search(query)
        took_ms = round((time.perf_counter() - started) * 1000, 3)
        payload = _to_json_payload(query, result, page, limit, took_ms, cached, sort_mode)

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
