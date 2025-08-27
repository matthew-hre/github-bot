[private]
default:
    @just --list

# Run taplo, ruff, pytest, and basedpyright in check mode
check:
    uv run taplo fmt --check --diff pyproject.toml
    uv run ruff format --preview --check
    uv run ruff check
    uv run pytest
    uv run basedpyright app tests

# Run taplo and ruff in fix mode
fix:
    uv run taplo fmt pyproject.toml
    uv run ruff format --preview
    uv run ruff check --fix
