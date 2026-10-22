import json

import pytest

from web_crawling import core, storage


def posting(**changes):
    return {'Page': 0, 'URL': 'legacy-page-id', 'Frequency': 1, 'Positions': [0], 'Links': 0, **changes}


@pytest.fixture(autouse=True)
def preserve_index():
    saved = dict(core.index)
    yield
    core.index.clear()
    core.index.update(saved)


def test_interrupted_index_write_preserves_previous_file(monkeypatch, tmp_path):
    target = tmp_path / 'index.json'
    previous = json.dumps({'old': [posting()]})
    target.write_text(previous, encoding='utf-8')

    def interrupted_dump(payload, handle, **kwargs):
        handle.write('{"unfinished":')
        raise OSError('disk write interrupted')

    monkeypatch.setattr(json, 'dump', interrupted_dump)
    with pytest.raises(OSError, match='interrupted'):
        core.build_index([['new']], target, ['new-page'], [0])

    assert target.read_text(encoding='utf-8') == previous
    assert sorted(path.name for path in tmp_path.iterdir()) == ['index.json']


def test_zero_page_build_does_not_replace_existing_index(tmp_path):
    target = tmp_path / 'index.json'
    target.write_text('{"old": []}', encoding='utf-8')

    with pytest.raises(ValueError, match='No pages'):
        core.build_index([], target, [], [])

    assert target.read_text(encoding='utf-8') == '{"old": []}'


@pytest.mark.parametrize('payload', [
    [], {'word': {}}, {'word': [posting(Page=True)]},
    {'word': [posting(Positions=[-1])]}, {'word': [posting(Frequency=2)]},
    {'word': [posting(URL='')]}, {'word': [posting(Links=-1)]},
    {'word': [posting(Frequency=2, Positions=[1, 0])]},
    {'word': [posting(), posting()]},
])
def test_invalid_index_rejected_without_mutating_loaded_state(tmp_path, payload):
    target = tmp_path / 'invalid.json'
    target.write_text(json.dumps(payload), encoding='utf-8')
    core.index.clear()
    core.index['sentinel'] = [posting()]

    with pytest.raises(ValueError, match='Invalid index'):
        core.load_index_json(target)

    assert core.index == {'sentinel': [posting()]}


def test_explicit_index_path_reloads_instead_of_reusing_another_file(tmp_path):
    first, second = tmp_path / 'first.json', tmp_path / 'second.json'
    first.write_text(json.dumps({'first': [posting()]}), encoding='utf-8')
    second.write_text(json.dumps({'second': [posting()]}), encoding='utf-8')
    core.load_index_json(first)

    core.ensure_index_loaded(second)

    assert set(core.index) == {'second'}


def test_nested_output_directory_and_legacy_index_round_trip(tmp_path):
    target = tmp_path / 'nested' / 'index.json'
    built = core.build_index([['hello', 'world', 'hello']], target, ['legacy-page-id'], [0])
    loaded = core.load_index_json(target)

    assert loaded == built
    assert loaded['hello'][0]['Positions'] == [0, 2]
    assert core.search_query('hello', loaded)['ranked_pages'][0][1] == 'legacy-page-id'


def test_failed_atomic_replace_keeps_previous_file_and_cleans_sibling(monkeypatch, tmp_path):
    target = tmp_path / 'index.json'
    target.write_text('previous', encoding='utf-8')

    def fail_replace(source, destination):
        assert source.parent == destination.parent == tmp_path
        raise PermissionError('replace denied')

    monkeypatch.setattr(storage.os, 'replace', fail_replace)
    with pytest.raises(PermissionError, match='replace denied'):
        storage.atomic_write_json(target, {'new': []})

    assert target.read_text(encoding='utf-8') == 'previous'
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize('content', [b'{unfinished', b'\xff'])
def test_invalid_encoding_or_json_preserves_loaded_index(tmp_path, content):
    target = tmp_path / 'invalid.json'
    target.write_bytes(content)
    core.index.clear()
    core.index['sentinel'] = [posting()]

    with pytest.raises(ValueError, match='Invalid index'):
        core.load_index_json(target)

    assert set(core.index) == {'sentinel'}
