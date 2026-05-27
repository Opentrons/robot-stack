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

# fetch OT-2 app and robot assets, write HTML report to .build/ot2-assets.html
@ot2-assets:
    uv run ./automation/ot2_assets.py

# generate OT-2 assets report and serve it on http://127.0.0.1:8765/
@ot2-assets-serve:
    uv run ./automation/ot2_assets.py --serve --open-browser

# fetch Flex app and robot assets, write HTML report to .build/flex-assets.html
@flex-assets:
    uv run ./automation/flex_assets.py

# generate Flex assets report and serve it on http://127.0.0.1:8766/
@flex-assets-serve:
    uv run ./automation/flex_assets.py --serve --open-browser

# generate Flex + OT-2 reports and index for GitHub Pages (pages/)
@assets-pages:
    uv run ./automation/publish_assets_pages.py

@ty:
    uv sync
    uv run ty check

teardown:
    rm -rf .venv

setup:
    uv venv .venv --python 3.14
    uv sync
    uv pip install -e .
