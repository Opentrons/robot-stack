# robot-stack

Tools to inspect, tag, and build Opentrons robots across the multi-repo software stack.

The only external dependency is [uv](https://docs.astral.sh/uv/).

Instead of make, use [just](https://github.com/casey/just). The VS Code justfile helper is [vscode-just](https://github.com/nefrob/vscode-just).

## How

- see the possible commands
  - `uv run just`
- format the justfile
  - `uv run just fmt`
- format and lint Python
  - `uv run just fix`
- sync repos and inspect release state
  - `uv run just go`

## Release Paths

`just go` runs `automation/go.py`, an interactive release helper. It supports two robot paths; **Flex is the default**.

| Path | Repos | App repo | Version scheme |
|---|---|---|---|
| **Flex** | `opentrons`, `oe-core`, `ot3-firmware` | `opentrons` | Semver (`v8.5.0`, alpha tags like `v8.5.0-alpha.6`) |
| **OT-2** | `opentrons-ot2`, `buildroot` | `opentrons-ot2` | Calendar semver (internal + external; see below) |

`robot-stack-infra` is always cloned and pulled for both paths as a reference repo. It is not included in release tables or tagging.

Each repo uses isolation branches named `chore_release-<version>` during a release cycle.

## OT-2 calendar semver

OT-2 uses semver-shaped versions so electron-updater and robot update checks work. **Internal and external channels use different patch schemes.** Within a channel, the app and robot OS share the same version string.

Calendar components use **US Eastern** (`America/New_York`):

| Component | Meaning |
|---|---|
| **Major (YY)** | Two-digit year (`2026` → `26`) |
| **Minor (M)** | Month, no leading zero (`June` → `6`) |

### Internal (`internal@`)

Patch encodes **day + same-day build** as `DNN = day * 100 + build_num` (build 1–99 per day).

| Example | Meaning |
|---|---|
| `internal@26.5.2601` | First stable internal build on May 26, 2026 |
| `internal@26.5.2602-alpha` | Second alpha internal build that day |
| `internal@26.5.101` | First stable internal build on May 1, 2026 |

Same-day follow-ups increment the build number in the patch (`2601` → `2602`).

### External (`v`)

Patch **N** is the monthly release counter, **starting at 0**. At most 10 stable external releases per month (`N` = 0–9).

| Example | Meaning |
|---|---|
| `v26.6.0` | First stable external release in June 2026 |
| `v26.6.1` | Second stable external release that month |
| `v26.6.0-alpha.0` | First external alpha on base `26.6.0` |
| `v26.6.0-alpha.1` | Second external alpha on the same base |

External alpha and beta builds use standard semver prerelease numbering (`-alpha.0`, `-alpha.1`, `-beta.0`, …) on a fixed `YY.M.N` base instead of bumping the patch.

### Summary

| Channel | Stable | Alpha | Beta |
|---|---|---|---|
| External | `v26.6.0` | `v26.6.0-alpha.0` | `v26.6.0-beta.0` |
| Internal | `internal@26.5.2601` | `internal@26.5.2601-alpha` | `internal@26.5.2601-beta` |

Implementation lives in `automation/go.py` and `opentrons-ot2/scripts/ot2_calendar_semver.py`.
