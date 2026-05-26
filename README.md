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
| **OT-2** | `opentrons-ot2`, `buildroot` | `opentrons-ot2` | Calendar semver (`v26.5.2601`) |

`robot-stack-infra` is always cloned and pulled for both paths as a reference repo. It is not included in release tables or tagging.

Each repo uses isolation branches named `chore_release-<version>` during a release cycle.

## OT-2 calendar semver

The OT-2 app and robot OS share the same version string. Electron-updater requires semver, so OT-2 uses semver-shaped versions with calendar components instead of Flex-style product semver.

Calendar components use **US Eastern** (`America/New_York`):

| Component | Meaning | Example (May 26, 2026) |
|---|---|---|
| **Major (YY)** | Two-digit year | `26` |
| **Minor (M)** | Month (no leading zero) | `5` |
| **Patch (DNN)** | Day + same-day build number | `2601` (day 26, build 01) |

Single-digit days stay single-digit in the patch (semver does not allow leading zeros on numeric identifiers). The patch encodes day and build as:

```text
DNN = day * 100 + build_num
```

| Day | Patch width | First build | Second build |
|---|---|---|---|
| 1-9 | 3 digits | `26.5.101` | `26.5.102` |
| 10-31 | 4 digits | `26.5.1001` | `26.5.1002` |
| 26 (example) | 4 digits | `26.5.2601` | `26.5.2602` |

`build_num` runs from 1 to 99 for multiple releases on the same day within a stability channel (stable, alpha, or beta).

### Tags

| Channel | Stable | Alpha | Beta |
|---|---|---|---|
| External | `v26.5.2601` | `v26.5.2601-alpha` | `v26.5.2601-beta` |
| Internal | `internal@26.5.2601` | `internal@26.5.2601-alpha` | `internal@26.5.2601-beta` |

Same-day follow-up builds increment the build number in the patch (`2601` → `2602`), keeping the same `-alpha` or `-beta` suffix when applicable.

Implementation lives in `automation/go.py` (`encode_ot2_version`, `decode_ot2_version`, `ot2_version_for_date`).
