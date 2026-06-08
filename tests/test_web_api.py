import re

from web_crawling.webui import create_app


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
    log_path = tmp_path / 'access.log'
    app = create_app(index_data=_sample_index(), log_file_path=str(log_path))
    client = app.test_client()

    response = client.get('/api/search?q=hello')

    assert response.status_code == 200
    assert log_path.exists()
    content = log_path.read_text(encoding='utf-8')
    assert 'endpoint=/api/search' in content
    assert 'status=200' in content
