# Contributing

Thank you for your interest in contributing.

## Development Setup

1. Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

2. Run the CLI quick check:

```powershell
.\.venv\Scripts\python .\search.py load
.\.venv\Scripts\python .\search.py find life
```

3. Run the web UI:

```powershell
.\.venv\Scripts\python .\search.py web
```

## Contribution Flow

1. Fork and create a branch.
2. Keep changes focused and small.
3. Update README and CHANGELOG if behavior changes.
4. Open a pull request with clear description and test steps.

## Code Style

- Keep functions small and explicit.
- Avoid breaking existing CLI behavior.
- Add comments only when logic is non-obvious.
