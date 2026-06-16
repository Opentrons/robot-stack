# displays list of available commands
@_default:
    uv run just --list

# format justfile
@fmt:
    just --fmt --unstable

# update opentrons repositories
@go *args:
    uv run ./automation/go.py {{ args }}

# find GitHub Actions build jobs for a pushed OT-2 or Flex release tag
@track-builds *args:
    uv run ./automation/track_builds.py {{ args }}

# print CloudFront invalidation command for a release tag
@invalidate-cloudfront *args:
    uv run ./automation/invalidate_cloudfront.py {{ args }}

# format and lint with ruff
@fix:
    uv run ruff format .
    uv run ruff check --fix --unsafe-fixes .

# format justfile, lint/format Python, and type-check (run before commit or PR)
@prep: fmt fix ty

@manifest:
    uv run ./automation/manifest.py

# fetch OT-2 app and robot assets, write HTML report to .build/ot2-assets.html
@ot2-assets:
    uv run ./automation/ot2_assets.py

# fetch Flex app and robot assets, write HTML report to .build/flex-assets.html
@flex-assets:
    uv run ./automation/flex_assets.py

# generate asset inventories, release guides, and index under pages/
@assets-pages:
    uv run ./automation/publish_assets_pages.py

# generate all pages/ HTML and serve at http://127.0.0.1:8765/
@assets-serve:
    uv run ./automation/publish_assets_pages.py --serve --open-browser

# verify coordinated Flex release tag across opentrons, oe-core, and ot3-firmware
@validate-release-tags *args:
    uv run ./automation/validate_release_tags.py {{ args }}

@ty:
    uv sync
    uv run ty check

teardown:
    rm -rf .venv

setup:
    uv venv .venv --python 3.14
    uv sync
    uv pip install -e .
