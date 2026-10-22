# Contributing

Bug reports, reproducible examples, documentation improvements and focused fixes are welcome. Follow the [Code of Conduct](CODE_OF_CONDUCT.md). Do not include credentials or private crawl data in issues.

## Local workflow

Use the [README setup](README.md#development-setup) with Python 3.12 and a repository-local `.venv`. On an external SSD, verify the mounted device first and source the storage script before installing. `requirements-dev.txt` installs the project's existing development tools through `pyproject.toml`.

1. Branch from the current default branch and preserve any existing local changes.
2. Describe the user-visible problem, then reproduce bugs with a fixture or Mock.
3. Implement the smallest fix. Preserve the documented index and search contracts.
4. Run `python -m ruff check .`, `python -m coverage run -m pytest`, and `python -m coverage report -m`.
5. Replay the offline benchmark when search behavior changes. For packaging changes, build and run the installed-package smoke check from the README.
6. Update the relevant docs and `CHANGELOG.md`, then open a PR with before/after behavior and validation results.

Tests must not access external websites; an autouse fixture blocks non-loopback connections. Do not weaken coverage gates or delete a failing regression to make CI pass. Avoid committing generated indexes, logs, build outputs or environments.

Linux CI covers Python 3.10–3.12; macOS and Windows cover Python 3.12. `python -m tox -e py310,py311,py312,lint` remains available when those local interpreters exist. Missing interpreters are skipped, so local tox success alone does not establish all-version support.

## Review and releases

PRs should state compatibility changes and remaining limitations. Maintainers merge after CI and review, then follow [the release procedure](docs/releasing.md). A release is not a promise that all public-web crawling edge cases are supported. The [roadmap](docs/roadmap.md) lists the next reliability work and its acceptance criteria.
