import re
from datetime import datetime

from web_crawling.webui import _resolve_log_path, create_app


def _sample_index():
    return {
        "hello": [
            {"Page": 1, "URL": "https://example.com/1", "Frequency": 2, "Positions": [0, 5], "Links": 1},
            {"Page": 2, "URL": "https://example.com/2", "Frequency": 1, "Positions": [3], "Links": 100},
        ],
        "world": [
            {"Page": 1, "URL": "https://example.com/1", "Frequency": 1, "Positions": [1], "Links": 2},
            {"Page": 3, "URL": "https://example.com/3", "Frequency": 1, "Positions": [0], "Links": 1},
        ],
    }


def test_api_search_requires_query_parameter():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/api/search')

    assert response.status_code == 400
    assert response.get_json()["error"] == "Missing query parameter q"


def test_api_search_returns_single_word_results():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/api/search?q=hello')
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["type"] == "single"
    assert len(payload["results"]) == 2
    assert payload["pagination"]["total"] == 2
    assert payload["meta"]["page"] == 1
    assert payload["meta"]["limit"] == 20


def test_api_search_supports_limit_and_cache_flag():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    first = client.get('/api/search?q=hello&limit=1&page=1').get_json()
    second = client.get('/api/search?q=hello&limit=1&page=2').get_json()

    assert first["pagination"]["returned"] == 1
    assert first["meta"]["cached"] is False
    assert second["pagination"]["returned"] == 1
    assert second["pagination"]["page"] == 2
    assert second["meta"]["cached"] is True


def test_api_search_rejects_invalid_limit():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/api/search?q=hello&limit=0')

    assert response.status_code == 400
    assert response.get_json()["error"] == "limit must be >= 1"


def test_api_search_supports_score_sort():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/api/search?q=hello&sort=score_desc')
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["meta"]["sort"] == "score_desc"
    assert payload["results"][0]["page"] == 2


def test_api_search_rejects_invalid_sort():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/api/search?q=hello&sort=unknown')

    assert response.status_code == 400
    assert "sort must be one of" in response.get_json()["error"]


def test_api_search_supports_bucket_filtering():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/api/search?q=hello%20world&bucket=term_at_a_time')
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["meta"]["bucket"] == "term_at_a_time"
    assert "term_at_a_time" in payload
    assert "conjunctive" not in payload
    assert "per_word" not in payload


def test_api_search_rejects_invalid_bucket():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/api/search?q=hello&bucket=bad')

    assert response.status_code == 400
    assert "bucket must be one of" in response.get_json()["error"]


def test_api_export_csv_returns_attachment():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/api/export?q=hello%20world&format=csv')

    assert response.status_code == 200
    disposition = response.headers["Content-Disposition"]
    assert disposition.startswith("attachment; filename=search_results_")
    assert disposition.endswith(".csv")
    assert re.search(r"search_results_\d{8}_\d{6}\.csv", disposition)
    assert "bucket,page,url,frequency,score,word" in response.get_data(as_text=True)


def test_api_export_rejects_limit_above_export_max():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/api/export?q=hello&format=json&limit=101')

    assert response.status_code == 400
    assert response.get_json()["error"] == "limit must be <= 100"


def test_api_request_writes_access_log(tmp_path):
    log_template = tmp_path / 'access_{date}.log'
    app = create_app(index_data=_sample_index(), log_file_path=str(log_template))
    client = app.test_client()

    response = client.get('/api/search?q=hello')

    expected_path = tmp_path / f"access_{datetime.now().strftime('%Y%m%d')}.log"
    assert response.status_code == 200
    assert expected_path.exists()
    content = expected_path.read_text(encoding='utf-8')
    assert 'endpoint=/api/search' in content
    assert 'status=200' in content


def test_resolve_log_path_appends_date_suffix_for_plain_log_file():
    resolved = _resolve_log_path('logs/access.log')
    expected_day = datetime.now().strftime('%Y%m%d')

    assert resolved.endswith(f'access_{expected_day}.log')


def test_dashboard_insights_aggregate_requests(tmp_path):
    log_template = tmp_path / 'access_{date}.log'
    app = create_app(index_data=_sample_index(), log_file_path=str(log_template))
    client = app.test_client()

    client.get('/api/search?q=hello&bucket=per_word')
    client.get('/api/export?q=hello&format=json&bucket=per_word')

    insights = client.get('/api/insights').get_json()

    assert insights['requests']['total'] == 2
    assert insights['requests']['search_total'] == 1
    assert insights['requests']['export_total'] == 1
    assert insights['top_queries'][0]['label'] == 'hello'
    assert insights['top_buckets'][0]['label'] == 'per_word'
    assert insights['engagement']['unique_queries'] >= 1
    assert 'p95_latency_ms' in insights['requests']
    assert insights['daily_volume']


def test_dashboard_page_renders():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/dashboard')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Search Analytics Dashboard' in html
    assert 'Cache Hit Rate' in html


def test_insights_export_returns_csv_report(tmp_path):
    log_template = tmp_path / 'access_{date}.log'
    app = create_app(index_data=_sample_index(), log_file_path=str(log_template))
    client = app.test_client()

    client.get('/api/search?q=hello')
    response = client.get('/api/insights/export?format=csv')

    disposition = response.headers['Content-Disposition']
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert disposition.startswith('attachment; filename=insights_report_')
    assert disposition.endswith('.csv')
    assert 'section,label,value' in body
    assert 'requests,total,' in body
    assert 'top_queries,hello,' in body


def test_insights_export_rejects_invalid_format():
    app = create_app(index_data=_sample_index())
    client = app.test_client()

    response = client.get('/api/insights/export?format=txt')

    assert response.status_code == 400
    assert response.get_json()['error'] == 'format must be json or csv'


def test_api_crawl_report_returns_404_without_report(tmp_path):
    app = create_app(index_data=_sample_index(), crawl_report_path=str(tmp_path / 'missing_report.json'))
    client = app.test_client()

    response = client.get('/api/crawl/report')

    assert response.status_code == 404
    payload = response.get_json()
    assert payload['error'] == 'crawl report not found'


def test_api_crawl_report_returns_json_when_present(tmp_path):
    report_path = tmp_path / 'crawl_report.json'
    report_path.write_text(
        '{"crawl_stats":{"pages_crawled":10,"pages_failed":0,"started_at":"a","finished_at":"b"},"index_stats":{"unique_terms":123,"total_tokens":456}}',
        encoding='utf-8',
    )
    app = create_app(index_data=_sample_index(), crawl_report_path=str(report_path))
    client = app.test_client()

    response = client.get('/api/crawl/report')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['crawl_stats']['pages_crawled'] == 10
    assert payload['index_stats']['unique_terms'] == 123


def test_api_performance_history_returns_payload(tmp_path):
    perf_file = tmp_path / 'perf_history.jsonl'
    perf_file.write_text('{"timestamp":"2026-06-29 10:00:00","metrics":{"avg_ms":1.23}}\n', encoding='utf-8')
    app = create_app(index_data=_sample_index(), perf_history_path=str(perf_file))
    client = app.test_client()

    response = client.get('/api/performance/history')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['path'] == str(perf_file)
    assert len(payload['history']) == 1
    assert payload['history'][0]['metrics']['avg_ms'] == 1.23


def test_portfolio_page_renders(tmp_path):
    report_path = tmp_path / 'crawl_report.json'
    report_path.write_text(
        '{"crawl_stats":{"pages_crawled":9,"pages_failed":0,"base_url":"https://example.com","duration_seconds":1.2},"index_stats":{"unique_terms":123,"total_tokens":456},"top_terms":[{"term":"hello","total_frequency":9}]}',
        encoding='utf-8',
    )
    perf_file = tmp_path / 'perf_history.jsonl'
    perf_file.write_text(
        '{"timestamp":"2026-06-29 10:00:00","metrics":{"avg_ms":1.23,"p95_ms":2.34,"qps":120,"operations":7},"regression_detected":false}\n',
        encoding='utf-8',
    )

    app = create_app(index_data=_sample_index(), crawl_report_path=str(report_path), perf_history_path=str(perf_file))
    client = app.test_client()

    response = client.get('/portfolio')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Python Crawler Portfolio Storyboard' in html
    assert 'Performance Trend' in html
