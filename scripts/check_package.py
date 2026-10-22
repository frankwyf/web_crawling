"""Install a wheel and its declared dependencies into a fresh disposable environment."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--venv', type=Path, required=True)
    args = parser.parse_args()
    wheels = list(args.dist.glob('*.whl'))
    if len(wheels) != 1:
        parser.error('Expected exactly one wheel in --dist')
    if args.venv.exists():
        parser.error('--venv must be a new directory')
    subprocess.run([sys.executable, '-m', 'venv', str(args.venv)], check=True)
    interpreter = args.venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    subprocess.run([str(interpreter), '-m', 'pip', 'install', str(wheels[0].resolve())], check=True)
    smoke = Path(__file__).with_name('smoke_installed.py').resolve()
    subprocess.run([str(interpreter), str(smoke)], check=True)


if __name__ == '__main__':
    main()
