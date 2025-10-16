[private]
default:
    @just --list

# Run taplo, ruff, and basedpyright in check mode
check:
    uv run taplo fmt --check --diff pyproject.toml
    uv run ruff format --check
    uv run ruff check
    uv run basedpyright app

# Run taplo and ruff in fix mode
fix:
    uv run taplo fmt pyproject.toml
    uv run ruff format
    uv run ruff check --fix
