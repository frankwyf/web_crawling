"""Compatible index validation and single-file replacement helpers."""

import json
import os
import tempfile
from pathlib import Path


class IndexFormatError(ValueError):
    """An index cannot safely be consumed by the search engine."""


def validate_output_paths(index_path, report_path):
    if Path(index_path).resolve() == Path(report_path).resolve():
        raise ValueError('Index and report must use different output paths.')


def validate_index(data):
    if not isinstance(data, dict):
        raise IndexFormatError('Invalid index: expected an object mapping terms to posting lists')
    for term, postings in data.items():
        if not isinstance(term, str) or not term or not isinstance(postings, list):
            raise IndexFormatError('Invalid index: each non-empty term must map to a list')
        pages = set()
        for doc in postings:
            prefix = f'Invalid index: posting for {term!r}'
            if not isinstance(doc, dict):
                raise IndexFormatError(f'{prefix} must be an object')
            for field, minimum in (('Page', 0), ('Frequency', 1), ('Links', 0)):
                value = doc.get(field)
                if type(value) is not int or value < minimum:
                    raise IndexFormatError(f'{prefix}: {field} must be an integer >= {minimum}')
            if not isinstance(doc.get('URL'), str) or not doc['URL'].strip():
                raise IndexFormatError(f'{prefix}: URL must be a non-empty string')
            positions = doc.get('Positions')
            if (
                not isinstance(positions, list)
                or not positions
                or any(type(position) is not int or position < 0 for position in positions)
                or any(left >= right for left, right in zip(positions, positions[1:]))
                or len(positions) != doc['Frequency']
            ):
                raise IndexFormatError(f'{prefix}: Positions must increase strictly and match Frequency')
            if doc['Page'] in pages:
                raise IndexFormatError(f'{prefix}: duplicate Page {doc["Page"]}')
            pages.add(doc['Page'])


def read_index(path):
    try:
        with Path(path).open(encoding='utf-8') as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise IndexFormatError(f'Invalid index {path}: {error}') from error
    validate_index(data)
    return data


def atomic_write_json(path, data):
    """Replace only after a complete write; keep the temporary file beside its target."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', dir=target.parent,
            prefix=f'.{target.name}.', suffix='.tmp', delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
