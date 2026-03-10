# Contributing

Thanks for contributing.

## Development setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements-dev.txt
```

3. Run tests:

```bash
pytest
```

## Branch and commit style

- Open a branch from `main`.
- Use conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`).
- Open a PR and wait for CI checks.

## Scope guardrails

- Do not add secrets to source control.
- Keep first-seen detection behavior stable.
- Avoid breaking state file compatibility.
