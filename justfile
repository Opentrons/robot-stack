# displays list of available commands
@_default:
    uv run just --list

# format justfile
@fmt:
    just --fmt --unstable

# update opentrons repositories
@go:
    uv run ./automation/go.py

# lint and format with ruff
@fix:
    uv run black .
    uv run ruff check --fix --unsafe-fixes .

@manifest:
    uv run ./automation/manifest.py

@mypy:
    uv run mypy .
