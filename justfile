# displays list of available commands
@_default:
    uv run just --list

# format justfile
@fmt:
    just --fmt --unstable

# update opentrons repositories
@go:
    uv run ./automation/go.py

# format and lint with ruff
@fix:
    uv run ruff format .
    uv run ruff check --fix --unsafe-fixes .

@manifest:
    uv run ./automation/manifest.py

@ty:
    uv sync
    uv run ty check
