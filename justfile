ci:
    uv run ruff format --preview --check
    uv run ruff check
    uv run pyright app tests
    uv run pytest
    uv run taplo fmt --check pyproject.toml
