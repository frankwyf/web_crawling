import search


def _sample_index():
    return {
        "hello": [
            {"Page": 1, "URL": "u1", "Frequency": 2, "Positions": [0, 5], "Links": 2},
            {"Page": 2, "URL": "u2", "Frequency": 1, "Positions": [3], "Links": 1},
        ],
        "world": [
            {"Page": 1, "URL": "u1", "Frequency": 1, "Positions": [1], "Links": 2},
            {"Page": 3, "URL": "u3", "Frequency": 1, "Positions": [0], "Links": 1},
        ],
        "python": [
            {"Page": 3, "URL": "u3", "Frequency": 2, "Positions": [1, 4], "Links": 1}
        ],
    }


def test_search_query_single_word_returns_ranked_pages():
    result = search.search_query("hello", _sample_index())

    assert result["type"] == "single"
    assert len(result["ranked_pages"]) == 2
    assert result["ranked_pages"][0][0] == 1


def test_search_query_phrase_returns_structured_buckets():
    result = search.search_query("hello world", _sample_index())

    assert result["type"] == "phrase"
    assert "phrase_result" in result
    assert "any_order_result" in result
    assert "each_query_result" in result
    assert len(result["phrase_result"]) >= 1


def test_search_query_empty_returns_empty_type():
    result = search.search_query("", _sample_index())

    assert result["type"] == "empty"
    assert result["ranked_pages"] == []
