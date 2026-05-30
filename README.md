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
  - non-interactive example: `uv run just go --non-interactive --skip-assumptions --path flex --release-type internal --stability unstable`
- find GitHub Actions runs after pushing an app tag
  - `uv run just track-builds --path ot2 --tag internal@26.5.2801 --wait`
- print a CloudFront invalidation command after builds finish
  - `uv run just invalidate-cloudfront --path ot2 --tag internal@26.5.2801`

## Release Paths

`just go` runs `automation/go.py`, an interactive release helper. It supports two robot paths; **Flex is the default**.

| Path | Repos | App repo | Version scheme |
|---|---|---|---|
| **Flex** | `opentrons`, `oe-core`, `ot3-firmware` | `opentrons` | Per-repo prefixes (`ot3@`, `internal@`, `v`; see below) |
| **OT-2** | `opentrons-ot2`, `buildroot` | `opentrons-ot2` | Calendar semver for app + internal; buildroot external uses its own `vX.Y.Z` line |

`robot-stack-infra` is always cloned and pulled for both paths as a reference repo. It is not included in release tables or tagging.

Each repo uses isolation branches named `chore_release-<version>` during a **Flex external** release cycle. Flex **internal** and all **OT-2** releases tag default-branch HEAD instead (`edge` / `opentrons-develop` / `main`).

### Tag push order

Push annotated tags in this order. Stack repos first, app monorepo last.

| Path | Order |
|---|---|
| **Flex** | `ot3-firmware` (if needed) → `oe-core` (if needed) → `opentrons` (app, always last) |
| **OT-2** | `buildroot` (if needed) → `opentrons-ot2` (app, always last) |

### Flex semver

Flex repos use different tag prefixes. In `just go`, Flex uses **stable/unstable** stability (unstable = alpha).

| Repo | Internal | External |
|---|---|---|
| `opentrons` | `ot3@X.Y.Z`, alpha `ot3@X.Y.Z-alpha.N` | `vX.Y.Z`, alpha `vX.Y.Z-alpha.N` |
| `oe-core` | `internal@X.Y.Z`, alpha `internal@X.Y.Z-alpha.N` | `v0.X.Y` (independent line) |
| `ot3-firmware` | `internal@vN` | `vN` |

For internal alpha builds, `go` coordinates oe-core alpha numbers with the next `ot3@X.Y.Z-alpha.N` on `opentrons`. Internal oe-core and app stable tags use the prompted base version; if that exact tag already exists on the branch, `go` suggests a patch bump.

### Track release builds

After pushing the app tag, locate CI with `just track-builds`:

```bash
just track-builds --path ot2 --tag internal@26.5.2801 --wait
```

The script finds app, kickoff, and robot OS workflow runs and prints a Rich table plus a Slack copy block with two links (`app` and `ot2` or `flex`). With `--wait`, it polls every 15 seconds until all three workflow runs appear (default timeout 15 minutes).

After builds finish, print a CloudFront invalidation command with `just invalidate-cloudfront --path ot2 --tag internal@26.5.2801`.

## OT-2 calendar semver

OT-2 uses semver-shaped versions so electron-updater and robot update checks work. **Internal and external channels use different patch schemes.** Internal app and robot OS share the same version string. External app uses calendar semver; external buildroot uses an independent traditional semver line (for example `v1.19.9`).

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

**App (`opentrons-ot2`):** patch **N** is the monthly build counter, **starting at 0**. Each external release in the month (stable, alpha, or beta) gets the next **N** slot. At most 10 external releases per month (`N` = 0–9).

| Example | Meaning |
|---|---|
| `v26.6.0` | First external app release in June 2026 |
| `v26.6.1-alpha.0` | Second external build that month (first alpha on base `26.6.1`) |
| `v26.6.1-alpha.1` | Another alpha QA cycle on the same base |
| `v26.6.2` | Third external build that month (stable) |

External alpha and beta app builds use standard semver prerelease numbering (`-alpha.0`, `-alpha.1`, `-beta.0`, …) on the monthly **YY.M.N** base for that build. Prerelease numbers increment on a fixed base; starting a new build in the month bumps **N**.

**Robot OS (`buildroot`):** external stable tags follow the repo's independent traditional semver line, for example `v1.19.9` → `v1.19.10`. They do not use the app calendar version.

### Summary

| Channel | Repo | Stable | Alpha | Beta |
|---|---|---|---|---|
| External | `opentrons-ot2` | `v26.6.0` | `v26.6.1-alpha.0` | `v26.6.1-beta.0` |
| External | `buildroot` | `v1.19.10` | patch bump on traditional line | patch bump on traditional line |
| Internal | both | `internal@26.5.2601` | `internal@26.5.2601-alpha` | `internal@26.5.2601-beta` |

Implementation lives in `automation/go.py` and `opentrons-ot2/scripts/ot2_calendar_semver.py`.
