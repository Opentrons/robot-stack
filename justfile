# displays list of available commands
@_default:
    uv run just --list

# format justfile
@fmt:
    just --fmt --unstable

# update opentrons repositories
@go:
    uv run go.py

# lint and format with ruff
@fix:
    uv run black go.py
    uv run ruff check --fix --unsafe-fixes go.py
