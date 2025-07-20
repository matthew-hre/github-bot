ci:
    uv run ruff format --preview
    uv run ruff check
    uv run pyright app tests
    uv run pytest
    uv run taplo fmt pyproject.toml