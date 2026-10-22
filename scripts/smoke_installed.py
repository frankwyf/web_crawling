"""Exercise an installed distribution from outside the source checkout, offline."""

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-root', type=Path, help='Optional pip --target directory for local checks.')
    args = parser.parse_args()
    checkout = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    bin_dir = Path(sys.executable).parent
    if args.package_root:
        package_root = args.package_root.resolve()
        sys.path.insert(0, str(package_root))
        environment['PYTHONPATH'] = str(package_root)
        bin_dir = package_root / ('Scripts' if os.name == 'nt' else 'bin')

    from web_crawling import __file__ as package_file
    from web_crawling import __version__
    from web_crawling.webui import create_app

    assert not Path(package_file).resolve().is_relative_to(checkout / 'web_crawling'), 'Imported source checkout'
    assert importlib.metadata.version('web-crawling-search') == __version__

    with tempfile.TemporaryDirectory(prefix='web-crawling-smoke-') as directory:
        workdir = Path(directory)

        def run(*command, expected=0):
            result = subprocess.run(command, cwd=workdir, env=environment, capture_output=True, text=True)
            assert result.returncode == expected, (command, result.stdout, result.stderr)
            return result

        console = bin_dir / ('web-crawling.exe' if os.name == 'nt' else 'web-crawling')
        assert __version__ in run(str(console), '--version').stdout
        run(sys.executable, '-m', 'web_crawling', 'demo')
        result = run(sys.executable, '-m', 'web_crawling', 'find', 'crawler', '--index-file', 'demo_index.json')
        assert 'https://example.invalid/demo/' in result.stdout
        run(sys.executable, '-m', 'search', 'load', '--index-file', 'demo_index.json')
        missing = run(sys.executable, '-m', 'web_crawling', 'load', '--index-file', 'missing.json', expected=1)
        assert 'Error:' in missing.stderr and 'Traceback' not in missing.stderr
        assert json.loads((workdir / 'demo_report.json').read_text())['crawl_stats']['source'] == 'offline-demo'

        app = create_app(index_path=str(workdir / 'demo_index.json'), log_file_path=str(workdir / 'access_{date}.log'))
        client = app.test_client()
        for route in ('/', '/dashboard', '/portfolio', '/health', '/static/app.css'):
            assert client.get(route).status_code == 200, route
        assert client.get('/api/search?q=crawler').get_json()['results']

    print(f'Installed package {__version__}: CLI, bundled corpus, legacy entry point, API, templates, and CSS passed')


if __name__ == '__main__':
    main()
