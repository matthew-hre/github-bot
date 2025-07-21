# Run ruff, pyright, pytest, and taplo in check mode
ci:
    uv run ruff format --preview --check
    uv run ruff check
    uv run pyright app tests
    uv run pytest
    uv run taplo fmt --check pyproject.toml

# Run ruff and taplo in fix mode
autofix:
    uv run ruff check --fix
    uv run ruff format --preview
    uv run taplo fmt --check pyproject.toml
