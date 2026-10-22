"""Validate the tag against both distributions and generate release checksums."""

import argparse
import hashlib
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path


def prepare_release(directory, tag):
    wheels = list(directory.glob('*.whl'))
    sources = list(directory.glob('*.tar.gz'))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError('Release requires exactly one wheel and one source distribution')
    with zipfile.ZipFile(wheels[0]) as archive:
        names = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
        if len(names) != 1:
            raise ValueError('Wheel must contain exactly one METADATA file')
        wheel_metadata = BytesParser().parsebytes(archive.read(names[0]))
    with tarfile.open(sources[0]) as archive:
        names = [member for member in archive.getmembers() if member.name.count('/') == 1 and member.name.endswith('/PKG-INFO')]
        if len(names) != 1:
            raise ValueError('Source distribution must contain exactly one root PKG-INFO')
        with archive.extractfile(names[0]) as handle:
            source_metadata = BytesParser().parsebytes(handle.read())
    for metadata in (wheel_metadata, source_metadata):
        if metadata['Name'] != 'web-crawling-search' or tag != f'v{metadata["Version"]}':
            raise ValueError(f'Tag {tag} does not match distribution {metadata["Name"]} {metadata["Version"]}')
    checksums = ''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in sorted(wheels + sources))
    (directory / 'SHA256SUMS').write_text(checksums, encoding='utf-8')
    print(f'{tag}: distribution metadata matches; SHA256SUMS written')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    try:
        prepare_release(args.dist, args.tag)
    except (OSError, ValueError) as error:
        print(f'Release validation failed: {error}', file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == '__main__':
    main()
